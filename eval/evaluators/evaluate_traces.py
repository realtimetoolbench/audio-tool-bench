#!/usr/bin/env python3
"""
Audio Tool Bench - unified evaluator.

Passing criteria:
1. Correct tool calls (right tool + right parameters).
2. Sensible timing (no premature calls + no unnecessary follow-up questions).
3. No hallucination (do not invent facts that are not in tool results).

A trace only passes when all three criteria hold simultaneously.
"""

import json
import os
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Any

# Reuse 6-class voice-error classifier from evaluate_reactive (single source of truth).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_reactive import _classify_voice_error  # noqa: E402

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False

# Test-case root directory (relative to the script location)
TASK_ROOT = Path(__file__).parent.parent / "data" / "tasks"


def find_task_file(task_id: str) -> Optional[Path]:
    """Recursively search data/tasks/ for a JSON file with the matching task_id."""
    if not TASK_ROOT.exists():
        return None
    for f in TASK_ROOT.rglob("*.json"):
        try:
            with open(f, encoding="utf-8") as fp:
                data = json.load(fp)
            # Support both task_id and scenario_id for backwards compatibility
            if data.get("task_id") == task_id or data.get("scenario_id") == task_id:
                return f
        except Exception:
            continue
    return None


def find_last_actual_tool_call(actual_calls: List[Dict], tool_name: str) -> Optional[Dict]:
    """Find the last actual call matching the tool name (last-wins)."""
    last_call = None
    for call in actual_calls:
        if call.get("tool_name") == tool_name:
            last_call = call
    return last_call


# ── Parameter type buckets ──
_DIGIT_STRING_PARAMS = {"phone", "account_number", "tracking_number",
                        "id_number", "license_plate"}
_TIME_PARAMS = {"time_slot", "time", "departure_time", "arrival_time", "showtime"}
_ITEMS_PARAMS = {"items"}


def _normalize_items(val: str) -> str:
    """Normalize a food order: split → strip → sort → lowercase-join."""
    parts = re.split(r'\s+and\s+|,\s*', val.strip())
    return ",".join(sorted(p.strip().lower() for p in parts if p.strip()))


def match_param(tool_name: str, param_name: str, expected: Any, actual: Any) -> bool:
    """
    Unified parameter matching — tolerate format differences only, never content errors.

    Rules:
    - Phone / numeric strings: strip non-digits and require exact match (tolerates dashes / spaces).
    - Times: exact match plus prefix match (09:00 == 09:00-12:00).
    - items: normalize the separator and then match ("A and B" == "A, B").
    - search-tool city / origin / destination: case-insensitive exact match.
    - Everything else: exact match (case-insensitive, stripped).
    """
    if expected is None or actual is None:
        return expected == actual

    expected_str = str(expected).strip()
    actual_str = str(actual).strip()

    # Phone / numeric strings: strip non-digits, then exact match
    if param_name in _DIGIT_STRING_PARAMS:
        e_digits = re.sub(r'[^0-9]', '', expected_str)
        a_digits = re.sub(r'[^0-9]', '', actual_str)
        if e_digits and a_digits:
            return e_digits == a_digits
        return expected_str.lower() == actual_str.lower()

    # Times: exact match plus prefix match
    if param_name in _TIME_PARAMS:
        e = expected_str.lower()
        a = actual_str.lower()
        return e == a or a.startswith(e)

    # items: normalize the separator, then match
    if param_name in _ITEMS_PARAMS:
        return _normalize_items(expected_str) == _normalize_items(actual_str)

    # Default: exact match (case-insensitive, stripped)
    return expected_str.lower() == actual_str.lower()


def check_all_params(expected_tools: List[Dict], actual_calls: List[Dict]) -> Dict:
    """
    Check that every expected_tools parameter value matches.

    Handles repeated calls to the same tool:
    - Last call wins (matches the "user changes their mind" scenario).

    Returns:
      - passed=True: every parameter matches.
      - passed=False: at least one parameter did not match; details are included.
    """
    mismatches = []

    for exp_tool in expected_tools:
        tool_name = exp_tool["tool"]
        expected_params = exp_tool.get("params", {})

        # Find the last call to the same-named tool
        actual = find_last_actual_tool_call(actual_calls, tool_name)
        if not actual:
            # Missing tools are caught by check_expected_tools — skip here
            continue

        actual_args = actual.get("arguments", {})

        for param_name, expected_val in expected_params.items():
            if expected_val is None:
                continue
            actual_val = actual_args.get(param_name)
            if not match_param(tool_name, param_name, expected_val, actual_val):
                mismatches.append({
                    "tool": tool_name,
                    "param": param_name,
                    "expected": expected_val,
                    "actual": actual_val,
                })

    if mismatches:
        details = "; ".join([
            f"{m['tool']}.{m['param']}: expected '{m['expected']}', got '{m['actual']}'"
            for m in mismatches
        ])
        return {
            "passed": False,
            "reason": "param_mismatch",
            "details": f"Parameter mismatch: {details}",
            "mismatches": mismatches,
        }

    return {"passed": True}


def classify_model_behavior(trace: Dict) -> str:
    """
    Classify the model's overall behaviour (core scoring path, no LLM required).

    Returns: "immediate_act" | "no_action"
    (offer_to_act / info_gathering require an LLM and are supplied by the diagnostic analysis.)
    """
    for step in trace.get("steps", []):
        if step.get("tool_executions"):
            return "immediate_act"
    return "no_action"


def classify_per_step_behavior(trace: Dict) -> List[Dict]:
    """
    Per-step behaviour classification.

    For each step:
    - Has tool_executions → immediate_act.
    - No tool_executions → collect and batch-classify with an LLM.

    Returns: [{"step_id": int, "behavior": str, "response": str}, ...]
    """
    steps = trace.get("steps", [])
    results = []
    needs_classification = []  # (index_in_results, step_id, response)

    for step in steps:
        step_id = step.get("step_id", 0)
        response = step.get("assistant_response", "")

        if step.get("tool_executions"):
            tools = [te["tool_name"] for te in step["tool_executions"]]
            results.append({"step_id": step_id, "behavior": "immediate_act",
                           "response": response, "tools": tools})
        else:
            results.append({"step_id": step_id, "behavior": "no_action",
                           "response": response, "tools": []})
            if response.strip():
                needs_classification.append((len(results) - 1, step_id, response))

    if not needs_classification:
        return results

    # Batch LLM classification
    classifications = _batch_classify_responses(needs_classification)
    for idx, behavior in classifications:
        results[idx]["behavior"] = behavior

    return results


def _batch_classify_responses(items: List[tuple]) -> List[tuple]:
    """
    Batch-classify steps without tool calls in a single LLM call.

    items: [(index, step_id, response), ...]
    Returns: [(index, behavior), ...]
    """
    if not items:
        return []

    if not HAS_OPENAI:
        raise RuntimeError("Diagnostic analysis requires the openai library — run pip install openai")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("Diagnostic analysis requires the OPENAI_API_KEY environment variable")

    # Build the batch prompt
    lines = []
    for _, step_id, response in items:
        lines.append(f"Turn {step_id}: {response}")
    all_text = "\n".join(lines)

    return _llm_batch_classify(items, all_text, api_key)


