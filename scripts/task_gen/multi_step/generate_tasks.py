#!/usr/bin/env python3
"""
Multi-Step Tool Use Task Generator

Generates tasks where tool call chains have data dependencies:
each tool's output feeds into the next tool's input.

Flow:
1. Pick a server + chain template
2. Load initial state → simulate the chain to get concrete IDs
3. LLM generates natural transcript from the scenario
4. Assemble task JSON with param_source annotations
5. Validate the task
"""

import os
import json
import random
import argparse
from pathlib import Path
from typing import Any, Dict, List, Optional
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

from eval.tools.failing_tools.adapter import create_executor_for_server
from eval.tools.failing_tools.chain_templates import CHAIN_TEMPLATES, get_all_templates, _merged_templates

try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


def _resolve_field_path(data: Any, path: str, index: int = None) -> Any:
    """Extract a value from nested data using dot-path notation.

    Examples:
        _resolve_field_path({"a": {"b": 1}}, "a.b") → 1
        _resolve_field_path([{"id": "x"}], "id", index=0) → "x"
        _resolve_field_path("bare_str", "$") → "bare_str"
        _resolve_field_path({"arr": [{"id": "x"}]}, "arr[0].id") → "x"
    """
    if path == "$":
        return data

    # If data is a list and index is specified, pick the element first
    if isinstance(data, list) and index is not None:
        if index >= len(data):
            return None
        data = data[index]

    parts = path.replace("[", ".[").split(".")
    current = data
    for part in parts:
        if part.startswith("[") and part.endswith("]"):
            idx = int(part[1:-1])
            if isinstance(current, list) and idx < len(current):
                current = current[idx]
            else:
                return None
        elif isinstance(current, dict):
            current = current.get(part)
        else:
            return None
        if current is None:
            return None
    return current


