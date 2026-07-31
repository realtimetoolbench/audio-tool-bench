"""
Chat Completions API runner — standard multi-turn dialogue + function calling.
Used as a baseline for text-only models such as GPT-5.2.
"""
import json
import time
import datetime
from typing import Optional, Dict, Any, List

from openai import OpenAI

from eval.data.task import Task, MessageRole
from eval.data.trace import Trace, TraceStep


class ChatCompletionsRunner:
    """Chat Completions API multi-turn dialogue runner."""

    def __init__(
        self, api_key: str, model: str = "gpt-5.2",
        tool_executor=None, quiet: bool = False,
    ):
        # Use US OpenAI endpoint (required for non-preview models)
        self.client = OpenAI(api_key=api_key, base_url="https://us.api.openai.com/v1")
        self.model = model
        self.tool_executor = tool_executor
        self.quiet = quiet

    def run_task(
        self, task: Task, task_path: str,
        system_prompt: Optional[str] = None,
        max_tool_rounds: int = 5,
    ) -> Trace:
        # Read task JSON to fetch context_turns / info_complete_turn.
        with open(task_path, 'r') as f:
            task_data = json.load(f)

        context_turns = task_data.get("context_turns", [])
        info_complete_turn = task_data.get("info_complete_turn")

        if not self.quiet:
            print(f"\n{'='*60}")
            print(f"Chat API: {task.name} | model: {self.model}")
            print(f"{'='*60}")

        # Build the system prompt.
        today = datetime.date.today()
        weekday_name = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"][today.weekday()]
        date_ctx = f"Today is {today.strftime('%B %d, %Y')} ({weekday_name}).\n\n"
        sys_msg = date_ctx + (system_prompt or "You are a helpful assistant.")

        # Accumulated messages.
        messages: List[Dict[str, Any]] = [{"role": "system", "content": sys_msg}]

        # Inject context_turns.
        for turn in context_turns:
            messages.append({"role": turn.get("role", "user"), "content": turn.get("content", "")})

        # Tools (Chat API format, pulled directly from the tool executor).
        tools = self.tool_executor.get_tools_for_openai() if self.tool_executor else []

        trace = Trace(
            task_name=task.name,
            start_time=datetime.datetime.now().isoformat(),
            metadata={
                **task.metadata,
                "mode": "chat_completions",
                "provider": "openai-chat",
                "realtime_model": self.model,
                "input_mode": "text",
            },
        )

        # Send user messages turn by turn.
        step_count = 0
        user_chunks = [c for c in task.chunks if c.role == MessageRole.USER]

        for chunk in user_chunks:
            step_count += 1
            user_text = chunk.content
            messages.append({"role": "user", "content": user_text})

            if not self.quiet:
                print(f"\n[Step {step_count}] user: {user_text[:80]}...")

            # Multi-round tool-call loop.
            start_time = time.time()
            llm_calls = []
            tool_executions = []
            assistant_text = ""

            for tool_round in range(max_tool_rounds + 1):
                kwargs: Dict[str, Any] = dict(
                    model=self.model, messages=messages,
                )
                if tools:
                    kwargs["tools"] = tools
                    kwargs["tool_choice"] = "auto"

                resp = self.client.chat.completions.create(**kwargs)
                choice = resp.choices[0]
                msg = choice.message

                llm_call: Dict[str, Any] = {
                    "round": tool_round + 1,
                    "finish_reason": choice.finish_reason,
                    "content": msg.content or "",
                    "tool_calls": None,
                }

                if msg.tool_calls:
                    llm_call["tool_calls"] = []
                    # Append the assistant message (with tool_calls) to messages.
                    messages.append(msg.model_dump())

                    for tc in msg.tool_calls:
                        func_name = tc.function.name
                        try:
                            func_args = json.loads(tc.function.arguments)
                        except Exception:
                            func_args = {}

                        if not self.quiet:
                            print(f"  tool: {func_name}({func_args})")

                        llm_call["tool_calls"].append({
                            "id": tc.id,
                            "name": func_name,
                            "arguments": func_args,
                        })

                        # Execute the tool.
                        if self.tool_executor:
                            result = self.tool_executor.execute_tool(func_name, func_args)
                            tool_executions.append({
                                "tool_call_id": tc.id,
                                "tool_name": func_name,
                                "arguments": func_args,
                                "result": result,
                                "latency_ms": result.get("latency_ms", 0),
                            })
                            # Append the tool result to messages.
                            messages.append({
                                "role": "tool",
                                "tool_call_id": tc.id,
                                "content": result.get("output", ""),
                            })

                    llm_calls.append(llm_call)
                    # Continue to the next round (let the model consume the tool result).
                    continue
                else:
                    # No tool call: final reply.
                    assistant_text = msg.content or ""
                    llm_calls.append(llm_call)
                    messages.append({"role": "assistant", "content": assistant_text})
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

        trace.conversation_history = messages
        trace.finalize()

        if not self.quiet:
            print(f"\nDone: {trace.summary['total_steps']} steps, "
                  f"{trace.summary['total_tool_calls']} tool calls")

        return trace