def _llm_batch_classify(items: List[tuple], all_text: str, api_key: str) -> List[tuple]:
    """Batch-classify with a single LLM call."""
    step_ids = [step_id for _, step_id, _ in items]
    step_list = ", ".join(str(s) for s in step_ids)

    prompt = f"""This assistant has access to tools (e.g., search_hotels, book_flight, check_ride_status). Classify each turn's behavior into exactly ONE category based on whether it relates to tool actions:

1. "offer_to_act" — Offers to perform a tool action (e.g., "Want me to look that up?", "I can search for flights", "Shall I book that for you?")
2. "info_gathering" — Asks for specific information needed to call a tool (e.g., "What city do you want to search?", "When is your check-in date?", "How many guests?")
3. "no_action" — Everything else: chatting, acknowledging, responding to conversation, discussing past events, or any response that is NOT about performing a tool action or collecting tool parameters

IMPORTANT: If the assistant is just having a normal conversation (e.g., "That sounds like a great trip!", "I see, that must have been nice"), that is "no_action" even if the conversation topic relates to travel/hotels/etc.

Assistant responses:
{all_text}

For each turn ({step_list}), output exactly one line in format: TURN <id>: <category>
Example:
TURN 1: no_action
TURN 3: offer_to_act"""

    client = OpenAI(api_key=api_key, base_url="https://us.api.openai.com/v1")
    response = client.chat.completions.create(
        model="gpt-5.2-chat-latest",
        messages=[{"role": "user", "content": prompt}],
        timeout=15,
    )
    answer = response.choices[0].message.content.strip()

    # Parse the result
    parsed = {}
    for line in answer.split("\n"):
        m = re.match(r"TURN\s+(\d+):\s*(\w+)", line.strip(), re.IGNORECASE)
        if m:
            turn_id = int(m.group(1))
            behavior = m.group(2).lower()
            if behavior in ("offer_to_act", "info_gathering", "no_action"):
                parsed[turn_id] = behavior

    # Map back to items; anything missing is an error
    result = []
    for idx, step_id, resp in items:
        if step_id in parsed:
            result.append((idx, parsed[step_id]))
        else:
            raise RuntimeError(f"LLM did not return a classification for Turn {step_id}")
    return result


def check_expected_tools(trace: Dict, task_data: Dict) -> Dict:
    """
    Compare expected_tools against actual tool calls (intersection match + blacklist).

    - expected_tools is empty (cancellation) → must have no actual tool calls to pass.
    - expected_tools non-empty → actual calls must include every expected tool (extras allowed).
    - forbidden_tools non-empty → actual calls must not include any forbidden tool.

    Strategy:
    1. Check that every expected tool was called (missing → fail).
    2. Check that no forbidden tool was called (called → fail).
    3. Allow extra tool calls (neither expected nor forbidden).
    """
    expected = task_data.get("expected_tools", [])
    expected_names = {item["tool"] for item in expected}
    # forbidden_tools may live at the top level or under metadata
    forbidden_names = set(
        task_data.get("forbidden_tools", [])
        or task_data.get("metadata", {}).get("forbidden_tools", [])
    )

    # Collect actually-called tool names (skip dangling executions: tool ran but result never returned to the model)
    actual_names = set()
    for step in trace.get("steps", []):
        for tool_exec in step.get("tool_executions", []):
            if not tool_exec.get("dangling"):
                actual_names.add(tool_exec["tool_name"])

    # Collect actual tool-call details (for parameter checking; same dangling skip)
    actual_calls = []
    for step in trace.get("steps", []):
        for tool_exec in step.get("tool_executions", []):
            if not tool_exec.get("dangling"):
                actual_calls.append(tool_exec)

    # Passive (non-action) tools — info extraction only, no side effects, don't count as unexpected_call
    PASSIVE_TOOLS = {"extract_info"}

    # Determine the model's behaviour class
    behavior = classify_model_behavior(trace)

    # Read intent_strength (proactive tasks carry an intent field)
    intent = task_data.get("intent", {})
    intent_strength = intent.get("strength", "")
    # Absence of an intent field means reactive (explicit)
    scenario_type = task_data.get("scenario_type", "reactive")

    if not expected_names:
        # cancellation / negative scenario: no action tool calls expected
        action_calls = actual_names - PASSIVE_TOOLS
        if not action_calls:
            # No tool calls, but possibly offer_to_act (weak scenario must not offer)
            if behavior == "offer_to_act" and intent_strength == "weak":
                return {"passed": False, "reason": "unexpected_offer",
                        "behavior": behavior,
                        "details": f"Negative scenario should not offer to act (reply contains an action proposal)"}
            return {"passed": True, "reason": "correct_no_call",
                    "behavior": behavior,
                    "details": "Correct: no tool calls (cancellation)"}
        else:
            return {"passed": False, "reason": "unexpected_call",
                    "behavior": "immediate_act",
                    "details": f"Expected no tool calls, but called: {action_calls}"}
    else:
        # expected_tools non-empty: model is expected to act

        # Check whether any forbidden tool was called
        forbidden_called = actual_names & forbidden_names
        if forbidden_called:
            return {"passed": False, "reason": "forbidden_tool_called",
                    "behavior": behavior,
                    "details": f"Called forbidden tool: {forbidden_called} (expected: {expected_names}, actual: {actual_names}, forbidden: {forbidden_names})"}

        # Model didn't call tools but did offer_to_act → decide by intent_strength
        if behavior == "offer_to_act" and not actual_names:
            if intent_strength in ("strong", "medium"):
                return {"passed": True, "reason": "offer_to_act",
                        "behavior": "offer_to_act",
                        "details": f"Model proactively offered to help ({intent_strength} scenario; acceptable)"}
            else:
                # reactive or other scenario: user already asked explicitly, so offering instead is wrong
                return {"passed": False, "reason": "offer_instead_of_act",
                        "behavior": "offer_to_act",
                        "details": f"Model offered instead of acting ({scenario_type} scenario; unacceptable)"}

        # Check whether all expected tools are present
        missing = expected_names - actual_names
        if not missing:
            # All expected tools were called — continue to parameter checking
            param_check = check_all_params(expected, actual_calls)
            if not param_check["passed"]:
                param_check["behavior"] = "immediate_act"
                return param_check

            extra = actual_names - expected_names - forbidden_names
            if extra:
                return {"passed": True, "reason": "correct_with_extra",
                        "behavior": "immediate_act",
                        "details": f"All expected tools present: {expected_names}; extras called: {extra}"}
            else:
                return {"passed": True, "reason": "correct",
                        "behavior": "immediate_act",
                        "details": f"Exact match for expected tools: {expected_names}"}
        else:
            # Expected tool missing
            return {"passed": False, "reason": "missing_expected_tool",
                    "behavior": behavior,
                    "details": f"Expected: {expected_names}, actual: {actual_names}, missing: {missing}"}