def simulate_chain(
    server_name: str,
    template: Dict[str, Any],
    rng: random.Random = None,
) -> Optional[Dict[str, Any]]:
    """Simulate a chain template against the real server to get concrete IDs.

    Returns a dict with:
      - tool_results: {func_name: raw_output} for each step
      - expected_tools: list of {tool, params, param_source}
      - user_param_values: {dotted_key: concrete_value}
    """
    if rng is None:
        rng = random.Random()

    chain = template["chain"]
    param_flow = template["param_flow"]
    user_params = template.get("user_params", {})

    # Create server + executor with ALL tools (implicit calls may need tools outside chain)
    server_instance, executor = create_executor_for_server(server_name)

    # Pre-sample user param values
    user_values = {}
    for key, spec in user_params.items():
        ptype = spec.get("type", "choice")
        if ptype == "choice":
            user_values[key] = rng.choice(spec["values"])
        elif ptype == "int":
            lo, hi = spec["range"]
            user_values[key] = rng.randint(lo, hi)
        elif ptype == "literal":
            user_values[key] = spec["value"]
        elif ptype == "date":
            # Generate a date in the near future
            month = rng.randint(6, 9)
            day = rng.randint(1, 28)
            user_values[key] = f"2025-{month:02d}-{day:02d}"
        elif ptype == "datetime":
            hour = rng.randint(9, 17)
            user_values[key] = f"2025-07-{rng.randint(1,28):02d}T{hour:02d}:00:00"

    # Fix date ordering: ensure check_out > check_in, end_time > start_time
    date_pairs = [("check_in_date", "check_out_date"), ("start_time", "end_time")]
    for early_suffix, late_suffix in date_pairs:
        early_keys = [k for k in user_values if k.endswith(f".{early_suffix}")]
        for ek in early_keys:
            prefix = ek.rsplit(".", 1)[0]
            lk = f"{prefix}.{late_suffix}"
            if lk in user_values:
                if user_values[lk] <= user_values[ek]:
                    # Swap or generate later date
                    from datetime import datetime, timedelta
                    try:
                        early_dt = datetime.fromisoformat(user_values[ek].replace("Z", ""))
                        late_dt = early_dt + timedelta(days=rng.randint(1, 3))
                        user_values[lk] = late_dt.strftime(user_values[ek][:10] and "%Y-%m-%d")
                        if "T" in user_values[ek]:
                            late_dt = early_dt + timedelta(hours=1)
                            user_values[lk] = late_dt.isoformat()
                    except Exception:
                        user_values[lk] = user_values[ek]  # fallback

    # Execute chain step by step
    tool_results = {}
    expected_tools = []

    for func_name in chain:
        # Build arguments for this call
        call_args = {}
        param_source = {}

        # 1. Apply user_params that aren't in param_flow
        for ukey, uval in user_values.items():
            parts = ukey.split(".", 1)
            if len(parts) != 2 or parts[0] != func_name:
                continue
            param_name = parts[1]
            # Skip nested paths like items[0].quantity or items.quantity
            if "[" in param_name or "." in param_name:
                continue
            if f"{func_name}.{param_name}" not in param_flow:
                call_args[param_name] = uval
                param_source[param_name] = "user"

        # 2. Apply param_flow entries
        for flow_key, flow_spec in param_flow.items():
            # flow_key format: "func_name.param_name"
            parts = flow_key.split(".", 1)
            if len(parts) != 2 or parts[0] != func_name:
                continue
            param_name = parts[1]

            if flow_spec == "user":
                # Get from pre-sampled user values (exact match first,
                # then fallback to same param_name from any tool)
                val = user_values.get(flow_key)
                if val is None:
                    for ukey, uval in user_values.items():
                        if ukey.endswith(f".{param_name}"):
                            val = uval
                            break
                if val is not None:
                    call_args[param_name] = val
                    param_source[param_name] = "user"
            elif isinstance(flow_spec, dict) and "composite" in flow_spec:
                # Composite param — assemble from multiple sources
                if flow_spec["composite"] == "order_items":
                    # Build items array from item_id + user quantity
                    item_src = flow_spec["item_id_from"]
                    item_data = tool_results.get(item_src["from_tool"])
                    if item_data is None:
                        continue
                    item_id = _resolve_field_path(item_data, item_src["field"], item_src.get("index"))
                    qty_key = f"{func_name}.{param_name}.quantity"
                    qty = user_values.get(qty_key, 1)
                    if item_id:
                        call_args[param_name] = [{"item_id": item_id, "quantity": qty}]
                        param_source[param_name] = {
                            "from_tool": item_src["from_tool"],
                            "field": item_src["field"],
                            "quantity": "user",
                        }
            elif isinstance(flow_spec, dict) and "from_tool" in flow_spec:
                # Resolve from previous tool's output
                source_tool = flow_spec["from_tool"]
                field = flow_spec["field"]
                index = flow_spec.get("index")
                collect = flow_spec.get("collect", False)
                prefix = flow_spec.get("prefix", "")
                wrap_list = flow_spec.get("wrap_list", False)

                if source_tool not in tool_results:
                    # Tool hasn't been called yet — might be implicit
                    if flow_spec.get("implicit"):
                        # Need to call this tool first
                        implicit_result = executor.execute_tool(source_tool, {})
                        if implicit_result["success"]:
                            tool_results[source_tool] = implicit_result["raw_output"]
                    else:
                        continue

                source_data = tool_results.get(source_tool)
                if source_data is None:
                    continue

                if collect:
                    # Collect all values of field from a list
                    if isinstance(source_data, list):
                        val = [item.get(field) for item in source_data if field in item]
                    else:
                        val = [_resolve_field_path(source_data, field, index)]
                else:
                    val = _resolve_field_path(source_data, field, index)

                if val is not None:
                    if prefix:
                        val = f"{prefix}{val}"
                    if wrap_list:
                        val = [val]
                    call_args[param_name] = val
                    param_source[param_name] = {
                        "from_tool": source_tool,
                        "field": field,
                    }
            elif isinstance(flow_spec, dict) and "literal" in flow_spec:
                call_args[param_name] = flow_spec["literal"]
                param_source[param_name] = "literal"

        # Execute the tool
        result = executor.execute_tool(func_name, call_args)
        if not result["success"]:
            # Chain broken — return None
            return None

        tool_results[func_name] = result["raw_output"]
        expected_tools.append({
            "tool": func_name,
            "params": call_args,
            "param_source": param_source,
        })

    return {
        "tool_results": tool_results,
        "expected_tools": expected_tools,
        "user_param_values": user_values,
    }


