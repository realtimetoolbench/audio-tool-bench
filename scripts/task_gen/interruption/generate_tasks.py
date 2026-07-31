#!/usr/bin/env python3
"""
Interruption Task Generator

Generates tasks that test the model's ability to handle user interruptions.

Speech-phase (v3.0) — trigger: keyword (listens to what the model is saying)
- correction: user corrects a parameter
- cancellation: user cancels an action
- redirection: user inserts a new topic and later returns to the original

Tool-phase (v3.1) — trigger: tool_phase (listens for the function_call the model
emits and leaves it dangling without executing).
Each scenario has exactly one tool call interrupted (a search tool) with no
prerequisite tools.
- tool_cancel: user cancels while the model is emitting the search function_call (expected=[])
- tool_correction: user corrects the wrong parameter and re-executes (expected=[search(correct)])
- tool_priority: user interrupts with an urgent task, then resumes the search
  (expected=[priority, search])

Reuses sampling, parameter, and validation logic from the existing reactive pipeline.
"""

import json
import random
import argparse
from pathlib import Path
from typing import Dict, List, Tuple, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from scripts.task_gen import transcript_hash, add_timestamps
from scripts.task_gen.reactive.graph_sampling import sample, SampledGraph
from scripts.task_gen.reactive.transcript_generator import (
    _call_llm, verify_transcript_params,
)
from scripts.task_gen.param_engine import (
    sample_params_for_chain, sample_params_for_tool,
    TOOL_DATA_SOURCE, get_available_cities,
)
from scripts.task_gen.reactive.generate_tasks import (
    compute_contains_params, compute_info_complete_turns,
    infer_tool_category,
)
from scripts.task_gen.verification import validate_task
from scripts.task_gen.tool_graph import (
    TOOL_GRAPH, SEARCH_TOOLS, TOOL_TO_CATEGORY,
)
from eval.tools.mock_data import DATES


INTERRUPTION_TYPES = [
    "correction", "cancellation", "redirection",           # speech-phase (v3.0)
    "tool_cancel", "tool_correction",                      # tool-phase (v3.1)
    "priority_no_return", "priority_late_return", "priority_early_return",
]

TYPE_GROUPS = {
    "all": INTERRUPTION_TYPES,
    "speech_phase": ["correction", "cancellation", "redirection"],
    "tool_phase": [
        "tool_cancel", "tool_correction",
        "priority_no_return", "priority_late_return", "priority_early_return",
    ],
}

# dangling_return mode per priority subtype
_PRIORITY_RETURN_MODE = {
    "priority_no_return": "never",
    "priority_late_return": "during_inserted",
    "priority_early_return": "before_resume",
}

# Correctable param types for tool_correction
_CORRECTABLE_PARAMS = {"city", "origin", "destination", "date", "checkin_date", "checkout_date", "pickup_date"}

# Priority tool candidates (standalone tools suitable for urgent interruptions)
_PRIORITY_TOOLS = ["check_balance", "list_bills", "track_package", "check_ride_status"]

# Tools without mock_data support — skip during sampling
_BROKEN_TOOLS = {
    "search_parking", "search_medicine", "search_books", "search_courses",
    "book_home_service", "request_ride",
}

# search tool → domain keyword (used for cancellation trigger & redirection)
_DOMAIN_KEYWORDS = {
    "search_hotels": "hotel",
    "search_flights": "flight",
    "search_trains": "train",
    "search_restaurants": "restaurant",
    "search_movies": "movie",
    "search_shows": "show",
    "search_attractions": "attraction",
    "search_cars": "car",
    "search_doctors": "doctor",
    "search_home_services": "service",
    "search_parking": "parking",
    "search_courses": "course",
    "search_books": "book",
    "search_restaurants_delivery": "delivery",
    "search_sports_events": "game",
}


# ============================================================
# Prompt Builders
# ============================================================

def _flat_param_list(tool_params: List[Dict]) -> str:
    lines = []
    for tp in tool_params:
        for k, v in tp["params"].items():
            lines.append(f"  {tp['tool']}.{k}: {v}")
    return "\n".join(lines)


def _build_correction_prompt(tool_params: List[Dict], target_turns: int) -> str:
    tools = [tp["tool"] for tp in tool_params]
    return f"""Generate a conversation for a voice assistant tool-calling scenario with an INTERRUPTION.

## Scenario: CORRECTION
The user gives a command but says ONE parameter wrong. While the assistant is responding (echoing back the wrong value), the user interrupts to correct it.

## Tool Chain
{', '.join(tools)}

## Correct Parameters (the FINAL correct values after correction)
{_flat_param_list(tool_params)}

## Requirements
1. Turn 1+: User provides parameters naturally, but ONE parameter value is WRONG
   - Pick a parameter that's easy to confuse (city, name, date, time)
   - The wrong value should be plausible (e.g., "Shanghai" instead of "Shenzhen", not gibberish)
2. Interruption turn: User corrects the wrong parameter
   - "Wait, not X, I meant Y" / "Sorry, I said X but I meant Y"
   - Keep it short and direct
3. After the interruption: User may provide remaining parameters if needed
4. Each turn: at most 3 new parameters
5. Direct, command-style language (no greetings or small talk)
6. Self-contained: mention entity names explicitly, never "that one" or "the first result"
7. Additive phrasing: "for 3 nights", not "update nights to 3"

## Output Format
```json
{{
  "turns": [
    {{"content": "User message with wrong param...", "phase": "pre_interrupt", "contains_params": ["tool.param=value"]}},
    {{"content": "Wait, not X, I meant Y", "phase": "interruption"}},
    {{"content": "Additional info if needed...", "phase": "post_interrupt", "contains_params": ["tool.param=value"]}}
  ],
  "wrong_param": {{"tool": "tool_name", "param": "param_name", "wrong_value": "the wrong value the user initially said"}},
  "interrupt_keyword": "the wrong value (what the model would echo back)"
}}
```

Rules:
1. Generate exactly {target_turns} user turns total
2. Exactly ONE turn must have phase "interruption"
3. The interruption turn should be turn 2 or 3 (early in the conversation)
4. ALL correct parameter values must appear in the transcript (across all turns)
5. The wrong_value must be a plausible alternative, NOT the correct value
6. interrupt_keyword = the wrong_value (model will echo this before being interrupted)

Generate now:"""


