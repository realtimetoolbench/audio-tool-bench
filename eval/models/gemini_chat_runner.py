"""
Gemini Chat runner — multi-turn dialogue + function calling via the google-genai SDK.
Mirrors ChatCompletionsRunner and serves as a baseline for text models such as Gemini 3.x Pro.
"""
import json
import time
import datetime
from typing import Optional, Dict, Any, List

from google import genai
from google.genai import types

from eval.data.task import Task, MessageRole
from eval.data.trace import Trace, TraceStep


def _openai_params_to_gemini_schema(params: Dict[str, Any]) -> Dict[str, Any]:
    """Convert OpenAI JSON schema to a Gemini schema dict (google-genai accepts a dict).

    OpenAI style: {"type":"object","properties":{...},"required":[...]}
    Gemini style: {"type":"OBJECT","properties":{...},"required":[...]}
    The "type" value must be uppercased.
    """
    if not isinstance(params, dict):
        return params
    out: Dict[str, Any] = {}
    for k, v in params.items():
        if k == "type" and isinstance(v, str):
            out[k] = v.upper()
        elif k == "properties" and isinstance(v, dict):
            out[k] = {pk: _openai_params_to_gemini_schema(pv) for pk, pv in v.items()}
        elif k == "items" and isinstance(v, dict):
            out[k] = _openai_params_to_gemini_schema(v)
        elif k == "anyOf" and isinstance(v, list):
            out[k] = [_openai_params_to_gemini_schema(x) for x in v]
        else:
            out[k] = v
    return out


def _openai_tools_to_gemini(openai_tools: List[Dict[str, Any]]) -> List[types.Tool]:
    """Convert tool_executor.get_tools_for_openai() output into a list of Gemini types.Tool."""
    decls = []
    for t in openai_tools:
        fn = t.get("function", t)
        decls.append(types.FunctionDeclaration(
            name=fn["name"],
            description=fn.get("description", ""),
            parameters=_openai_params_to_gemini_schema(fn.get("parameters", {"type": "OBJECT"})),
        ))
    return [types.Tool(function_declarations=decls)]