def check_interruption_semantics(trace: Dict, task_data: Dict) -> Dict:
    """Semantic check specific to v3.1 tool-phase interruptions.

    Verifies by interruption_type:
    - tool_cancel: a dangling call exists (the runner intercepted successfully).
    - tool_correction: after the interruption the model re-invoked the dangling tool with corrected_params.
    - priority_*: the priority_tool runs before the dangling tool resumes.
    - priority_late/early_return: the dangling tool must not be redundantly re-called.
    """
    int_type = task_data.get("interruption_type", "")
    meta = task_data.get("metadata", {})

    # Only apply this check to v3.1 tool-phase types
    if int_type not in ("tool_cancel", "tool_correction",
                        "priority_no_return", "priority_late_return", "priority_early_return"):
        return {"passed": True, "reason": "not_tool_phase"}

    dangling_tool = meta.get("dangling_call")
    if not dangling_tool:
        return {"passed": True, "reason": "no_dangling_call_metadata"}

    # Collect every tool_execution, sorted by step
    all_execs = []
    for step in trace.get("steps", []):
        for te in step.get("tool_executions", []):
            all_execs.append({"step": step["step_id"], **te})

    # Dangling markers can come from three places:
    # 1. dangling=True in tool_executions (legacy path).
    # 2. dangling=True in llm_calls[].tool_calls[] (no_return mode does not execute; logged only in llm_calls).
    # 3. dangling_return field in tool_executions (early/late_return modes did execute, but the call is dangling).
    dangling_in_llm = False
    for step in trace.get("steps", []):
        for lc in step.get("llm_calls", []):
            for tc in (lc.get("tool_calls") or []):
                if tc.get("dangling") and tc.get("name") == dangling_tool:
                    dangling_in_llm = True
    dangling_in_execs = [e for e in all_execs if e.get("dangling") or e.get("dangling_return")]
    dangling_found = dangling_in_llm or bool(dangling_in_execs)

    # "Resumed call" = a non-dangling call to dangling_tool.
    # Exclude: execs with dangling=True and execs with a dangling_return field (those are the dangling execution itself).
    resumed_execs = [
        e for e in all_execs
        if e["tool_name"] == dangling_tool
        and not e.get("dangling")
        and not e.get("dangling_return")
    ]

    if int_type == "tool_cancel":
        if not dangling_found:
            return {"passed": False, "reason": "dangling_not_intercepted",
                    "details": f"Dangling tool {dangling_tool} was not intercepted by the runner"}
        return {"passed": True, "reason": "dangling_intercepted"}

    elif int_type == "tool_correction":
        if not dangling_found:
            return {"passed": False, "reason": "dangling_not_intercepted",
                    "details": f"Dangling tool {dangling_tool} was not intercepted by the runner"}
        # Verify the model re-invoked the dangling tool
        if not resumed_execs:
            return {"passed": False, "reason": "correction_not_recalled",
                    "details": f"Model did not re-invoke {dangling_tool} after the interruption"}
        # Verify the re-invocation matches corrected_params
        corrected = meta.get("corrected_params", {})
        if corrected:
            last_resume = resumed_execs[-1]
            args = last_resume.get("arguments", {})
            for key_str, expected_val in corrected.items():
                param_name = key_str.split(".")[-1] if "." in key_str else key_str
                actual_val = str(args.get(param_name, "")).lower()
                if actual_val != str(expected_val).lower():
                    return {"passed": False, "reason": "correction_wrong_param",
                            "details": f"Re-invoked {dangling_tool} with {param_name}={actual_val}; expected {expected_val}"}
        return {"passed": True, "reason": "correction_recalled_correctly"}

    elif int_type.startswith("priority_"):
        priority_tool = meta.get("priority_tool")
        if not priority_tool:
            return {"passed": True, "reason": "no_priority_tool_metadata"}

        # Find executions of priority_tool
        priority_execs = [
            e for e in all_execs
            if e["tool_name"] == priority_tool
            and not e.get("dangling")
            and not e.get("dangling_return")
        ]
        if not priority_execs:
            return {"passed": False, "reason": "priority_tool_not_called",
                    "details": f"Priority tool {priority_tool} was not called"}

        # Verify priority_tool runs before dangling_tool resumes
        if resumed_execs:
            priority_step = priority_execs[0]["step"]
            resumed_step = resumed_execs[0]["step"]
            if priority_step > resumed_step:
                return {"passed": False, "reason": "priority_order_wrong",
                        "details": f"{priority_tool} (step {priority_step}) should run before {dangling_tool} resumes (step {resumed_step})"}

        return {"passed": True, "reason": "priority_order_correct"}

    return {"passed": True}


def check_call_timing(trace: Dict, task_data: Dict) -> Dict:
    """
    Check tool-call timing: each tool must be called only after its required information is complete.

    info_complete_turn format:
    - Legacy (int): a single global "information complete" turn.
    - New (dict): {"search_hotels": 2, "book_hotel": 6, ...} per-tool turn.

    For every call of every tool, verify step_id >= that tool's info_complete_turn.

    Interruption tasks: ignore tool calls before the interruption turn (calling with the old
    intent / wrong params before the interruption is expected behaviour).
    """
    info_complete = task_data.get("info_complete_turn")
    if info_complete is None:
        return {"passed": True, "details": "No info_complete_turn — skipped"}

    # Legacy compatibility: int → applied to every action tool
    if isinstance(info_complete, int):
        info_complete_dict = {}
        for et in task_data.get("expected_tools", []):
            info_complete_dict[et["tool"]] = info_complete
    else:
        info_complete_dict = info_complete

    # Interruption tasks: locate the interruption step number and skip earlier calls
    interrupt_step = 0  # default: don't skip
    if task_data.get("scenario_type") == "interruption":
        for i, t in enumerate(task_data.get("transcript", [])):
            if t.get("metadata", {}).get("is_interruption"):
                interrupt_step = i + 1  # 1-indexed step number
                break

    # Collect every tool call together with its step_id
    premature_calls = []
    for step in trace.get("steps", []):
        step_id = step["step_id"]
        # interruption: skip calls before the interruption turn
        if step_id < interrupt_step:
            continue
        for te in step.get("tool_executions", []):
            if te.get("dangling"):
                continue
            tool_name = te.get("tool_name", "")
            tool_complete = info_complete_dict.get(tool_name)
            if tool_complete is not None and step_id < tool_complete:
                premature_calls.append({
                    "tool": tool_name,
                    "step": step_id,
                    "info_complete": tool_complete,
                })

    if premature_calls:
        details = "; ".join([
            f"{p['tool']} called at step {p['step']}, but its info is not complete until turn {p['info_complete']}"
            for p in premature_calls
        ])
        return {
            "passed": False,
            "reason": "premature_call",
            "details": details,
            "premature_calls": premature_calls,
        }

    return {"passed": True, "details": "All tool calls had sensible timing"}


def check_extra_turns(trace: Dict, task_data: Dict) -> Dict:
    """
    Detect unnecessary follow-up turns: how many extra turns the model spent before calling
    a tool, after the relevant information was already complete.

    Not a failure condition — purely an efficiency metric.
    extra_turns = actual_call_step - info_complete_turn (per tool)

    Returns:
      - total_extra_turns: sum of extra_turns across all tools.
      - per_tool: per-tool details.
    """
    info_complete = task_data.get("info_complete_turn")
    if info_complete is None:
        return {"total_extra_turns": 0, "per_tool": {}, "details": "no info_complete_turn"}

    if isinstance(info_complete, int):
        info_complete_dict = {}
        for et in task_data.get("expected_tools", []):
            info_complete_dict[et["tool"]] = info_complete
    else:
        info_complete_dict = info_complete

    # Find the first step each tool is called (skip dangling executions)
    first_call_step = {}
    for step in trace.get("steps", []):
        for te in step.get("tool_executions", []):
            if te.get("dangling"):
                continue
            tool_name = te.get("tool_name", "")
            if tool_name not in first_call_step:
                first_call_step[tool_name] = step["step_id"]

    per_tool = {}
    total_extra = 0
    for tool_name, complete_turn in info_complete_dict.items():
        call_step = first_call_step.get(tool_name)
        if call_step is None:
            per_tool[tool_name] = {"info_complete": complete_turn, "call_step": None, "extra_turns": None}
            continue
        extra = max(0, call_step - complete_turn)
        total_extra += extra
        per_tool[tool_name] = {"info_complete": complete_turn, "call_step": call_step, "extra_turns": extra}

    details_parts = []
    for tool, info in per_tool.items():
        if info["extra_turns"] is not None and info["extra_turns"] > 0:
            details_parts.append(f"{tool}: +{info['extra_turns']} turns (info@{info['info_complete']}, call@{info['call_step']})")

    details = "; ".join(details_parts) if details_parts else "No unnecessary follow-up"

    return {
        "total_extra_turns": total_extra,
        "per_tool": per_tool,
        "details": details,
    }