def _build_cancellation_prompt(
    tool_params: List[Dict],
    cancelled_tools: List[str],
    cancel_keyword: str,
    target_turns: int,
) -> str:
    kept_tools = [tp for tp in tool_params if tp["tool"] not in cancelled_tools]
    cancelled_names = [tp["tool"] for tp in tool_params if tp["tool"] in cancelled_tools]
    all_names = [tp["tool"] for tp in tool_params]

    return f"""Generate a conversation for a voice assistant tool-calling scenario with an INTERRUPTION.

## Scenario: CANCELLATION
The user initially mentions wanting multiple things. After the assistant handles the first request and starts talking about the next one ({cancel_keyword}), the user interrupts to cancel it.

## Full Tool Chain (originally intended)
{', '.join(all_names)}

## Tools to KEEP (these should be called)
{', '.join(tp['tool'] for tp in kept_tools)}

## Tools to CANCEL (user will cancel these)
{', '.join(cancelled_names)}
Cancel keyword: "{cancel_keyword}"

## Parameters for KEPT tools (must appear in transcript)
{_flat_param_list(kept_tools)}

## Requirements
1. Turn 1+: User provides info for the kept tools, AND mentions wanting the cancelled task too
   - Example: "Search flights from Beijing to Shenzhen, and also find hotels there"
   - The cancelled task can be mentioned briefly without full params
2. Interruption turn: User clearly cancels the {cancel_keyword} task
   - Must be explicit: "Actually forget the {cancel_keyword}" / "Never mind the {cancel_keyword}, I don't need it"
   - Keep it short and direct
3. After interruption: User may provide remaining params for KEPT tools
4. Each turn: at most 3 new parameters
5. Direct, command-style language
6. Self-contained entity references

## Output Format
```json
{{
  "turns": [
    {{"content": "User message mentioning both tasks...", "phase": "pre_interrupt", "contains_params": ["tool.param=value"]}},
    {{"content": "Forget the {cancel_keyword}", "phase": "interruption"}},
    {{"content": "More details for kept tools...", "phase": "post_interrupt", "contains_params": ["tool.param=value"]}}
  ],
  "interrupt_keyword": "{cancel_keyword}"
}}
```

Rules:
1. Generate exactly {target_turns} user turns total
2. Exactly ONE turn must have phase "interruption"
3. ALL parameters for KEPT tools must appear in the transcript
4. Parameters for CANCELLED tools do NOT need to appear
5. The user must briefly mention wanting the {cancel_keyword} task before cancelling it

Generate now:"""


def _build_redirection_prompt(
    original_params: List[Dict],
    inserted_params: List[Dict],
    target_turns: int,
) -> str:
    orig_tools = [tp["tool"] for tp in original_params]
    ins_tools = [tp["tool"] for tp in inserted_params]
    orig_keyword = _DOMAIN_KEYWORDS.get(
        orig_tools[0], orig_tools[0].replace("search_", "")
    )

    return f"""Generate a conversation for a voice assistant tool-calling scenario with an INTERRUPTION.

## Scenario: REDIRECTION
The user starts with one topic. While the assistant is responding, the user interrupts with a different request. After the new request is handled, the user returns to the original topic.

## Original Topic (started first, completed last)
Tools: {', '.join(orig_tools)}
Parameters:
{_flat_param_list(original_params)}

## Inserted Topic (interruption, handled in the middle)
Tools: {', '.join(ins_tools)}
Parameters:
{_flat_param_list(inserted_params)}

## Requirements
1. Turn 1+: User provides info for the ORIGINAL topic
2. Interruption turn: User switches to the INSERTED topic
   - "Hold on, first check..." / "Wait, before that, search for..."
   - Include the inserted topic's key parameters
3. Post-interruption turns: User provides remaining params for the inserted topic if needed
4. Return turn: User explicitly returns to the original topic
   - "OK, back to the {orig_keyword}" / "Now about the {orig_keyword}"
   - The model must remember the original parameters (testing memory)
5. Each turn: at most 3 new parameters
6. Direct, command-style language
7. Self-contained entity references

## Output Format
```json
{{
  "turns": [
    {{"content": "Original topic request...", "phase": "original", "contains_params": ["tool.param=value"]}},
    {{"content": "Wait, first check inserted topic...", "phase": "interruption", "contains_params": ["tool.param=value"]}},
    {{"content": "More inserted topic details...", "phase": "inserted", "contains_params": ["tool.param=value"]}},
    {{"content": "OK back to the original topic", "phase": "return"}}
  ],
  "interrupt_keyword": "{orig_keyword}"
}}
```

Rules:
1. Generate exactly {target_turns} user turns total
2. Exactly ONE turn must have phase "interruption"
3. Exactly ONE turn must have phase "return" (after the inserted topic is done)
4. ALL parameters for BOTH topics must appear in the transcript
5. Original topic params in "original" phase turns
6. Inserted topic params in "interruption" and/or "inserted" phase turns
7. The "return" turn should NOT repeat the original parameters — just ask to continue

Generate now:"""


# ============================================================
# Tool-Phase Prompt Builders (v3.1)
# ============================================================