def _build_transcript_prompt(
    server_name: str,
    template: Dict[str, Any],
    sim_result: Dict[str, Any],
) -> str:
    """Build an LLM prompt to generate a natural user transcript."""
    chain = template["chain"]
    expected_tools = sim_result["expected_tools"]
    user_values = sim_result["user_param_values"]

    # Build scenario description
    tool_descriptions = []
    for i, et in enumerate(expected_tools):
        tool = et["tool"]
        params = et["params"]
        sources = et["param_source"]

        user_provided = {k: v for k, v in params.items() if sources.get(k) == "user"}
        from_tool = {k: v for k, v in sources.items() if isinstance(v, dict)}

        desc = f"Step {i+1}: Call {tool}"
        if user_provided:
            desc += f" — user provides: {json.dumps(user_provided, ensure_ascii=False)}"
        if from_tool:
            refs = []
            for k, v in from_tool.items():
                src = v.get("from_tool", "") if isinstance(v, dict) else ""
                if "index" in v if isinstance(v, dict) else False:
                    refs.append(f"{k} = pick from {src} results (user must say which one, e.g. 'the first one')")
                else:
                    refs.append(f"{k} from {src}")
            desc += f" — model extracts: {', '.join(refs)}"
        tool_descriptions.append(desc)

    prompt = f"""You are generating a natural voice conversation for a {server_name.replace('_', ' ')} scenario.

The user is talking to a voice assistant. Generate a realistic multi-turn transcript where the user gradually provides information and the assistant performs actions.

## Scenario: {template['description']}

## Tool call sequence:
{chr(10).join(tool_descriptions)}

## CRITICAL RULES:
1. The user MUST naturally mention all "user provides" values in their speech.
2. The user must NOT say any IDs (like restaurant_id, item_id, order_id). Instead use natural references like "the first one", "that restaurant", "my default address".
3. For coordinates (lat/lng), use place names instead. E.g. "from Union Square to the Ferry Building" not "from 37.7749 to 37.7899".
4. When a previous tool returns a list of options (variants, ride types, calendars, etc.), the user MUST indicate which one to pick. Use phrases like "the first one", "the cheapest option", "use my primary calendar", "the black one", etc. The user should NEVER leave the choice ambiguous.
5. Each turn should feel natural — don't dump all info in one turn.
6. Keep turns concise (1-2 sentences each), as this is a voice conversation.
7. The user does NOT see tool schemas — they speak naturally.
8. Output ONLY a JSON array of user turns (no assistant turns).
9. Use 3-5 user turns total (some turns may trigger multiple tool calls).
10. All text must be in English.

## Output format:
```json
[
  {{"text": "user's first message", "triggers_tools": ["tool1"]}},
  {{"text": "user's second message", "triggers_tools": ["tool2", "tool3"]}},
  ...
]
```
"""
    return prompt


def _call_llm(prompt: str, model: str = "gpt-4.1-mini") -> Optional[str]:
    """Call OpenAI to generate transcript."""
    if not HAS_OPENAI:
        return None

    import os
    base_url = os.environ.get("OPENAI_BASE_URL", "https://us.api.openai.com/v1")
    client = OpenAI(base_url=base_url)
    response = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        max_tokens=1000,
    )
    return response.choices[0].message.content


def _parse_transcript_response(response: str) -> Optional[List[Dict]]:
    """Parse LLM response into transcript turns."""
    # Extract JSON from markdown code blocks
    import re
    json_match = re.search(r'```(?:json)?\s*\n?(.*?)\n?\s*```', response, re.DOTALL)
    if json_match:
        text = json_match.group(1)
    else:
        text = response.strip()

    try:
        turns = json.loads(text)
        if not isinstance(turns, list):
            return None
        return turns
    except json.JSONDecodeError:
        return None


def _build_fallback_transcript(
    template: Dict[str, Any],
    sim_result: Dict[str, Any],
) -> List[Dict]:
    """Build a simple transcript without LLM (for testing)."""
    expected_tools = sim_result["expected_tools"]
    user_values = sim_result["user_param_values"]
    chain = template["chain"]

    turns = []
    current_tools = []

    for et in expected_tools:
        tool = et["tool"]
        sources = et["param_source"]
        user_parts = []

        for k, v in et["params"].items():
            if sources.get(k) == "user":
                user_parts.append(f"{k}: {v}")

        if user_parts:
            text = f"Please {tool.replace('_', ' ')} with {', '.join(user_parts)}."
        else:
            text = f"Go ahead and {tool.replace('_', ' ')}."

        current_tools.append(tool)

        # Group tools that share the same turn
        next_tool_idx = chain.index(tool) + 1
        if next_tool_idx < len(chain):
            next_tool = chain[next_tool_idx]
            next_et = expected_tools[next_tool_idx]
            next_sources = next_et["param_source"]
            # If next tool has no user params, it can be triggered in the same turn
            has_user = any(v == "user" for v in next_sources.values())
            if not has_user and not turns:
                continue

        turns.append({
            "speaker": "user",
            "text": text,
            "timestamp": 0.0 if not turns else 6.0,
            "metadata": {
                "phase": "step",
                "triggers_tools": list(current_tools),
            },
        })
        current_tools = []

    # Flush remaining
    if current_tools:
        turns.append({
            "speaker": "user",
            "text": f"Now {current_tools[0].replace('_', ' ')} for me.",
            "timestamp": 6.0,
            "metadata": {"phase": "step", "triggers_tools": current_tools},
        })

    return turns