def check_hallucination(trace: Dict) -> Dict:
    """
    Hallucination check: did the model fabricate facts that the tool results don't support?

    For every step with tool_executions, check that every factual claim in assistant_response
    can be backed by something in tool_result.

    Requires the OpenAI API (OPENAI_API_KEY); skipped if missing.

    Returns:
      - passed: True/False
      - hallucinations: [{step, tool, claim, detail}, ...]
    """
    if not HAS_OPENAI:
        return {"skipped": True, "details": "skipped: openai not installed"}

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return {"skipped": True, "details": "skipped: OPENAI_API_KEY not set"}

    # Collect user conversation context
    user_messages = []
    for step in trace.get("steps", []):
        user_text = step.get("user_text", "")
        if user_text:
            user_messages.append(f"Turn {step['step_id']}: {user_text}")

    # Collect every (tool_result, assistant_response) pair that needs checking
    check_items = []
    for step in trace.get("steps", []):
        tool_execs = step.get("tool_executions", [])
        response = step.get("assistant_response", "")
        if not tool_execs or not response:
            continue

        # Merge all tool results and call arguments for this step
        tool_results = []
        for te in tool_execs:
            tool_name = te.get("tool_name", "")
            result = te.get("result", {})
            arguments = te.get("arguments", {})
            tool_results.append({
                "tool": tool_name,
                "arguments": arguments,
                "output": result.get("output", ""),
                "success": result.get("success", True),
            })

        check_items.append({
            "step_id": step["step_id"],
            "tool_results": tool_results,
            "assistant_response": response,
        })

    if not check_items:
        return {"passed": True, "details": "No replies after tool calls"}

    # Build the prompt that checks all steps in one go
    user_context = "\n".join(user_messages) if user_messages else "(no user messages)"

    steps_text = []
    for item in check_items:
        tools_info = []
        for tr in item["tool_results"]:
            args_str = json.dumps(tr["arguments"], ensure_ascii=False) if tr["arguments"] else "(none)"
            tools_info.append(
                f"  Tool: {tr['tool']}\n  Arguments: {args_str}\n"
                f"  Success: {tr['success']}\n  Output:\n{tr['output']}"
            )
        tools_str = "\n".join(tools_info)
        steps_text.append(
            f"--- Step {item['step_id']} ---\n"
            f"Tool Calls & Results:\n{tools_str}\n\n"
            f"Assistant Response:\n{item['assistant_response']}"
        )

    all_steps = "\n\n".join(steps_text)

    prompt = f"""You are a factual accuracy judge. For each step below, check if the assistant's response contains any factual claims that are NOT supported by the available information.

Available information sources (NOT hallucination):
1. Tool results (output)
2. Tool call arguments (the assistant's own input to the tool)
3. User conversation context (what the user said earlier)

Focus ONLY on factual claims about:
- Prices, ratings, dates, times, quantities
- Names of hotels/restaurants/flights/etc.
- Booking status, IDs, confirmation details
- Locations, addresses

Ignore (NOT hallucination):
- Politeness, filler phrases
- Reasonable inferences from tool results
- Information the assistant repeats from user conversation or its own tool call arguments
- Vague statements without specific factual claims

=== User Conversation Context ===
{user_context}

=== Steps to Judge ===
{all_steps}

For each step, output ONE line:
- "STEP X: PASS" if no hallucination
- "STEP X: FAIL | <specific hallucinated claim> | <why it's not supported by ANY source>"

Output your judgment now (one line per step):"""

    try:
        client = OpenAI(api_key=api_key, base_url="https://us.api.openai.com/v1")
        response = client.chat.completions.create(
            model="gpt-5.2-chat-latest",
            messages=[{"role": "user", "content": prompt}],
            timeout=30,
        )
        judge_output = response.choices[0].message.content.strip()
    except Exception as e:
        return {"skipped": True, "details": f"skipped: LLM judge call failed ({e})"}

    # Parse the judge output
    hallucinations = []
    for line in judge_output.split("\n"):
        line = line.strip()
        if not line:
            continue
        if "FAIL" in line.upper():
            parts = line.split("|", 2)
            step_part = parts[0].strip()
            claim = parts[1].strip() if len(parts) > 1 else "unknown"
            detail = parts[2].strip() if len(parts) > 2 else ""
            step_match = re.search(r"STEP\s+(\d+)", step_part, re.IGNORECASE)
            step_id = int(step_match.group(1)) if step_match else -1
            hallucinations.append({
                "step": step_id,
                "claim": claim,
                "detail": detail,
            })

    if hallucinations:
        details = "; ".join([
            f"Step {h['step']}: {h['claim']}"
            for h in hallucinations
        ])
        return {
            "passed": False,
            "reason": "hallucination",
            "details": f"Hallucination: {details}",
            "hallucinations": hallucinations,
            "judge_output": judge_output,
        }

    return {"passed": True, "details": "No hallucination", "judge_output": judge_output}


def diagnose_per_turn(trace: Dict, task_data: Dict) -> Dict:
    """
    Per-turn diagnostic analysis: classify each turn's behaviour and judge whether it was reasonable.

    Does not affect pass/fail or behavior_score — purely diagnostic output.

    Returns:
      - turns: [{step_id, behavior, reasonable, reason}, ...]
      - summary: {behavior_distribution, unreasonable_count, ...}
    """
    expected_tools = task_data.get("expected_tools", [])

    per_step = classify_per_step_behavior(trace)

    # Fetch info_complete_turn
    info_complete = task_data.get("info_complete_turn")
    if isinstance(info_complete, int):
        info_complete_dict = {et["tool"]: info_complete for et in expected_tools}
    elif isinstance(info_complete, dict):
        info_complete_dict = info_complete
    else:
        info_complete_dict = {}

    # max info_complete_turn = the moment information for every tool is complete.
    # weak/negative tasks have no expected_tools → info is never "ready".
    max_complete = max(info_complete_dict.values()) if info_complete_dict else 999

    intent = task_data.get("intent", {})
    intent_strength = intent.get("strength", "")

    turns = []
    for step_info in per_step:
        step_id = step_info["step_id"]
        behavior = step_info["behavior"]
        info_ready = step_id >= max_complete if max_complete > 0 else True

        # Judge reasonableness (weak is short-circuited earlier; here we handle tasks with expected_tools)
        # weak task: only "calling a tool" counts as unreasonable.
        if intent_strength == "weak":
            if behavior == "immediate_act":
                reasonable, reason = False, "unnecessary_action"
            else:
                reasonable, reason = True, "correct_no_action"
        elif not info_ready:
            # Info not yet ready
            if behavior == "immediate_act":
                reasonable, reason = False, "premature_call"
            elif behavior == "offer_to_act":
                reasonable, reason = True, "early_offer_ok"
            elif behavior == "info_gathering":
                reasonable, reason = True, "reasonable_gathering"
            else:
                reasonable, reason = True, "waiting"
        else:
            # Info is ready
            if behavior == "immediate_act":
                reasonable, reason = True, "correct_timing"
            elif behavior == "offer_to_act":
                reasonable = intent_strength in ("strong", "medium")
                reason = "offer_ok" if reasonable else "offer_weak"
            elif behavior == "info_gathering":
                reasonable, reason = False, "unnecessary_gathering"
            else:
                # no_action when info is ready and expected_tools exist
                reasonable, reason = False, "delayed_action"

        turns.append({
            "step_id": step_id,
            "behavior": behavior,
            "info_ready": info_ready,
            "reasonable": reasonable,
            "reason": reason,
            "tools": step_info.get("tools", []),
        })

    # Aggregate
    behavior_dist = {}
    unreasonable_count = 0
    for t in turns:
        b = t["behavior"]
        behavior_dist[b] = behavior_dist.get(b, 0) + 1
        if not t["reasonable"]:
            unreasonable_count += 1

    return {
        "turns": turns,
        "summary": {
            "total_turns": len(turns),
            "behavior_distribution": behavior_dist,
            "unreasonable_count": unreasonable_count,
            "unreasonable_rate": unreasonable_count / len(turns) if turns else 0,
        },
    }