class GeminiChatRunner:
    """Gemini generate_content multi-turn runner with a manual tool-call loop."""

    def __init__(
        self, api_key: str, model: str = "gemini-3.1-pro-preview",
        tool_executor=None, quiet: bool = False, request_timeout_s: int = 120,
    ):
        # request_timeout_s is per-HTTP-call. retry_options attempts=1 disables
        # SDK-level retry (default 5) — otherwise a hanging request can burn
        # >30min before giving up.
        self.client = genai.Client(
            api_key=api_key,
            http_options=types.HttpOptions(
                timeout=request_timeout_s * 1000,
                retry_options=types.HttpRetryOptions(attempts=1),
            ),
        )
        self.model = model
        self.tool_executor = tool_executor
        self.quiet = quiet

    def run_task(
        self, task: Task, task_path: str,
        system_prompt: Optional[str] = None,
        max_tool_rounds: int = 5,
    ) -> Trace:
        with open(task_path, 'r') as f:
            task_data = json.load(f)
        context_turns = task_data.get("context_turns", [])

        if not self.quiet:
            print(f"\n{'='*60}")
            print(f"Gemini Chat: {task.name} | model: {self.model}")
            print(f"{'='*60}")

        today = datetime.date.today()
        weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][today.weekday()]
        date_ctx = f"Today is {today.strftime('%B %d, %Y')} ({weekday_name}).\n\n"
        sys_text = date_ctx + (system_prompt or "You are a helpful assistant.")

        contents: List[types.Content] = []
        for turn in context_turns:
            role = turn.get("role", "user")
            gemini_role = "user" if role in ("user", "system") else "model"
            contents.append(types.Content(role=gemini_role, parts=[types.Part.from_text(text=turn.get("content", ""))]))

        openai_tools = self.tool_executor.get_tools_for_openai() if self.tool_executor else []
        tools = _openai_tools_to_gemini(openai_tools) if openai_tools else None

        gen_config = types.GenerateContentConfig(
            system_instruction=sys_text,
            tools=tools,
            automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
        )

        trace = Trace(
            task_name=task.name,
            start_time=datetime.datetime.now().isoformat(),
            metadata={
                **task.metadata,
                "mode": "gemini_chat",
                "provider": "gemini-chat",
                "realtime_model": self.model,
                "input_mode": "text",
            },
        )

        step_count = 0
        user_chunks = [c for c in task.chunks if c.role == MessageRole.USER]

        for chunk in user_chunks:
            step_count += 1
            user_text = chunk.content
            contents.append(types.Content(role="user", parts=[types.Part.from_text(text=user_text)]))

            if not self.quiet:
                print(f"\n[Step {step_count}] user: {user_text[:80]}...")

            start_time = time.time()
            llm_calls: List[Dict[str, Any]] = []
            tool_executions: List[Dict[str, Any]] = []
            assistant_text = ""

            for tool_round in range(max_tool_rounds + 1):
                resp = self.client.models.generate_content(
                    model=self.model, contents=contents, config=gen_config,
                )

                finish_reason = None
                content_text = ""
                fn_calls = []
                if resp.candidates:
                    cand = resp.candidates[0]
                    finish_reason = str(cand.finish_reason) if cand.finish_reason else None
                    if cand.content and cand.content.parts:
                        for p in cand.content.parts:
                            if p.text:
                                content_text += p.text
                            if p.function_call:
                                fn_calls.append(p.function_call)

                llm_call: Dict[str, Any] = {
                    "round": tool_round + 1,
                    "finish_reason": finish_reason,
                    "content": content_text,
                    "tool_calls": None,
                }

                if fn_calls:
                    # append assistant message (with function_call parts) to contents
                    contents.append(resp.candidates[0].content)

                    llm_call["tool_calls"] = []
                    tool_result_parts: List[types.Part] = []
                    for fc in fn_calls:
                        func_name = fc.name
                        func_args = dict(fc.args) if fc.args else {}

                        if not self.quiet:
                            print(f"  tool: {func_name}({func_args})")

                        llm_call["tool_calls"].append({
                            "id": func_name,
                            "name": func_name,
                            "arguments": func_args,
                        })

                        if self.tool_executor:
                            result = self.tool_executor.execute_tool(func_name, func_args)
                            tool_executions.append({
                                "tool_call_id": func_name,
                                "tool_name": func_name,
                                "arguments": func_args,
                                "result": result,
                                "latency_ms": result.get("latency_ms", 0),
                            })
                            tool_result_parts.append(types.Part.from_function_response(
                                name=func_name,
                                response={"output": result.get("output", "")},
                            ))
                        else:
                            tool_result_parts.append(types.Part.from_function_response(
                                name=func_name, response={"output": ""},
                            ))

                    contents.append(types.Content(role="tool", parts=tool_result_parts))
                    llm_calls.append(llm_call)
                    continue
                else:
                    assistant_text = content_text
                    llm_calls.append(llm_call)
                    contents.append(types.Content(
                        role="model", parts=[types.Part.from_text(text=assistant_text or "")],
                    ))
                    break

            end_time = time.time()

            if not self.quiet:
                print(f"  assistant: {assistant_text[:80]}...")
                print(f"  tools: {len(tool_executions)} | latency: {(end_time - start_time)*1000:.0f}ms")

            step = TraceStep(
                step_id=step_count,
                timestamp=chunk.timestamp,
                input_chunk={
                    "role": "user",
                    "content": user_text,
                    "timestamp": chunk.timestamp,
                    "metadata": chunk.metadata or {},
                    "audio_size_bytes": 0,
                },
                assistant_response=assistant_text,
                llm_calls=llm_calls,
                tool_executions=tool_executions,
                total_latency_ms=(end_time - start_time) * 1000,
            )
            trace.add_step(step)

        # Serialize contents (types.Content is not natively JSON serializable) — simplified form.
        try:
            trace.conversation_history = [
                {"role": c.role, "parts": [
                    ({"text": p.text} if p.text else (
                        {"function_call": {"name": p.function_call.name, "args": dict(p.function_call.args or {})}}
                        if p.function_call else
                        ({"function_response": {"name": p.function_response.name, "response": dict(p.function_response.response or {})}} if p.function_response else {})
                    ))
                    for p in (c.parts or [])
                ]}
                for c in contents
            ]
        except Exception:
            trace.conversation_history = []

        trace.finalize()

        if not self.quiet:
            print(f"\nDone: {trace.summary['total_steps']} steps, "
                  f"{trace.summary['total_tool_calls']} tool calls")

        return trace