def _sample_wrong_value(tool_name: str, param_name: str, correct_value) -> Optional[str]:
    """Sample a plausible wrong value for tool_correction.

    Returns a different value of the same type, or None if no alternative found.
    """
    if param_name in ("city",) and tool_name in TOOL_DATA_SOURCE:
        cities = get_available_cities(TOOL_DATA_SOURCE[tool_name])
        alternatives = [c for c in cities if c != correct_value]
        return random.choice(alternatives) if alternatives else None

    if param_name in ("origin", "destination"):
        # Use cities from flight/train routes
        from eval.tools.mock_data import FLIGHTS, TRAINS
        all_cities = set()
        for route in list(FLIGHTS.keys()) + list(TRAINS.keys()):
            all_cities.update(route)
        alternatives = [c for c in all_cities if c != correct_value]
        return random.choice(alternatives) if alternatives else None

    if param_name in ("date", "checkin_date", "checkout_date", "pickup_date"):
        alternatives = [d for d in DATES if d != correct_value]
        return random.choice(alternatives) if alternatives else None

    return None


def _build_tool_cancel_prompt(
    tool_params: List[Dict],
    dangling_tool: str,
    target_turns: int,
) -> str:
    # Find cancelled tools (dangling + its book pair) and kept tools
    dangling_idx = next(i for i, tp in enumerate(tool_params) if tp["tool"] == dangling_tool)
    # cancelled = dangling search + next tool (its book pair)
    cancelled = [tool_params[dangling_idx]["tool"]]
    if dangling_idx + 1 < len(tool_params):
        cancelled.append(tool_params[dangling_idx + 1]["tool"])
    kept = [tp for tp in tool_params if tp["tool"] not in cancelled]

    cancel_keyword = _DOMAIN_KEYWORDS.get(dangling_tool, dangling_tool.replace("search_", ""))

    return f"""Generate a conversation for a voice assistant tool-calling scenario with a TOOL-PHASE INTERRUPTION.

## Scenario: TOOL_CANCEL
The user mentions wanting multiple things. The model issues the first search function_call — but before it executes, the user cancels that part. Then the user continues with the remaining tasks.

## Full Tool Chain
{', '.join(tp['tool'] for tp in tool_params)}

## Dangling Tool (model issues this, user cancels before execution)
{dangling_tool}

## Tools to CANCEL
{', '.join(cancelled)}

## Tools to KEEP (user continues with these AFTER cancelling)
{', '.join(tp['tool'] for tp in kept)}

## Parameters for KEPT tools (must appear in transcript)
{_flat_param_list(kept)}

## Requirements
1. Turn 1: User mentions wanting the {cancel_keyword} task AND other tasks
   - Provides parameters for {dangling_tool} so the model issues the function_call
   - Example: "Search hotels in Shanghai and also find flights to Beijing"
2. Interruption turn: User cancels the {cancel_keyword} part
   - "Never mind the {cancel_keyword}" / "Forget the {cancel_keyword}, skip it"
3. After interruption: User provides parameters for the KEPT tools
4. Each turn: at most 3 new parameters
5. Direct, command-style language
6. Self-contained entity references

## Output Format
```json
{{
  "turns": [
    {{"content": "Search hotels and also...", "phase": "pre_interrupt", "contains_params": ["{dangling_tool}.param=value"]}},
    {{"content": "Forget the {cancel_keyword}", "phase": "interruption"}},
    {{"content": "Now for the flights...", "phase": "post_interrupt", "contains_params": ["tool.param=value"]}}
  ]
}}
```

Rules:
1. Generate exactly {target_turns} user turns total
2. Exactly ONE turn with phase "interruption"
3. ALL parameters for KEPT tools must appear in the transcript
4. The user must mention the {cancel_keyword} task before cancelling it

Generate now:"""


def _build_tool_correction_prompt(
    tool_params: List[Dict],
    dangling_tool: str,
    wrong_param_info: Dict,
    target_turns: int,
) -> str:
    return f"""Generate a conversation for a voice assistant tool-calling scenario with a TOOL-PHASE INTERRUPTION.

## Scenario: TOOL_CORRECTION
The user gives a command with one WRONG parameter. The model issues the first search function_call with the wrong value — but before it executes, the user corrects it. Then the user continues with the remaining tools.

## Full Tool Chain
{', '.join(tp['tool'] for tp in tool_params)}

## Correct Parameters (FINAL correct values after correction)
{_flat_param_list(tool_params)}

## Wrong Parameter
Tool: {wrong_param_info['tool']}
Param: {wrong_param_info['param']}
Wrong value (user says first): {wrong_param_info['wrong_value']}
Correct value (user corrects to): {wrong_param_info['correct_value']}

## Dangling Tool (model issues function_call with wrong param, user corrects)
{dangling_tool}

## Requirements
1. Turn 1: User provides parameters for {dangling_tool} but says {wrong_param_info['param']} as "{wrong_param_info['wrong_value']}" (WRONG)
   - All other parameters for {dangling_tool} should be correct
2. Interruption turn: User corrects the wrong parameter
   - "Wait, not {wrong_param_info['wrong_value']}, I meant {wrong_param_info['correct_value']}"
3. After interruption: User provides parameters for the REMAINING tools in the chain
4. Each turn: at most 3 new parameters
5. Direct, command-style language
6. Self-contained entity references

## Output Format
```json
{{
  "turns": [
    {{"content": "User message with wrong param...", "phase": "pre_interrupt", "contains_params": ["tool.param=value"]}},
    {{"content": "Wait, not X, I meant Y", "phase": "interruption"}},
    {{"content": "Continue with next tools...", "phase": "post_interrupt", "contains_params": ["tool.param=value"]}}
  ]
}}
```

Rules:
1. Generate exactly {target_turns} user turns total
2. Exactly ONE turn must have phase "interruption" (turn 2 or 3)
3. ALL correct parameter values for ALL tools must appear in the transcript
4. The wrong value "{wrong_param_info['wrong_value']}" must appear in a pre_interrupt turn
5. Do NOT include interrupt_keyword — the trigger is the dangling function_call, not a keyword

Generate now:"""