def compute_behavior_score(trace: Dict, task_data: Dict) -> Dict:
    """
    Per-tool behavior_score.

    For each expected tool, answer three questions:
    1. Did the model call it? Not called → 0.
    2. Timing: was it called before or after info_complete_turn? Before (premature) → 0.
    3. Are the parameters correct? Wrong → 0; correct → 1.

    behavior_score = mean of the scores across expected tools (range 0~1).
    """
    expected_tools = task_data.get("expected_tools", [])
    if not expected_tools:
        # weak/negative tasks have no expected_tools — don't compute behavior_score
        return {"score": None, "per_tool": {}, "details": "no expected_tools"}

    # Fetch per-tool info_complete_turn
    info_complete = task_data.get("info_complete_turn")
    if isinstance(info_complete, int):
        info_complete_dict = {et["tool"]: info_complete for et in expected_tools}
    elif isinstance(info_complete, dict):
        info_complete_dict = info_complete
    else:
        info_complete_dict = {}

    # Collect actual tool calls together with their step_id (skip dangling executions)
    actual_calls_by_tool = {}  # tool_name -> [(step_id, call_data)]
    for step in trace.get("steps", []):
        for te in step.get("tool_executions", []):
            if te.get("dangling"):
                continue
            tool_name = te.get("tool_name", "")
            actual_calls_by_tool.setdefault(tool_name, []).append(
                (step["step_id"], te)
            )

    per_tool = {}
    for exp_tool in expected_tools:
        tool_name = exp_tool["tool"]
        expected_params = exp_tool.get("params", {})

        # Q1: did the model call it?
        calls = actual_calls_by_tool.get(tool_name, [])
        if not calls:
            per_tool[tool_name] = {"score": 0, "reason": "not_called"}
            continue

        # Use the last call as the reference
        last_step_id, last_call = calls[-1]

        # Q2: timing
        tool_complete = info_complete_dict.get(tool_name)
        if tool_complete is not None and last_step_id < tool_complete:
            per_tool[tool_name] = {"score": 0, "reason": "premature_call",
                                   "call_step": last_step_id, "info_complete": tool_complete}
            continue

        # Q3: are the parameters correct?
        actual_args = last_call.get("arguments", {})
        param_ok = True
        bad_param = None
        for param_name, expected_val in expected_params.items():
            if expected_val is None:
                continue
            actual_val = actual_args.get(param_name)
            if not match_param(tool_name, param_name, expected_val, actual_val):
                param_ok = False
                bad_param = f"{param_name}: '{expected_val}' vs '{actual_val}'"
                break

        if not param_ok:
            per_tool[tool_name] = {"score": 0, "reason": "param_mismatch",
                                   "detail": bad_param}
        else:
            per_tool[tool_name] = {"score": 1, "reason": "correct"}

    scores = [v["score"] for v in per_tool.values()]
    avg_score = sum(scores) / len(scores) if scores else 0.0

    return {
        "score": avg_score,
        "per_tool": per_tool,
        "details": ", ".join(f"{t}: {v['score']}({v['reason']})" for t, v in per_tool.items()),
    }


def _edit_distance(s1: str, s2: str) -> int:
    """Levenshtein edit distance."""
    if len(s1) < len(s2):
        return _edit_distance(s2, s1)
    if len(s2) == 0:
        return len(s1)
    prev = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        curr = [i + 1]
        for j, c2 in enumerate(s2):
            curr.append(min(prev[j + 1] + 1, curr[j] + 1, prev[j] + (c1 != c2)))
        prev = curr
    return prev[-1]


def classify_errors(trace: Dict, task_data: Dict) -> Dict:
    """
    Automatic 6-class error attribution (2 Voice + 4 Tool use), consistent with evaluate_reactive.

    Voice layer (speech-perception error, root cause in ASR/perception):
        1. entity_mishearing  — Named entities (person/place/brand/restaurant/hotel) misheard.
        2. numerical_id_error — Numerical IDs (order numbers, phone numbers, flight numbers,
                                etc.) with dropped or transposed digits.

    Tool-use layer (tool-call reasoning errors):
        3. missing_call       — Should have been called but wasn't.
        4. unexpected_call    — Called when it shouldn't be (covers weak/negative scenarios
                                where the model acts on its own initiative, plus calling
                                a non-expected tool).
        5. premature_call     — Called before its required info is gathered.
        6. parameter_reasoning— Parameter reasoning error (not a voice mishearing).

    Priority: voice > tool use; within voice, entity > numerical (when both fire, entity is the root cause).
    Conservative rule: only label the whole call as voice when every failing parameter is identified
    as a voice error; otherwise fall back to parameter_reasoning.
    """
    expected_tools = task_data.get("expected_tools", [])
    expected_names = {item["tool"] for item in expected_tools}
    # forbidden_tools may live at the top level or under metadata
    forbidden_names = set(
        task_data.get("forbidden_tools", [])
        or task_data.get("metadata", {}).get("forbidden_tools", [])
    )

    # Fetch per-tool info_complete_turn
    info_complete = task_data.get("info_complete_turn")
    if isinstance(info_complete, int):
        info_complete_dict = {et["tool"]: info_complete for et in expected_tools}
    elif isinstance(info_complete, dict):
        info_complete_dict = info_complete
    else:
        info_complete_dict = {}

    # Collect actual calls (skip dangling executions)
    actual_calls_by_tool = {}
    actual_names = set()
    PASSIVE_TOOLS = {"extract_info"}
    for step in trace.get("steps", []):
        for te in step.get("tool_executions", []):
            if te.get("dangling"):
                continue
            tool_name = te.get("tool_name", "")
            actual_names.add(tool_name)
            actual_calls_by_tool.setdefault(tool_name, []).append(
                (step["step_id"], te)
            )

    # Locate the interruption step (used to split errors into pre/post buckets).
    # In the transcript, find the turn with is_interruption=True; its step_id matches.
    interrupt_step = None
    for i, turn in enumerate(task_data.get("transcript", [])):
        if turn.get("metadata", {}).get("is_interruption"):
            # step_id is 1-indexed: turn index + 1
            interrupt_step = i + 1
            break

    def _phase_of_call(step_id: int) -> str:
        """Return whether a call happened before or after the interruption. interrupt_step is the step of the interruption itself."""
        if interrupt_step is None:
            return "no_interrupt"
        return "pre" if step_id < interrupt_step else "post"

    per_tool_errors = []

    if not expected_names:
        # weak/negative: a tool was called when it shouldn't be
        action_calls = actual_names - PASSIVE_TOOLS
        if action_calls:
            # Use the step of the first unexpected call to determine the phase
            first_step = min(
                (calls[0][0] for t, calls in actual_calls_by_tool.items() if t in action_calls),
                default=0,
            )
            per_tool_errors.append({
                "tool": ", ".join(sorted(action_calls)),
                "error_type": "unexpected_call",
                "phase": _phase_of_call(first_step),
                "detail": f"Tool should not have been called; called: {sorted(action_calls)}",
            })
    else:
        # Examine each expected tool
        for exp_tool in expected_tools:
            tool_name = exp_tool["tool"]
            expected_params = exp_tool.get("params", {})
            calls = actual_calls_by_tool.get(tool_name, [])

            if not calls:
                # For missing_call infer the phase from the step the expected tool should have run (info_complete_turn)
                tc = info_complete_dict.get(tool_name)
                miss_phase = _phase_of_call(tc) if tc is not None else "no_interrupt"
                per_tool_errors.append({
                    "tool": tool_name,
                    "error_type": "missing_call",
                    "phase": miss_phase,
                    "detail": "Model did not call this tool",
                })
                continue

            # Check timing: any call before info_complete counts as premature
            tool_complete = info_complete_dict.get(tool_name)
            first_step_id = calls[0][0]
            if tool_complete is not None and first_step_id < tool_complete:
                per_tool_errors.append({
                    "tool": tool_name,
                    "error_type": "premature_call",
                    "phase": _phase_of_call(first_step_id),
                    "detail": f"Called at step {first_step_id}; info_complete_turn={tool_complete}",
                })
                continue

            # Check parameters: use the last call as the reference
            last_call_step, last_call = calls[-1]
            actual_args = last_call.get("arguments", {})
            fail_params = []
            for param_name, expected_val in expected_params.items():
                if expected_val is None:
                    continue
                actual_val = actual_args.get(param_name)
                if not match_param(tool_name, param_name, expected_val, actual_val):
                    fail_params.append((param_name, expected_val, actual_val))

            if fail_params:
                # 6-class attribution: voice has priority (entity > numerical); otherwise parameter_reasoning
                voice_subtypes = [_classify_voice_error(p, e, a) for p, e, a in fail_params]
                all_voice = all(v is not None for v in voice_subtypes)
                if all_voice:
                    error_type = "entity_mishearing" if "entity_mishearing" in voice_subtypes else "numerical_id_error"
                else:
                    error_type = "parameter_reasoning"
                detail = "; ".join(f"{p}: '{e}' vs '{a}'" for p, e, a in fail_params)
                per_tool_errors.append({
                    "tool": tool_name,
                    "error_type": error_type,
                    "phase": _phase_of_call(last_call_step),
                    "detail": detail,
                })

        # wrong_tool is now merged into unexpected_call: a tool that is neither expected nor passive
        wrong = actual_names - expected_names - PASSIVE_TOOLS
        for t in sorted(wrong):
            wrong_step = actual_calls_by_tool.get(t, [(0,)])[0][0]
            per_tool_errors.append({
                "tool": t,
                "error_type": "unexpected_call",
                "phase": _phase_of_call(wrong_step),
                "detail": f"Called a tool not in expected_tools: {t}",
            })

    # Aggregate error_types and phase distribution
    error_types = {}
    phase_counts = {"pre": 0, "post": 0, "no_interrupt": 0}
    error_by_phase = {}  # {error_type: {"pre": N, "post": M}}
    for e in per_tool_errors:
        et = e["error_type"]
        ph = e.get("phase", "no_interrupt")
        error_types[et] = error_types.get(et, 0) + 1
        phase_counts[ph] = phase_counts.get(ph, 0) + 1
        error_by_phase.setdefault(et, {"pre": 0, "post": 0, "no_interrupt": 0})
        error_by_phase[et][ph] = error_by_phase[et].get(ph, 0) + 1

    return {
        "errors": per_tool_errors,
        "error_types": error_types,
        "phase_counts": phase_counts,
        "error_by_phase": error_by_phase,
        "primary_error": per_tool_errors[0]["error_type"] if per_tool_errors else None,
    }