def _compute_info_complete_turn(
    expected_tools: List[Dict],
    transcript: List[Dict],
) -> Dict[str, int]:
    """Compute which turn provides enough info for each tool call."""
    ict = {}
    # For multi-step, each tool is triggered by the turn that provides
    # its user params (or the turn after the previous tool completes)
    turn_idx = 1
    for et in expected_tools:
        tool = et["tool"]
        sources = et["param_source"]
        has_user = any(v == "user" for v in sources.values())
        if has_user:
            # Find the turn that mentions this tool's user params
            for i, turn in enumerate(transcript):
                triggers = turn.get("metadata", {}).get("triggers_tools", [])
                if tool in triggers:
                    turn_idx = i + 1
                    break
        ict[tool] = turn_idx
    return ict


def generate_task(
    server_name: str,
    template_name: str,
    task_id: str,
    use_llm: bool = False,
    rng: random.Random = None,
) -> Optional[Dict[str, Any]]:
    """Generate a single multi-step task.

    Returns task JSON dict or None on failure.
    """
    if rng is None:
        rng = random.Random()

    templates = _merged_templates().get(server_name, {})
    template = templates.get(template_name)
    if template is None:
        return None

    # Simulate the chain to get concrete IDs and params
    sim = simulate_chain(server_name, template, rng)
    if sim is None:
        return None

    # Generate transcript
    if use_llm:
        prompt = _build_transcript_prompt(server_name, template, sim)
        response = _call_llm(prompt)
        if response:
            parsed = _parse_transcript_response(response)
            if parsed:
                transcript = []
                for i, turn in enumerate(parsed):
                    transcript.append({
                        "speaker": "user",
                        "text": turn["text"],
                        "timestamp": 0.0 if i == 0 else 6.0,
                        "metadata": {
                            "phase": "step",
                            "triggers_tools": turn.get("triggers_tools", []),
                        },
                    })
            else:
                transcript = _build_fallback_transcript(template, sim)
        else:
            transcript = _build_fallback_transcript(template, sim)
    else:
        transcript = _build_fallback_transcript(template, sim)

    # Compute info_complete_turn
    ict = _compute_info_complete_turn(sim["expected_tools"], transcript)

    # Assemble task
    task = {
        "task_id": task_id,
        "scenario_type": "multi_step",
        "server": server_name,
        "template": template_name,
        "description": template["description"],
        "tools": template["chain"],
        "transcript": transcript,
        "expected_tools": sim["expected_tools"],
        "chain_depth": len(template["chain"]),
        "info_complete_turn": ict,
    }

    return task


def generate_batch(
    output_dir: str,
    count: int = 50,
    use_llm: bool = False,
    seed: int = 42,
):
    """Generate a batch of multi-step tasks across all servers."""
    rng = random.Random(seed)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_templates = get_all_templates()
    template_keys = list(all_templates.keys())

    generated = 0
    attempts = 0
    max_attempts = count * 3

    while generated < count and attempts < max_attempts:
        attempts += 1

        # Round-robin across templates
        tkey = template_keys[generated % len(template_keys)]
        tdef = all_templates[tkey]
        server_name = tdef["server"]
        template_name = tkey.split("/")[1]

        task_id = f"ms_{generated:06d}"
        task = generate_task(server_name, template_name, task_id, use_llm, rng)

        if task is None:
            continue

        # Write to file
        fname = output_path / f"{task_id}.json"
        with open(fname, "w") as f:
            json.dump(task, f, indent=2, ensure_ascii=False)

        generated += 1
        if generated % 10 == 0:
            print(f"  Generated {generated}/{count} tasks")

    print(f"\nDone: {generated} tasks in {output_dir}")
    return generated


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Generate multi-step tool use tasks")
    parser.add_argument("--output", "-o", default="data/tasks/multi_step",
                        help="Output directory")
    parser.add_argument("--count", "-n", type=int, default=50,
                        help="Number of tasks to generate")
    parser.add_argument("--use-llm", action="store_true",
                        help="Use LLM for transcript generation")
    parser.add_argument("--seed", type=int, default=42,
                        help="Random seed")
    args = parser.parse_args()

    generate_batch(args.output, args.count, args.use_llm, args.seed)