def _build_tool_priority_prompt(
    tool_params: List[Dict],
    dangling_tool: str,
    inserted_params: List[Dict],
    target_turns: int,
) -> str:
    inserted_tools_str = ', '.join(tp['tool'] for tp in inserted_params)

    return f"""Generate a conversation for a voice assistant tool-calling scenario with a TOOL-PHASE INTERRUPTION.

## Scenario: TOOL_PRIORITY
The user starts a multi-step task. The model issues the first search function_call — but before it executes, the user interrupts with an urgent, different-domain request (a full chain of tools). After completing the inserted chain, the user resumes the original chain.

## Original Tool Chain
{', '.join(tp['tool'] for tp in tool_params)}

## Dangling Tool (model issues this call, user interrupts before execution)
{dangling_tool}

## Inserted Tool Chain (urgent tasks inserted by user)
{inserted_tools_str}

## Original Parameters (must all appear in transcript)
{_flat_param_list(tool_params)}

## Inserted Parameters (must all appear in transcript)
{_flat_param_list(inserted_params)}

## Structure
1. Turn 1: User provides parameters for {dangling_tool} (first search)
2. Interruption turn: User switches to the inserted chain (first inserted-chain parameters)
3. Inserted turns: User provides remaining parameters for inserted chain tools
4. Return turn: User explicitly returns to the original task — "OK, continue with the search now" / "Go ahead with the search"
5. Post-return turns: User provides remaining parameters for the rest of the original chain

## Requirements
1. Turn 1: User provides parameters for {dangling_tool}
   - The model will issue a function_call that gets dangling'd
2. Interruption turn: User switches to the inserted chain
   - "Hold on, I need to do something else first" / "Wait, before that..."
   - Start providing parameters for the inserted tools
3. Continue providing parameters for inserted chain tools (if needed)
4. Return turn: User asks to resume — do NOT repeat {dangling_tool} parameters
   - "OK, continue with the search now" / "Go ahead with the search" / "Now back to the original topic"
   - This turn must have phase "return" and should NOT carry parameters for the original chain
5. Post-return turns: User provides parameters for remaining tools in the original chain
6. Each turn: at most 3 new parameters
7. Direct, command-style language
8. Self-contained entity references

## Output Format
```json
{{
  "turns": [
    {{"content": "Search hotels in Beijing...", "phase": "original", "contains_params": ["{dangling_tool}.param=value"]}},
    {{"content": "Hold on, first search restaurants in Shanghai", "phase": "interruption", "contains_params": ["search_restaurants.city=Shanghai"]}},
    {{"content": "Book that restaurant for tomorrow", "phase": "inserted", "contains_params": ["book_restaurant.date=..."]}},
    {{"content": "OK, continue with the search now", "phase": "return"}},
    {{"content": "Book the first hotel for...", "phase": "post_return", "contains_params": ["book_hotel.param=value"]}}
  ]
}}
```

Rules:
1. Generate exactly {target_turns} user turns total
2. Exactly ONE turn with phase "interruption" (first turn of inserted chain)
3. Exactly ONE turn with phase "return" (after the inserted chain is done)
4. The "return" turn must NOT repeat {dangling_tool} parameters — just ask to continue
5. ALL parameters for ALL original tools must appear in the transcript
6. ALL parameters for ALL inserted tools must appear in the transcript

Generate now:"""


# ============================================================
# Transcript Generation
# ============================================================