class TaskEvaluator:
    """Task evaluator."""

    def __init__(self):
        self.results = []

    def evaluate_trace(self, trace_path: str, task_data: Dict = None, diagnose: bool = False) -> Dict:
        with open(trace_path, 'r', encoding='utf-8') as f:
            trace = json.load(f)

        # Support both task_name and scenario_name for backwards compatibility
        task_name = trace.get('task_name') or trace.get('scenario_name', 'unknown')

        if task_data is None:
            return {
                'task_name': task_name,
                'trace_path': trace_path,
                'checks': {},
                'test_dimension': None,
                'sub_category': None,
                'tool_category': None,
                'success': None,
                'failure_reason': 'skipped: no task_data',
            }

        # Verify trace content matches the task (avoid evaluating new tasks against stale traces)
        task_hash = task_data.get("transcript_hash")
        if task_hash:
            trace_texts = []
            for step in trace.get("steps", []):
                inp = step.get("input_chunk", {})
                if isinstance(inp, dict):
                    text = inp.get("content", "")
                    if text:
                        trace_texts.append(text)
            task_texts = [t.get("text", "") for t in task_data.get("transcript", []) if t.get("speaker") == "user"]
            # Compare the first-turn user input (the most reliable matching signal)
            if trace_texts and task_texts:
                # Compare the first 50 characters because ASR may rewrite later content
                trace_first = trace_texts[0][:50].lower().strip()
                task_first = task_texts[0][:50].lower().strip()
                if trace_first != task_first:
                    print(f"  ⚠️  {task_name}: trace/task content mismatch — likely a stale trace")
                    print(f"       trace: {trace_first}")
                    print(f"       task:  {task_first}")
                    return {
                        'task_name': task_name,
                        'trace_path': trace_path,
                        'checks': {},
                        'test_dimension': None,
                        'sub_category': None,
                        'tool_category': None,
                        'success': None,
                        'failure_reason': 'skipped: trace/task content mismatch (stale trace)',
                    }

        result = {
            'task_name': task_name,
            'trace_path': trace_path,
            'checks': {},
            'test_dimension': task_data.get('test_dimension'),
            'sub_category': task_data.get('sub_category'),
            'tool_category': task_data.get('tool_category'),
        }

        et_check = check_expected_tools(trace, task_data)
        result['checks']['expected_tools'] = et_check
        result['behavior'] = et_check.get('behavior', 'unknown')

        # Record tool sets for F1 computation (skip dangling executions)
        expected_names = {item["tool"] for item in task_data.get("expected_tools", [])}
        actual_names = set()
        for step in trace.get("steps", []):
            for te in step.get("tool_executions", []):
                if not te.get("dangling"):
                    actual_names.add(te["tool_name"])
        result['_expected_tools'] = expected_names
        result['_actual_tools'] = actual_names

        timing_check = check_call_timing(trace, task_data)
        result['checks']['call_timing'] = timing_check

        # v3.1 interruption-specific semantic check
        int_check = check_interruption_semantics(trace, task_data)
        result['checks']['interruption_semantics'] = int_check
        result['interruption_type'] = task_data.get('interruption_type')

        extra_turns_check = check_extra_turns(trace, task_data)
        result['checks']['extra_turns'] = extra_turns_check

        hallucination_check = check_hallucination(trace)
        result['checks']['hallucination'] = hallucination_check

        # behavior_score: per-tool action score
        bs = compute_behavior_score(trace, task_data)
        result['behavior_score'] = bs['score']
        result['checks']['behavior_score'] = bs

        # Per-turn diagnostic analysis (requires --diagnose and OPENAI_API_KEY; skipped otherwise)
        if diagnose:
            try:
                diag = diagnose_per_turn(trace, task_data)
                result['checks']['diagnosis'] = diag
                result['diagnosis_summary'] = diag['summary']
            except RuntimeError:
                result['checks']['diagnosis'] = {"skipped": True}
                result['diagnosis_summary'] = None
        else:
            result['checks']['diagnosis'] = {"skipped": True}
            result['diagnosis_summary'] = None

        # Composite verdict: tool calls + timing + interruption semantics must all be correct to pass.
        # hallucination and extra_turns are diagnostic only and do not affect pass/fail.
        all_passed = et_check['passed'] and timing_check['passed'] and int_check['passed']
        result['success'] = all_passed
        result['hallucination_skipped'] = hallucination_check.get('skipped', False)
        if not all_passed:
            reasons = []
            if not et_check['passed']:
                reasons.append(et_check['reason'])
            if not timing_check['passed']:
                reasons.append(timing_check.get('reason'))
            if not int_check['passed']:
                reasons.append(int_check.get('reason'))
            result['failure_reason'] = reasons[0] if len(reasons) == 1 else '+'.join(reasons)
            # Automatic error attribution
            err_attr = classify_errors(trace, task_data)
            result['error_attribution'] = err_attr
        else:
            result['failure_reason'] = None
            result['error_attribution'] = None
        return result


def evaluate_directory(trace_dir: str, pattern: str = "*.json", task_dir: str = None,
                       diagnose: bool = False):
    """Evaluate every trace file in a directory.

    Args:
        task_dir: optional task-file directory (searched first to avoid task_id collisions).
    """
    evaluator = TaskEvaluator()
    trace_dir = Path(trace_dir)

    trace_files = sorted(trace_dir.glob(pattern))

    if not trace_files:
        print(f"No matching trace files found: {trace_dir}/{pattern}")
        return

    print(f"Found {len(trace_files)} trace files")
    print("=" * 80)

    # When task_dir is supplied, preload every task file into an index.
    # task_index holds every candidate (the same task_id may appear in different subdirectories
    # with different contents); when scoring a trace we pick the right version by matching the
    # first transcript line so later writes don't shadow earlier ones.
    task_index = {}  # task_id -> list of (path, data)
    if task_dir:
        task_dir_path = Path(task_dir)
        for f in task_dir_path.rglob("*.json"):
            try:
                with open(f, encoding="utf-8") as fp:
                    data = json.load(fp)
                tid = data.get("task_id") or data.get("scenario_id", "")
                if tid:
                    task_index.setdefault(tid, []).append((f, data))
            except Exception:
                continue
        dup = {tid: paths for tid, paths in task_index.items() if len(paths) > 1}
        if dup:
            print(f"  [info] {len(dup)} task_ids under {task_dir} have multiple candidates; matching by trace transcript")

    def _pick_task_for_trace(task_id_, trace_data_):
        candidates = task_index.get(task_id_, [])
        if not candidates:
            return None
        if len(candidates) == 1:
            return candidates[0][1]
        # Multiple candidates: match by the first user input in the trace against the first transcript line in the task
        trace_first = ""
        for step in trace_data_.get("steps", []):
            c = step.get("input_chunk", {}).get("content", "")
            if c:
                trace_first = c[:50].lower().strip()
                break
        for _path, td in candidates:
            task_users = [t.get("text", "") for t in td.get("transcript", []) if t.get("speaker") == "user"]
            task_first = (task_users[0] if task_users else "")[:50].lower().strip()
            if task_first == trace_first:
                return td
        return candidates[0][1]  # nothing matched: fall back to the first; the evaluator will surface the mismatch later

    results = []
    for trace_file in trace_files:
        # Try to find the corresponding task file
        with open(trace_file, encoding='utf-8') as f:
            trace_data = json.load(f)
        # Support both task_name and scenario_name for backwards compatibility
        task_id = trace_data.get('task_name') or trace_data.get('scenario_name', '')

        # Search within the supplied directory; when --task-dir is given, do not fall back to the global search to avoid matching an older same-named version
        task_data = _pick_task_for_trace(task_id, trace_data) if task_index else None
        if task_data is None and not task_dir:
            task_file = find_task_file(task_id)
            if task_file:
                with open(task_file, encoding='utf-8') as f:
                    task_data = json.load(f)
        if task_data is None and task_dir:
            print(f"  ⚠️  {task_id}: not found under {task_dir}; skipping (no fallback to global search)")

        result = evaluator.evaluate_trace(str(trace_file), task_data, diagnose=diagnose)
        results.append(result)

        # Write the evaluation result back into the trace file
        checks = result.get('checks', {})
        et = checks.get('expected_tools', {})
        timing = checks.get('call_timing', {})
        extra = checks.get('extra_turns', {})
        hallucination = checks.get('hallucination', {})
        bs = result.get('checks', {}).get('behavior_score', {})
        diag = result.get('checks', {}).get('diagnosis') or {}
        trace_data['evaluation'] = {
            'passed': result['success'],
            'reason': result.get('failure_reason'),
            'details': et.get('details', '') if et else '',
            'call_timing': timing.get('details', ''),
            'extra_turns': extra.get('total_extra_turns', 0),
            'extra_turns_details': extra.get('details', ''),
            'behavior_score': bs.get('score'),
            'behavior_score_details': bs.get('details', ''),
            'diagnosis': diag.get('summary') if not diag.get('skipped') else None,
            'per_turn_behaviors': [
                {"step": t["step_id"], "behavior": t["behavior"],
                 "reasonable": t["reasonable"], "reason": t["reason"]}
                for t in diag.get('turns', [])
            ] if not diag.get('skipped') else None,
            'hallucination': hallucination.get('details', ''),
            'hallucination_skipped': hallucination.get('skipped', False),
            'hallucination_passed': None if hallucination.get('skipped') else hallucination.get('passed', False),
            'error_attribution': result.get('error_attribution'),
        }
        with open(trace_file, 'w', encoding='utf-8') as f:
            json.dump(trace_data, f, ensure_ascii=False, indent=2)

    generate_report(results)