def _generate_tool_phase_transcript(
    interruption_type: str,
    tool_params: List[Dict],
    expected_tools: List[Dict],
    dangling_tool: str,
    model: str = "gpt-5.2",
    max_retries: int = 3,
    # type-specific
    wrong_param_info: Dict = None,
    priority_tool: str = None,
    priority_params: Dict = None,
    inserted_params: List[Dict] = None,
    dangling_return: str = "never",
) -> Optional[Tuple[List[Dict], Dict]]:
    """Generate tool-phase interruption transcript via LLM.

    Returns:
        (transcript, extra_meta) or None on failure
    """
    all_params = tool_params + (inserted_params or [])
    n_params = sum(
        len([k for k, v in tp["params"].items() if v is not None])
        for tp in all_params
    )
    # Full chain: same complexity as v3.0
    # +1 for interruption turn, +1 for explicit return turn (tool_priority only)
    extra = 2 if interruption_type == "tool_priority" else 0
    params_per_turn = 3
    target_turns = max(4, (n_params + 2) // params_per_turn + 2 + extra)

    if interruption_type == "tool_cancel":
        prompt = _build_tool_cancel_prompt(tool_params, dangling_tool, target_turns)
    elif interruption_type == "tool_correction":
        prompt = _build_tool_correction_prompt(
            tool_params, dangling_tool, wrong_param_info, target_turns,
        )
    elif interruption_type == "tool_priority":
        prompt = _build_tool_priority_prompt(
            tool_params, dangling_tool, inserted_params or [], target_turns,
        )
    else:
        raise ValueError(f"Unknown tool-phase type: {interruption_type}")

    for attempt in range(max_retries):
        try:
            content = _call_llm(prompt, model)

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            result = json.loads(json_str)

            turns = result.get("turns", [])
            if not turns:
                print(f"  Attempt {attempt+1}: missing turns")
                continue

            interrupt_turns = [t for t in turns if t.get("phase") == "interruption"]
            if len(interrupt_turns) != 1:
                print(f"  Attempt {attempt+1}: expected 1 interruption turn, got {len(interrupt_turns)}")
                continue

            if not all(t.get("content", "").strip() for t in turns):
                print(f"  Attempt {attempt+1}: empty content in turns")
                continue

            if len(turns) < 2:
                print(f"  Attempt {attempt+1}: too few turns ({len(turns)})")
                continue

            # tool_priority: must have explicit return turn (v3.0-style)
            if interruption_type == "tool_priority":
                return_turns = [t for t in turns if t.get("phase") == "return"]
                if len(return_turns) != 1:
                    print(f"  Attempt {attempt+1}: expected 1 return turn for tool_priority, got {len(return_turns)}")
                    continue
                has_post = any(t.get("phase") == "post_return" for t in turns)
                if not has_post:
                    print(f"  Attempt {attempt+1}: missing post_return turns for tool_priority")
                    continue

            # Convert to standard transcript format
            transcript = []
            for i, turn in enumerate(turns):
                entry = {"speaker": "user", "text": turn["content"]}
                metadata = {}

                if turn.get("phase"):
                    metadata["phase"] = turn["phase"]
                if turn.get("contains_params"):
                    metadata["contains_params"] = turn["contains_params"]

                if turn["phase"] == "interruption":
                    metadata["is_interruption"] = True
                    metadata["interrupts_after_step"] = i
                    metadata["interrupt_trigger"] = {
                        "type": "tool_phase",
                        "dangling_tool": dangling_tool,
                        "dangling_return": dangling_return,
                        "timeout_s": 5.0,
                    }

                if metadata:
                    entry["metadata"] = metadata
                transcript.append(entry)

            # Timestamps
            add_timestamps(transcript)
            for turn in transcript:
                if turn.get("metadata", {}).get("is_interruption"):
                    turn["timestamp"] = 0.0
            # tool_priority: return turn gets a fixed timestamp after the priority tool completes
            if interruption_type == "tool_priority":
                for turn in transcript:
                    if turn.get("metadata", {}).get("phase") == "return":
                        turn["timestamp"] = 6.0

            # Verify params — for tool_cancel only verify pre-dangling tools
            is_valid, missing = verify_transcript_params(transcript, expected_tools)
            if not is_valid:
                print(f"  Attempt {attempt+1}: Missing params: {missing[:3]}...")
                continue

            extra_meta = {
                "dangling_call": dangling_tool,
            }
            if interruption_type == "tool_correction" and wrong_param_info:
                extra_meta["wrong_params"] = {
                    f"{wrong_param_info['tool']}.{wrong_param_info['param']}": wrong_param_info["wrong_value"]
                }
                extra_meta["corrected_params"] = {
                    f"{wrong_param_info['tool']}.{wrong_param_info['param']}": wrong_param_info["correct_value"]
                }
            if interruption_type == "tool_priority" and inserted_params:
                extra_meta["inserted_tools"] = [tp["tool"] for tp in inserted_params]

            return transcript, extra_meta

        except json.JSONDecodeError as e:
            print(f"  Attempt {attempt+1}: JSON parse error: {e}")
        except Exception as e:
            print(f"  Attempt {attempt+1}: LLM error: {e}")

    return None


def _generate_interruption_transcript(
    interruption_type: str,
    tool_params: List[Dict],
    expected_tools: List[Dict],
    model: str = "gpt-5.2",
    max_retries: int = 3,
    # type-specific
    cancelled_tools: List[str] = None,
    cancel_keyword: str = None,
    original_params: List[Dict] = None,
    inserted_params: List[Dict] = None,
) -> Optional[Tuple[List[Dict], str, Dict]]:
    """
    Generate interruption transcript via LLM.

    Returns:
        (transcript, interrupt_keyword, extra_meta) or None on failure
    """
    n_params = sum(
        len([k for k, v in tp["params"].items() if v is not None])
        for tp in tool_params
    )
    # +1 for interruption turn, +1 for buffer
    target_turns = max(4, (n_params + 2) // 3 + 2)

    if interruption_type == "correction":
        prompt = _build_correction_prompt(tool_params, target_turns)
    elif interruption_type == "cancellation":
        prompt = _build_cancellation_prompt(
            tool_params, cancelled_tools, cancel_keyword, target_turns
        )
    elif interruption_type == "redirection":
        prompt = _build_redirection_prompt(
            original_params, inserted_params, target_turns
        )
    else:
        raise ValueError(f"Unknown interruption type: {interruption_type}")

    for attempt in range(max_retries):
        try:
            content = _call_llm(prompt, model)

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            result = json.loads(json_str)

            turns = result.get("turns", [])
            if not turns:
                print(f"  Attempt {attempt+1}: missing turns")
                continue

            # Exactly one interruption turn
            interrupt_turns = [t for t in turns if t.get("phase") == "interruption"]
            if len(interrupt_turns) != 1:
                print(f"  Attempt {attempt+1}: expected 1 interruption turn, got {len(interrupt_turns)}")
                continue

            if not all(t.get("content", "").strip() for t in turns):
                print(f"  Attempt {attempt+1}: empty content in turns")
                continue

            if len(turns) < 3:
                print(f"  Attempt {attempt+1}: too few turns ({len(turns)})")
                continue

            interrupt_keyword = result.get("interrupt_keyword", "")
            if not interrupt_keyword:
                print(f"  Attempt {attempt+1}: missing interrupt_keyword")
                continue

            # Redirection must have a return turn
            if interruption_type == "redirection":
                return_turns = [t for t in turns if t.get("phase") == "return"]
                if not return_turns:
                    print(f"  Attempt {attempt+1}: missing return turn for redirection")
                    continue

            # Convert to standard transcript format
            transcript = []
            for i, turn in enumerate(turns):
                entry = {"speaker": "user", "text": turn["content"]}
                metadata = {}

                if turn.get("phase"):
                    metadata["phase"] = turn["phase"]
                if turn.get("contains_params"):
                    metadata["contains_params"] = turn["contains_params"]

                if turn["phase"] == "interruption":
                    # interrupts_after_step is 1-indexed step number
                    metadata["is_interruption"] = True
                    metadata["interrupts_after_step"] = i  # previous step (1-indexed = i)
                    metadata["interrupt_trigger"] = {
                        "type": "keyword",
                        "keyword": interrupt_keyword,
                        "timeout_s": 5.0,
                    }

                if metadata:
                    entry["metadata"] = metadata
                transcript.append(entry)

            # Timestamps: normal for all turns, then override interruption to 0.0
            add_timestamps(transcript)
            for turn in transcript:
                if turn.get("metadata", {}).get("is_interruption"):
                    turn["timestamp"] = 0.0

            # Verify all expected params appear in transcript
            is_valid, missing = verify_transcript_params(transcript, expected_tools)
            if not is_valid:
                print(f"  Attempt {attempt+1}: Missing params: {missing[:3]}...")
                continue

            extra_meta = {}
            if interruption_type == "correction":
                extra_meta["wrong_param"] = result.get("wrong_param")

            return transcript, interrupt_keyword, extra_meta

        except json.JSONDecodeError as e:
            print(f"  Attempt {attempt+1}: JSON parse error: {e}")
        except Exception as e:
            print(f"  Attempt {attempt+1}: LLM error: {e}")

    return None


# ============================================================
# Task Generation
# ============================================================

def _find_search_book_pairs(tools: List[str]) -> List[Tuple[str, str]]:
    """Find all search-book pairs in a tool list, preserving order."""
    pairs = []
    for tool in tools:
        if tool in SEARCH_TOOLS:
            book_tool = TOOL_GRAPH.get_search_book_pair(tool)
            if book_tool and book_tool in tools:
                pairs.append((tool, book_tool))
    return pairs


def _assemble_task(
    task_id: str,
    interruption_type: str,
    sampled: SampledGraph,
    transcript: List[Dict],
    expected_tools: List[Dict],
    interrupt_keyword: str,
    extra_meta: Dict = None,
) -> Optional[Dict]:
    """Assemble final task dict from generated components."""
    transcript, cp_warnings = compute_contains_params(transcript, expected_tools)
    if cp_warnings:
        print(f"  contains_params warnings: {cp_warnings}")


    ict = compute_info_complete_turns(transcript, expected_tools)
    tool_category = infer_tool_category(sampled.tools)

    task = {
        "task_id": task_id,
        "description": f"Interruption ({interruption_type}): {len(sampled.tools)} tools, {len(transcript)} turns",
        "task": "generated",
        "scenario_type": "interruption",
        "interruption_type": interruption_type,
        "test_dimension": "interruption",
        "sub_category": interruption_type,
        "tool_category": tool_category,
        "tools": sampled.tools,
        "transcript": transcript,
        "expected_tools": expected_tools,
        "transcript_hash": transcript_hash(transcript),
        "info_complete_turn": ict,
        "metadata": {
            "tool_count": len(sampled.tools),
            "turn_count": len(transcript),
            "interruption_type": interruption_type,
            "interrupt_keyword": interrupt_keyword,
            "template": sampled.structure.get("template") if isinstance(sampled.structure, dict) else None,
            "generated": True,
        },
    }

    if extra_meta:
        task["metadata"].update(extra_meta)
        # Promote forbidden_tools to top-level (evaluation code reads from top-level)
        if "forbidden_tools" in extra_meta:
            task["forbidden_tools"] = extra_meta["forbidden_tools"]
        if "inserted_tools" in extra_meta:
            task["inserted_tools"] = extra_meta["inserted_tools"]

    ok, reason = validate_task(task, use_model_check=False)
    if not ok:
        print(f"  validation failed: {reason}")
        return None

    return task


def generate_correction_task(
    task_id: str,
    tool_count: int = None,
    model: str = "gpt-5.2",
) -> Optional[Dict]:
    """Generate a correction interruption task."""
    if tool_count is None:
        tool_count = random.randint(4, 6)

    sampled = sample(tool_count=tool_count)
    tool_params, expected_tools = sample_params_for_chain(sampled.tools)

    result = _generate_interruption_transcript(
        "correction", tool_params, expected_tools, model=model,
    )
    if result is None:
        return None

    transcript, interrupt_keyword, extra_meta = result
    return _assemble_task(
        task_id, "correction", sampled, transcript,
        expected_tools, interrupt_keyword, extra_meta,
    )


def generate_cancellation_task(
    task_id: str,
    tool_count: int = None,
    model: str = "gpt-5.2",
) -> Optional[Dict]:
    """Generate a cancellation interruption task."""
    if tool_count is None:
        tool_count = random.randint(4, 6)
    # Even number for clean search-book pairs
    if tool_count % 2 != 0:
        tool_count += 1

    # Need at least 2 search-book pairs
    for _ in range(5):
        sampled = sample(tool_count=tool_count)
        pairs = _find_search_book_pairs(sampled.tools)
        if len(pairs) >= 2:
            break
    else:
        print(f"  Cannot find chain with 2+ search-book pairs after 5 attempts")
        return None

    # Cancel the last pair (earlier tasks are already done)
    cancelled_pair = pairs[-1]
    cancelled_tools = list(cancelled_pair)
    cancel_keyword = _DOMAIN_KEYWORDS.get(
        cancelled_pair[0], cancelled_pair[0].replace("search_", "")
    )

    # Sample params for ALL tools (including cancelled, for prompt context)
    tool_params, all_expected = sample_params_for_chain(sampled.tools)

    # expected_tools = only non-cancelled
    expected_tools = [et for et in all_expected if et["tool"] not in cancelled_tools]

    result = _generate_interruption_transcript(
        "cancellation", tool_params, expected_tools,
        model=model,
        cancelled_tools=cancelled_tools,
        cancel_keyword=cancel_keyword,
    )
    if result is None:
        return None

    transcript, interrupt_keyword, extra_meta = result
    task = _assemble_task(
        task_id, "cancellation", sampled, transcript,
        expected_tools, interrupt_keyword, extra_meta,
    )
    if task:
        task["cancelled_tools"] = cancelled_tools
    return task


def generate_redirection_task(
    task_id: str,
    tool_count: int = None,
    model: str = "gpt-5.2",
) -> Optional[Dict]:
    """Generate a redirection interruption task."""
    orig_count = random.randint(2, 4)
    ins_count = random.randint(2, 4)

    # Ensure different domains, no tool overlap
    for _ in range(10):
        orig_sampled = sample(tool_count=orig_count)
        ins_sampled = sample(tool_count=ins_count)

        orig_cats = {TOOL_TO_CATEGORY.get(t) for t in orig_sampled.tools}
        ins_cats = {TOOL_TO_CATEGORY.get(t) for t in ins_sampled.tools}

        if not orig_cats.intersection(ins_cats):
            break
    else:
        print(f"  Cannot find non-overlapping chains after 10 attempts")
        return None

    # Sample params independently
    orig_params, orig_expected = sample_params_for_chain(orig_sampled.tools)
    ins_params, ins_expected = sample_params_for_chain(ins_sampled.tools)

    # Combined: inserted first (processed first), then original (returned to)
    all_tools = ins_sampled.tools + orig_sampled.tools
    all_tool_params = ins_params + orig_params
    expected_tools = ins_expected + orig_expected

    combined_sampled = SampledGraph(
        sample_type=orig_sampled.sample_type,
        tools=all_tools,
        structure={"original": orig_sampled.tools, "inserted": ins_sampled.tools},
    )

    result = _generate_interruption_transcript(
        "redirection", all_tool_params, expected_tools,
        model=model,
        original_params=orig_params,
        inserted_params=ins_params,
    )
    if result is None:
        return None

    transcript, interrupt_keyword, extra_meta = result
    return _assemble_task(
        task_id, "redirection", combined_sampled, transcript,
        expected_tools, interrupt_keyword, extra_meta,
    )


# ============================================================
# Tool-Phase Task Generators (v3.1)
# ============================================================

def generate_tool_cancel_task(
    task_id: str,
    model: str = "gpt-5.2",
) -> Optional[Dict]:
    """Generate a tool_cancel task: mirrors v3.0 cancellation with tool_phase trigger.

    Full chain (4-6 tools). First search-book pair is cancelled via dangling.
    User continues with remaining tools after cancellation.
    """
    tool_count = random.randint(4, 6)
    if tool_count % 2 != 0:
        tool_count += 1

    # Need at least 2 search-book pairs
    for _ in range(5):
        sampled = sample(tool_count=tool_count)
        pairs = _find_search_book_pairs(sampled.tools)
        if len(pairs) >= 2:
            break
    else:
        print(f"  Cannot find chain with 2+ search-book pairs after 5 attempts")
        return None

    tool_params, all_expected = sample_params_for_chain(sampled.tools)

    # Cancel the first pair (dangling = first search)
    cancelled_pair = pairs[0]
    cancelled_tools = list(cancelled_pair)
    dangling_tool = cancelled_pair[0]

    # expected_tools = only non-cancelled
    expected_tools = [et for et in all_expected if et["tool"] not in cancelled_tools]
    forbidden_tools = cancelled_tools

    result = _generate_tool_phase_transcript(
        "tool_cancel", tool_params, expected_tools,
        dangling_tool=dangling_tool, model=model,
    )
    if result is None:
        return None

    transcript, extra_meta = result
    extra_meta["forbidden_tools"] = forbidden_tools

    task = _assemble_task(
        task_id, "tool_cancel", sampled, transcript,
        expected_tools, "", extra_meta,
    )
    if task:
        task["cancelled_tools"] = cancelled_tools
    return task


def generate_tool_correction_task(
    task_id: str,
    model: str = "gpt-5.2",
) -> Optional[Dict]:
    """Generate a tool_correction task: mirrors v3.0 correction with tool_phase trigger.

    Full chain (4-6 tools). First search has wrong param, dangling'd, user corrects.
    Then user continues with remaining chain.
    """
    tool_count = random.randint(4, 6)

    for _ in range(5):
        sampled = sample(tool_count=tool_count)
        pairs = _find_search_book_pairs(sampled.tools)
        if pairs:
            break
    else:
        print(f"  Cannot find chain with search-book pair after 5 attempts")
        return None

    tool_params, expected_tools = sample_params_for_chain(sampled.tools)

    # Dangling tool = first search tool
    dangling_tool = pairs[0][0]

    # Find a correctable param on the dangling tool
    dangling_params = next(tp for tp in tool_params if tp["tool"] == dangling_tool)
    correctable = [
        (k, v) for k, v in dangling_params["params"].items()
        if k in _CORRECTABLE_PARAMS and v is not None
    ]
    if not correctable:
        print(f"  No correctable params found on {dangling_tool}")
        return None

    param_name, correct_value = random.choice(correctable)
    wrong_value = _sample_wrong_value(dangling_tool, param_name, correct_value)
    if wrong_value is None:
        print(f"  Cannot sample wrong value for {dangling_tool}.{param_name}")
        return None

    wrong_param_info = {
        "tool": dangling_tool,
        "param": param_name,
        "wrong_value": wrong_value,
        "correct_value": correct_value,
    }

    result = _generate_tool_phase_transcript(
        "tool_correction", tool_params, expected_tools,
        dangling_tool=dangling_tool, model=model,
        wrong_param_info=wrong_param_info,
    )
    if result is None:
        return None

    transcript, extra_meta = result
    return _assemble_task(
        task_id, "tool_correction", sampled, transcript,
        expected_tools, "", extra_meta,
    )


def generate_tool_priority_task(
    task_id: str,
    model: str = "gpt-5.2",
    priority_subtype: str = "priority_no_return",
) -> Optional[Dict]:
    """Generate a tool_priority task: mirrors v3.0 redirection with tool_phase trigger.

    Main chain (2-4 tools) + inserted chain (2-4 tools), matching v3.0 redirection.
    First search of main chain is dangling'd, user inserts a different-domain chain,
    then resumes and continues with the original chain.
    """
    main_count = random.randint(2, 4)
    ins_count = random.randint(2, 4)

    # Sample two non-overlapping chains (same as v3.0 redirection)
    for _ in range(20):
        main_sampled = sample(tool_count=main_count)
        ins_sampled = sample(tool_count=ins_count)

        # Skip chains with broken tools
        all_tools = set(main_sampled.tools) | set(ins_sampled.tools)
        if all_tools & _BROKEN_TOOLS:
            continue

        main_cats = {TOOL_TO_CATEGORY.get(t) for t in main_sampled.tools}
        ins_cats = {TOOL_TO_CATEGORY.get(t) for t in ins_sampled.tools}

        pairs = _find_search_book_pairs(main_sampled.tools)
        if pairs and not main_cats.intersection(ins_cats):
            break
    else:
        print(f"  Cannot find non-overlapping chains with search-book pair after 10 attempts")
        return None

    main_params, main_expected = sample_params_for_chain(main_sampled.tools)
    ins_params, ins_expected = sample_params_for_chain(ins_sampled.tools)

    # Dangling tool = first search tool of main chain
    dangling_tool = pairs[0][0]

    # expected_tools = inserted chain first + main chain after (same as v3.0 redirection)
    expected_tools = ins_expected + main_expected

    # Combine tool params for prompt (main chain params — inserted chain handled separately)
    combined_tools = main_sampled.tools + ins_sampled.tools
    combined_sampled = SampledGraph(
        sample_type=main_sampled.sample_type,
        tools=combined_tools,
        structure={"main": main_sampled.tools, "inserted": ins_sampled.tools},
    )

    result = _generate_tool_phase_transcript(
        "tool_priority", main_params, expected_tools,
        dangling_tool=dangling_tool, model=model,
        priority_tool=None, priority_params=None,
        inserted_params=ins_params,
        dangling_return=_PRIORITY_RETURN_MODE.get(priority_subtype, "never"),
    )
    if result is None:
        return None

    transcript, extra_meta = result
    extra_meta["inserted_tools"] = list(ins_sampled.tools)
    extra_meta["dangling_return"] = _PRIORITY_RETURN_MODE.get(priority_subtype, "never")

    return _assemble_task(
        task_id, priority_subtype, combined_sampled, transcript,
        expected_tools, "", extra_meta,
    )


# ============================================================
# Batch Generation
# ============================================================

def _make_priority_generator(subtype: str):
    """Create a generator function for a specific priority subtype."""
    def generator(task_id: str, model: str = "gpt-5.2") -> Optional[Dict]:
        return generate_tool_priority_task(task_id, model=model, priority_subtype=subtype)
    return generator

_TYPE_GENERATORS = {
    "correction": generate_correction_task,
    "cancellation": generate_cancellation_task,
    "redirection": generate_redirection_task,
    "tool_cancel": generate_tool_cancel_task,
    "tool_correction": generate_tool_correction_task,
    "priority_no_return": _make_priority_generator("priority_no_return"),
    "priority_late_return": _make_priority_generator("priority_late_return"),
    "priority_early_return": _make_priority_generator("priority_early_return"),
}


def generate_batch(
    output_dir: Path,
    count: int = 30,
    seed: int = 42,
    interruption_type: str = "all",
    start: int = 0,
    model: str = "gpt-5.2",
) -> Tuple[int, int]:
    """Batch generate interruption tasks."""
    random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Expand TYPE_GROUPS or use as single type
    if interruption_type in TYPE_GROUPS:
        types = TYPE_GROUPS[interruption_type]
    elif interruption_type in _TYPE_GENERATORS:
        types = [interruption_type]
    else:
        raise ValueError(f"Unknown interruption type or group: {interruption_type}")

    total_generated = 0
    total_attempted = 0

    # tool-phase types use tint_ prefix
    _TOOL_PHASE = {"tool_cancel", "tool_correction", "priority_no_return", "priority_late_return", "priority_early_return"}

    for i in range(start, start + count):
        total_attempted += 1

        # Round-robin across types
        itype = types[i % len(types)]
        prefix = "tint" if itype in _TOOL_PHASE else "int"
        task_id = f"{prefix}_{i:06d}"
        generator = _TYPE_GENERATORS[itype]

        task = None
        for attempt in range(3):
            task = generator(task_id=task_id, model=model)
            if task:
                break
            random.seed(seed + i * 100 + attempt)

        if task:
            output_file = output_dir / f"{task_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(task, f, ensure_ascii=False, indent=2)

            total_generated += 1
            print(f"  {task_id} ({itype}, tools={task['metadata']['tool_count']}, turns={task['metadata']['turn_count']})")
        else:
            print(f"  {task_id} ({itype}) failed")

    return total_generated, total_attempted


# ============================================================
# CLI
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Interruption Task Generator")
    parser.add_argument("--output", "-o", type=str, default="data/tasks/interruption",
                        help="output directory")
    parser.add_argument("--count", "-n", type=int, default=3,
                        help="number of tasks to generate")
    parser.add_argument("--seed", "-s", type=int, default=42,
                        help="random seed")
    parser.add_argument("--use-llm", action="store_true",
                        help="use the LLM to generate transcripts (required)")
    parser.add_argument("--type", type=str, default="all",
                        choices=[
                            "correction", "cancellation", "redirection",
                            "tool_cancel", "tool_correction", "tool_priority",
                            "all", "speech_phase", "tool_phase",
                        ],
                        help="interruption type (single type or group: all/speech_phase/tool_phase)")
    parser.add_argument("--start", type=int, default=0,
                        help="starting index")
    parser.add_argument("--model", type=str, default="gpt-5.2",
                        help="LLM model")

    args = parser.parse_args()
    output_dir = Path(args.output)

    print("=" * 60)
    print("Interruption Task Generator")
    print("=" * 60)
    print(f"Task count: {args.count}")
    print(f"Start index: {args.start}")
    print(f"Interruption type: {args.type}")
    print(f"Output directory: {output_dir}")
    print(f"LLM model: {args.model}")
    print()

    generated, attempted = generate_batch(
        output_dir=output_dir,
        count=args.count,
        seed=args.seed,
        interruption_type=args.type,
        start=args.start,
        model=args.model,
    )

    print()
    print("=" * 60)
    print(f"Done: {generated}/{attempted} ({generated/attempted*100:.1f}%)")
    print(f"Output directory: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