def generate_report(results: List[Dict]):
    """Generate the evaluation report."""
    if not results:
        print("No results")
        return

    et_results = [r for r in results if 'expected_tools' in r.get('checks', {})]

    print("=" * 80)
    print("Evaluation report")
    print("=" * 80)

    if et_results:
        et_pass = sum(1 for r in et_results if r['success'])
        print(f"\n=== Expected Tools comparison ===")
        print(f"Total: {len(et_results)} traces")
        print(f"Pass rate: {et_pass}/{len(et_results)} ({et_pass/len(et_results)*100:.1f}%)")

        # Behavior distribution
        behavior_counts = {}
        for r in et_results:
            b = r.get('behavior', 'unknown')
            behavior_counts[b] = behavior_counts.get(b, 0) + 1
        if behavior_counts:
            print(f"\nBehavior distribution:")
            for b in ["immediate_act", "offer_to_act", "info_gathering", "no_action", "unknown"]:
                if b in behavior_counts:
                    # Count how many tasks of this behavior passed
                    b_pass = sum(1 for r in et_results if r.get('behavior') == b and r['success'])
                    print(f"  {b:<20} {behavior_counts[b]:>3} (pass: {b_pass})")

        # By dimension
        dim_stats: Dict[str, List] = {}
        for r in et_results:
            dim = r.get('test_dimension') or 'unknown'
            dim_stats.setdefault(dim, []).append(r['success'])

        if dim_stats:
            print("\nBy dimension:")
            for dim in sorted(dim_stats):
                vals = dim_stats[dim]
                n = sum(vals)
                print(f"  {dim:<35} {n}/{len(vals)} ({n/len(vals)*100:.1f}%)")

        # By category
        cat_stats: Dict[str, List] = {}
        for r in et_results:
            cat = r.get('tool_category') or 'unknown'
            cat_stats.setdefault(cat, []).append(r['success'])

        if cat_stats:
            print("\nBy category:")
            for cat in sorted(cat_stats):
                vals = cat_stats[cat]
                n = sum(vals)
                print(f"  {cat:<35} {n}/{len(vals)} ({n/len(vals)*100:.1f}%)")

        # By sub-category
        sub_stats: Dict[str, List] = {}
        for r in et_results:
            sub = r.get('sub_category') or 'unknown'
            sub_stats.setdefault(sub, []).append(r['success'])

        if sub_stats:
            print("\nBy sub-category:")
            for sub in sorted(sub_stats):
                vals = sub_stats[sub]
                n = sum(vals)
                print(f"  {sub:<35} {n}/{len(vals)} ({n/len(vals)*100:.1f}%)")

    # By interruption type (v3.1)
    int_type_stats = {}
    for r in et_results:
        itype = r.get('interruption_type')
        if itype:
            int_type_stats.setdefault(itype, []).append(1 if r.get('success') else 0)
    if int_type_stats:
        print("\nBy interruption type:")
        for itype in sorted(int_type_stats):
            vals = int_type_stats[itype]
            n = sum(vals)
            print(f"  {itype:<35} {n}/{len(vals)} ({n/len(vals)*100:.1f}%)")

        # Interruption-semantics check details
        int_sem_stats = {}
        for r in et_results:
            itype = r.get('interruption_type')
            sem = r.get('checks', {}).get('interruption_semantics', {})
            if itype and sem.get('reason'):
                int_sem_stats.setdefault(itype, []).append(sem)
        if int_sem_stats:
            print("\nInterruption-semantics check:")
            for itype in sorted(int_sem_stats):
                sems = int_sem_stats[itype]
                passed = sum(1 for s in sems if s.get('passed'))
                reasons = [s.get('reason') for s in sems if not s.get('passed')]
                print(f"  {itype}: {passed}/{len(sems)} passed")
                for reason in reasons:
                    print(f"    - {reason}")

    # Behavior Score
    bs_scores = [r['behavior_score'] for r in et_results if r.get('behavior_score') is not None]
    if bs_scores:
        avg_bs = sum(bs_scores) / len(bs_scores)
        print(f"\n=== Behavior Score ===")
        print(f"Average behavior_score: {avg_bs:.3f} ({len(bs_scores)} tasks)")

    # Tool F1
    f1_scores = []
    for r in et_results:
        expected_set = set()
        actual_set = set()
        task_name = r['task_name']
        # Extracting from checks would require the original task_data; use the trace steps instead.
        checks = r.get('checks', {})
        et = checks.get('expected_tools', {})
        # Cannot reliably extract from `details`, so use the info recorded in result.
        # We log expected/actual tool sets explicitly in evaluate_trace.
        exp_tools = r.get('_expected_tools', set())
        act_tools = r.get('_actual_tools', set())
        if exp_tools:
            tp = len(exp_tools & act_tools)
            precision = tp / len(act_tools) if act_tools else (1.0 if not exp_tools else 0.0)
            recall = tp / len(exp_tools) if exp_tools else (1.0 if not act_tools else 0.0)
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
            f1_scores.append(f1)

    if f1_scores:
        avg_f1 = sum(f1_scores) / len(f1_scores)
        print(f"\n=== Tool F1 ===")
        print(f"Average Tool F1: {avg_f1:.3f} ({len(f1_scores)} tasks)")

    # Efficiency metric: extra follow-up turns
    extra_turns_data = []
    for r in et_results:
        et = r.get('checks', {}).get('extra_turns', {})
        total = et.get('total_extra_turns', 0)
        extra_turns_data.append((r['task_name'], total, et.get('details', '')))

    has_extra = [x for x in extra_turns_data if x[1] > 0]
    avg_extra = sum(x[1] for x in extra_turns_data) / len(extra_turns_data) if extra_turns_data else 0
    print(f"\n=== Efficiency: extra follow-up turns ===")
    print(f"Average extra_turns: {avg_extra:.1f}")
    print(f"Tasks with extra follow-up: {len(has_extra)}/{len(extra_turns_data)}")
    if has_extra:
        for name, total, details in has_extra:
            print(f"  {name}: +{total} turns ({details})")

    # Hallucination detection
    h_checked = []
    h_skipped = []
    for r in et_results:
        h = r.get('checks', {}).get('hallucination', {})
        if h.get('skipped'):
            h_skipped.append(r['task_name'])
        else:
            h_checked.append((r['task_name'], h.get('passed', False), h.get('details', '')))

    print(f"\n=== Hallucination check ===")
    if h_checked:
        h_pass = sum(1 for x in h_checked if x[1])
        print(f"Passed: {h_pass}/{len(h_checked)}")
        h_failed = [x for x in h_checked if not x[1]]
        for name, _, details in h_failed:
            print(f"  ❌ {name}: {details}")
    if h_skipped:
        print(f"Skipped: {len(h_skipped)} ({', '.join(h_skipped)})")
    if not h_checked and not h_skipped:
        print(f"No data")

    # Per-turn diagnostic summary
    diag_results = [r for r in et_results if r.get('diagnosis_summary')]
    if diag_results:
        # Gather every turn's detailed data
        all_turns = []
        for r in diag_results:
            diag = r.get('checks', {}).get('diagnosis') or {}
            all_turns.extend(diag.get('turns', []))

        if all_turns:
            total = len(all_turns)
            before = [t for t in all_turns if not t.get("info_ready")]
            after = [t for t in all_turns if t.get("info_ready")]

            print(f"\n=== Per-turn diagnosis ===")
            print(f"Total turns: {total} (info-not-ready: {len(before)}, info-ready: {len(after)})")

            # Cross-tabulate by info state x behaviour
            for label, turns in [("info-not-ready", before), ("info-ready", after)]:
                if not turns:
                    continue
                print(f"\n  [{label}] ({len(turns)} turns)")
                behavior_counts = {}
                unreasonable_by_behavior = {}
                for t in turns:
                    b = t["behavior"]
                    behavior_counts[b] = behavior_counts.get(b, 0) + 1
                    if not t["reasonable"]:
                        unreasonable_by_behavior[b] = unreasonable_by_behavior.get(b, 0) + 1

                for b in ["immediate_act", "offer_to_act", "info_gathering", "no_action"]:
                    if b in behavior_counts:
                        cnt = behavior_counts[b]
                        bad = unreasonable_by_behavior.get(b, 0)
                        marker = f" ❌{bad}" if bad else ""
                        print(f"    {b:<20} {cnt:>3}{marker}")

            total_unreasonable = sum(1 for t in all_turns if not t["reasonable"])
            unr_rate = total_unreasonable / total * 100 if total else 0
            print(f"\n  Unreasonable behavior: {total_unreasonable}/{total} ({unr_rate:.1f}%)")

    # Error-attribution summary
    failed = [r for r in results if not r['success']]
    if failed:
        error_type_counts: Dict[str, int] = {}
        for r in failed:
            attr = r.get('error_attribution')
            if attr and attr.get('error_types'):
                for et, cnt in attr['error_types'].items():
                    error_type_counts[et] = error_type_counts.get(et, 0) + cnt
            elif r.get('failure_reason') == 'skipped: no task_data':
                error_type_counts['no_task_data'] = error_type_counts.get('no_task_data', 0) + 1

        if error_type_counts:
            print(f"\n=== Error attribution ({len(failed)} failed traces) ===")
            ORDER = ["entity_mishearing", "numerical_id_error",
                     "missing_call", "unexpected_call", "premature_call", "parameter_reasoning",
                     "no_task_data"]
            for et in ORDER:
                if et in error_type_counts:
                    print(f"  {et:<20} {error_type_counts[et]:>3} times")
            for et in sorted(error_type_counts):
                if et not in ORDER:
                    print(f"  {et:<20} {error_type_counts[et]:>3} times")

        # Pre/post-interruption error distribution (v3.1 specific)
        phase_by_type: Dict[str, Dict[str, int]] = {}
        total_phase = {"pre": 0, "post": 0, "no_interrupt": 0}
        for r in failed:
            attr = r.get('error_attribution')
            if not attr or not attr.get('error_by_phase'):
                continue
            for et, phases in attr['error_by_phase'].items():
                phase_by_type.setdefault(et, {"pre": 0, "post": 0, "no_interrupt": 0})
                for ph, n in phases.items():
                    phase_by_type[et][ph] = phase_by_type[et].get(ph, 0) + n
                    total_phase[ph] = total_phase.get(ph, 0) + n

        if phase_by_type and (total_phase["pre"] + total_phase["post"] > 0):
            print(f"\n=== Pre/post-interruption error distribution ===")
            print(f"  {'error_type':<20} {'pre':>5} {'post':>5}  ratio (post/total)")
            for et in ORDER:
                if et not in phase_by_type:
                    continue
                d = phase_by_type[et]
                pre_n, post_n = d.get("pre", 0), d.get("post", 0)
                total = pre_n + post_n
                ratio = f"{post_n/total*100:.0f}%" if total > 0 else "-"
                print(f"  {et:<20} {pre_n:>5} {post_n:>5}  {ratio:>8}")
            # Totals
            total_pre, total_post = total_phase["pre"], total_phase["post"]
            total = total_pre + total_post
            if total > 0:
                overall_ratio = f"{total_post/total*100:.0f}%"
                print(f"  {'TOTAL':<20} {total_pre:>5} {total_post:>5}  {overall_ratio:>8}")
                print(f"\n  Reading: a high post ratio → the interruption disrupted the model's working memory.")
                print(f"           a low post ratio → the errors are independent of the interruption (raw capability gap).")

    # Detailed failure list
    if failed:
        print(f"\n=== Failure details ({len(failed)}) ===")
        for r in failed[:50]:  # show up to 50 entries
            reason = r['failure_reason']
            attr = r.get('error_attribution')
            # Prefer the error_attribution surface
            if attr and attr.get('errors'):
                types = [e['error_type'] for e in attr['errors']]
                detail = ", ".join(f"{e['tool']}({e['error_type']})" for e in attr['errors'])
            else:
                checks = r.get('checks', {})
                if reason == 'premature_call':
                    detail = checks.get('call_timing', {}).get('details', '')
                elif reason == 'hallucination':
                    detail = checks.get('hallucination', {}).get('details', '')
                else:
                    detail = checks.get('expected_tools', {}).get('details', '')
            print(f"  ❌ {r['task_name']}: {detail}")
        if len(failed) > 50:
            print(f"  ... and {len(failed)-50} more failures")


def main():
    if len(sys.argv) < 2:
        print("Usage: python evaluate_traces.py <trace_directory> [pattern] [--task-dir <dir>] [--diagnose]")
        print("Example: python evaluate_traces.py data/traces")
        print("         python evaluate_traces.py data/traces '*.json' --task-dir data/tasks/proactive/v1.8")
        print("         python evaluate_traces.py data/traces --diagnose  # enable LLM diagnosis (slower)")
        sys.exit(1)

    trace_dir = sys.argv[1]
    pattern = "*.json"
    task_dir = None
    diagnose = False

    # Parse arguments
    args = sys.argv[2:]
    i = 0
    while i < len(args):
        if args[i] == "--task-dir" and i + 1 < len(args):
            task_dir = args[i + 1]
            i += 2
        elif args[i] == "--diagnose":
            diagnose = True
            i += 1
        else:
            pattern = args[i]
            i += 1

    if diagnose:
        print("LLM diagnosis: enabled")
    evaluate_directory(trace_dir, pattern, task_dir=task_dir, diagnose=diagnose)


if __name__ == "__main__":
    main()
