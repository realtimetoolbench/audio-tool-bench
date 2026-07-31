#!/usr/bin/env python3
"""
Task Generator - Graph-based + Back-Instruct pipeline.

Pipeline:
1. Graph Sampling: sample a tool chain from the tool graph.
2. Back-Instruct: generate parameters and a transcript for the chain.
3. Verification: validate the generated task.
"""

import os
import json
import random
import argparse
from collections import Counter
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
import sys

sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

import re
from scripts.task_gen import transcript_hash
from scripts.task_gen.reactive.graph_sampling import sample, SampledGraph
from scripts.task_gen.reactive.transcript_generator import back_instruct, PROACTIVE_STYLES
from scripts.task_gen.verification import rule_check, validate_task
from scripts.task_gen.tool_graph import RESOURCE_EDGES



# ID fields in search->book chains: the user never says these, the model gets them from search results.
_RESOURCE_ID_FIELDS = {(e.to_tool, e.field) for e in RESOURCE_EDGES}


_MONTH_NAMES = [
    "", "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
]

_NUMBER_WORDS = {
    "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
    "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten",
}


def _needs_user_mention(tool: str, pname: str, pvalue) -> bool:
    """Return True if a parameter needs to be mentioned by the user in the transcript."""
    if pvalue is None or isinstance(pvalue, bool):
        return False
    if (tool, pname) in _RESOURCE_ID_FIELDS:
        return False
    return True


def _value_variants(val_str: str) -> List[str]:
    """Generate search variants of a parameter value to handle natural-language differences."""
    variants = [val_str]

    # Date 2026-03-14 -> "March 14", "03-14"
    m = re.fullmatch(r'(\d{4})-(\d{2})-(\d{2})', val_str)
    if m:
        month, day = int(m.group(2)), int(m.group(3))
        if 1 <= month <= 12:
            variants.append(f"{_MONTH_NAMES[month]} {day}")
            variants.append(f"{m.group(2)}-{m.group(3)}")
        return variants

    # Time 20:00 -> "8:00 PM", "8 PM"; 09:00 -> "9:00 AM", "9 AM"
    m = re.fullmatch(r'(\d{2}):(\d{2})', val_str)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2))
        if hour >= 12:
            h12 = hour - 12 if hour > 12 else 12
            suffix = "PM"
        else:
            h12 = hour if hour > 0 else 12
            suffix = "AM"
        if minute == 0:
            variants.append(f"{h12} {suffix}")
            variants.append(f"{h12}:00 {suffix}")
        else:
            variants.append(f"{h12}:{m.group(2)} {suffix}")
        # Also match h:mm without AM/PM
        if minute == 0:
            variants.append(f"{h12}:00")
        else:
            variants.append(f"{h12}:{m.group(2)}")
        return variants

    # Small integers -> English number words ("2" -> "two")
    if val_str in _NUMBER_WORDS:
        variants.append(_NUMBER_WORDS[val_str])

    # time_slot enum: morning -> morning hours, afternoon -> afternoon hours
    if val_str == "morning":
        variants.extend(["morning", "09:00", "9:00", "10:00", "11:00", "9 AM", "10 AM", "11 AM"])
    elif val_str == "afternoon":
        variants.extend(["afternoon", "13:00", "14:00", "15:00", "16:00", "17:00",
                          "1 PM", "2 PM", "3 PM", "4 PM", "5 PM",
                          "1:00 PM", "2:00 PM", "3:00 PM", "4:00 PM", "5:00 PM"])

    return variants


def _is_false_numeric_match(text: str, start: int, end: int) -> bool:
    """Detect false positives for numeric value matches."""
    before = text[max(0, start - 20):start]
    after = text[end:end + 20]
    # Alphanumeric IDs: "G3", "CA1456", "D321"
    if start > 0 and text[start - 1].isalpha():
        return True
    if end < len(text) and text[end].isalpha():
        return True
    # Dates: "March 10", "January 5"
    if re.search(r'(?i)(January|February|March|April|May|June|July|August|September|October|November|December)\s*$', before):
        return True
    # Times: "2:00", "10:30"
    if re.search(r'^:\d{2}', after):
        return True
    # Time AM/PM: "2 PM", "5 am"
    if re.search(r'^\s*(?:AM|PM|am|pm|a\.m\.|p\.m\.)', after):
        return True
    # Ordinals: "3rd", "1st", "2nd"
    if re.search(r'^(?:st|nd|rd|th)\b', after):
        return True
    # Multi-word proper-noun suffixes: "Wandering Earth 3" (small integers only; does not affect amounts like "Wang Fang 982.54")
    matched = text[start:end]
    if re.fullmatch(r'\d{1,2}', matched) and re.search(r'[A-Z][a-z]+\s+[A-Z][a-z]+\s*$', before):
        return True
    return False


def _find_in_text(text: str, val_str: str) -> bool:
    """Search for a parameter value within a text."""
    # Plain numbers
    if re.fullmatch(r'-?\d+(\.\d+)?', val_str):
        pattern = r'(?<!\d)' + re.escape(val_str) + r'(?!\d)'
        for m in re.finditer(pattern, text):
            if not _is_false_numeric_match(text, m.start(), m.end()):
                return True
        return False
    # English number words: exclude pronominal usages like "that one", "the one", "this one"
    if val_str.lower() in _NUMBER_WORDS.values():
        pattern = r'\b' + re.escape(val_str) + r'\b'
        for m in re.finditer(pattern, text, re.IGNORECASE):
            pre = text[max(0, m.start() - 15):m.start()]
            if re.search(r'\b(the|that|this|which|another)\s*$', pre, re.IGNORECASE):
                continue
            return True
        return False
    # H:MM time format — use a digit boundary to keep "9:00" from matching "19:00"
    if re.fullmatch(r'\d{1,2}:\d{2}(?:\s*[APap][Mm])?', val_str):
        pattern = r'(?<!\d)' + re.escape(val_str)
        return bool(re.search(pattern, text, re.IGNORECASE))
    # Default substring match
    return val_str.lower() in text.lower()


# Context disambiguation: numeric parameter name -> unit word expected after the value
_PARAM_CONTEXT_WORDS = {
    "party_size": r'(?:people|persons?|guests?|diners?|of\s+us)',
    "nights": r'nights?',
    "ticket_count": r'tickets?',
    "seat_count": r'seats?',
    "days": r'days?',
}


def _has_param_context(text: str, val_str: str, pname: str) -> bool:
    """Check whether `val_str` in `text` is followed by a context word matching `pname`."""
    ctx_pattern = _PARAM_CONTEXT_WORDS.get(pname)
    if not ctx_pattern:
        return False
    for v in _value_variants(val_str):
        positions = []
        if re.fullmatch(r'-?\d+(\.\d+)?', v):
            for m in re.finditer(r'(?<!\d)' + re.escape(v) + r'(?!\d)', text):
                positions.append(m.end())
        elif v.lower() in _NUMBER_WORDS.values():
            for m in re.finditer(r'\b' + re.escape(v) + r'\b', text, re.IGNORECASE):
                positions.append(m.end())
        for pos in positions:
            after = text[pos:pos + 20]
            if re.search(r'^\s*' + ctx_pattern, after, re.IGNORECASE):
                return True
    return False


def compute_contains_params(
    transcript: List[Dict],
    expected_tools: List[Dict],
) -> Tuple[List[Dict], List[str]]:
    """
    Programmatically compute contains_params for every turn, replacing LLM annotation.

    Two-phase matching:
    1. For each parameter, find every turn whose text contains the value.
    2. Same-value disambiguation: prefer turns with contextual evidence
       ("3 nights" -> nights, "3 people" -> party_size).

    Returns:
        (updated_transcript, warnings)
    """
    # Collect the parameters that need to be searched
    needed = []  # [(tool, param_name, str(value))]
    for et in expected_tools:
        tool = et["tool"]
        for pname, pvalue in et.get("params", {}).items():
            if not _needs_user_mention(tool, pname, pvalue):
                continue
            needed.append((tool, pname, str(pvalue)))

    user_turn_indices = [
        i for i, t in enumerate(transcript)
        if t.get("speaker") == "user"
    ]

    # Phase 1: for each unique value, find every turn that mentions it
    unique_values = {val_str for _, _, val_str in needed}
    value_turns = {}  # val_str -> [turn_index, ...]
    for val_str in unique_values:
        turns = []
        variants = _value_variants(val_str)
        for i in user_turn_indices:
            text = transcript[i]["text"]
            if any(_find_in_text(text, v) for v in variants):
                turns.append(i)
        value_turns[val_str] = turns

    # Phase 2: two-step assignment — first place exclusive values to anchor each tool,
    # then assign shared values using affinity to those anchors.
    param_assignments = {}  # turn_index -> ["tool.param=value", ...]
    warnings = []

    # Count how many (tool, param) pairs share each value
    from collections import Counter, defaultdict
    value_users = defaultdict(list)  # val_str -> [(tool, pname), ...]
    for tool, pname, val_str in needed:
        value_users[val_str].append((tool, pname))

    tool_assigned_turns = defaultdict(set)  # tool -> set of assigned turn indices

    def _assign(tool, pname, val_str, best_turn):
        key = f"{tool}.{pname}"
        param_assignments.setdefault(best_turn, []).append(f"{key}={val_str}")
        tool_assigned_turns[tool].add(best_turn)

    # Step 1: assign exclusive values (values used by exactly one tool.param)
    for tool, pname, val_str in needed:
        if len(value_users[val_str]) > 1:
            continue
        turns = value_turns.get(val_str, [])
        if not turns:
            warnings.append(f"{tool}.{pname}={val_str}")
            continue
        best = None
        if pname in _PARAM_CONTEXT_WORDS:
            for t in turns:
                if _has_param_context(transcript[t]["text"], val_str, pname):
                    best = t
                    break
        if best is None:
            best = turns[0]
        _assign(tool, pname, val_str, best)

    # Step 2: assign shared values (the same value used by multiple tool.param entries).
    # Priority: context words > tool context > tool proximity > first occurrence.
    _TOOL_CONTEXT = {
        "search_attractions": r'(?i)(?:attraction|sight|touris|visit|place.*see|things.*do)',
        "search_hotels": r'(?i)(?:hotel|stay|room|accommodat|lodge|check.?in|night)',
        "search_restaurants": r'(?i)(?:restaurant|dinner|lunch|eat|dine|food|meal)',
        "search_flights": r'(?i)(?:flight|fly|plane|airport|airline)',
        "search_trains": r'(?i)(?:train|rail)',
        "search_movies": r'(?i)(?:movie|film|cinema)',
        "search_shows": r'(?i)(?:show|concert|performance|theater|theatre)',
        "search_doctors": r'(?i)(?:doctor|medical|health|clinic)',
        "search_sports_events": r'(?i)(?:sport|match|game|stadium)',
        "search_restaurants_delivery": r'(?i)(?:deliver|takeout|take.?out)',
        "search_cars": r'(?i)(?:car\b|rent|drive)',
    }

    for tool, pname, val_str in needed:
        if len(value_users[val_str]) <= 1:
            continue
        turns = value_turns.get(val_str, [])
        if not turns:
            warnings.append(f"{tool}.{pname}={val_str}")
            continue

        best = None
        # Prefer context-word disambiguation (numeric parameters)
        if pname in _PARAM_CONTEXT_WORDS:
            for t in turns:
                if _has_param_context(transcript[t]["text"], val_str, pname):
                    best = t
                    break

        # Try tool-context disambiguation (e.g. city parameter of a search tool)
        if best is None and tool in _TOOL_CONTEXT:
            pat = _TOOL_CONTEXT[tool]
            for t in turns:
                if re.search(pat, transcript[t]["text"]):
                    best = t
                    break

        # Tool affinity: pick the turn closest to the tool's other parameters.
        # On ties, prefer turns after the center (parameter mentions usually appear in order
        # within a tool's conversational segment, and entity names tend to fall inside it).
        if best is None and tool_assigned_turns[tool]:
            other = tool_assigned_turns[tool]
            center = sum(other) / len(other)
            best = min(turns, key=lambda t: (abs(t - center), t < center))

        # Fallback: the first matching turn
        if best is None:
            best = turns[0]

        _assign(tool, pname, val_str, best)

    # Build the updated transcript
    updated = []
    for i, turn in enumerate(transcript):
        new_turn = {**turn}
        if turn.get("speaker") == "user":
            metadata = {**turn.get("metadata", {})}
            if i in param_assignments:
                metadata["contains_params"] = sorted(param_assignments[i])
            else:
                metadata.pop("contains_params", None)
            if metadata:
                new_turn["metadata"] = metadata
            else:
                new_turn.pop("metadata", None)
        updated.append(new_turn)

    return updated, warnings


def compute_info_complete_turns(transcript: List[Dict], expected_tools: List[Dict]) -> Dict[str, int]:
    """
    Compute each tool's info_complete_turn: the turn by which all its parameters are present.

    Uses the metadata.contains_params annotation on each transcript turn rather than
    substring matching. The format of each turn's contains_params is:
        ["tool.param=value", ...]

    Returns: {"search_hotels": 2, "book_hotel": 6, ...}
    """
    result = {}
    for exp in expected_tools:
        tool = exp["tool"]
        params = exp.get("params", {})

        # Parameters that must appear in the transcript
        needed = set()
        for pname, pvalue in params.items():
            if pvalue is None:
                continue
            if (tool, pname) in _RESOURCE_ID_FIELDS:
                continue
            if isinstance(pvalue, bool):
                continue
            needed.add(f"{tool}.{pname}")

        if not needed:
            result[tool] = 1
            continue

        # Find the turn where each parameter first appears in contains_params
        found_turns = {}
        for i, turn in enumerate(transcript):
            cp = turn.get("metadata", {}).get("contains_params", [])
            for entry in cp:
                key = entry.split("=")[0]  # "tool.param"
                if key in needed and key not in found_turns:
                    found_turns[key] = i + 1

        if found_turns:
            result[tool] = max(found_turns.values())
        else:
            result[tool] = 1

    return result


# ============================================================
# Tool-category mapping (imported from tool_graph)
# ============================================================

from scripts.task_gen.tool_graph import TOOL_TO_CATEGORY, get_tool_category


def infer_tool_category(tools: List[str]) -> str:
    """Infer the category from a list of tools."""
    categories = set()
    for tool in tools:
        cat = get_tool_category(tool)
        if cat != "other":
            categories.add(cat)

    if len(categories) == 0:
        return None
    elif len(categories) == 1:
        return list(categories)[0]
    else:
        return 'multi'


# ============================================================
# Task generation
# ============================================================

def generate_task(
    task_id: str,
    tool_count: int,
    use_llm: bool = True,
    style: str = "conversational",
) -> Optional[Dict]:
    """
    Generate a single task.

    Args:
        task_id: task ID
        tool_count: number of tools (2-6)
        use_llm: whether to use an LLM to generate the transcript
        style: transcript style (reactive or proactive)

    Returns:
        the generated task, or None on failure
    """
    # v7: style -> strength + scenario_type.
    # All proactive styles (including negative) share scenario_type="proactive";
    # the top-level `strength` field ("strong" / "ambiguous" / "negative") distinguishes sub-grades.
    is_reactive = style == "conversational"
    _STYLE_TO_STRENGTH = {
        "proactive_strong":    "strong",
        "proactive_ambiguous": "ambiguous",
        "proactive_negative":  "negative",
        "proactive_medium":    "ambiguous",  # legacy alias
        "proactive_weak":      "negative",   # legacy alias
    }
    strength = _STYLE_TO_STRENGTH.get(style)  # None for reactive
    is_negative = (strength == "negative")
    scenario_type = "reactive" if is_reactive else "proactive"

    # 1. Sample the tool chain (uses the same sampler as reactive)
    sampled = sample(tool_count=tool_count)

    # 2. Generate the transcript and expected_tools
    try:
        transcript, expected_tools, intent_meta = back_instruct(sampled, use_llm=use_llm, style=style)
    except Exception as e:
        print(f"  transcript generation failed: {type(e).__name__}: {e}")
        return None

    # 3. Programmatically compute contains_params (overrides any LLM output)
    if not is_negative:
        transcript, cp_warnings = compute_contains_params(transcript, expected_tools)
        if cp_warnings:
            print(f"  contains_params warnings: {cp_warnings}")

    # 4. Infer tool_category
    tool_category = infer_tool_category(sampled.tools)

    # 5. Build the task (base schema)
    final_expected = [] if is_negative else expected_tools
    task = {
        "task_id": task_id,
        "description": f"Generated: {len(sampled.tools)} tools, {len(transcript)} turns",
        "task": "generated",
        "scenario_type": scenario_type,
        "tool_category": tool_category,
        "tools": sampled.tools,
        "transcript": transcript,
        "expected_tools": final_expected,  # v1 legacy + validation
        "transcript_hash": transcript_hash(transcript),
        "metadata": {
            "tool_count": len(sampled.tools),
            "turn_count": len(transcript),
            "style": style,
            "sample_type": sampled.sample_type.value,
            "template": sampled.structure.get("template") if isinstance(sampled.structure, dict) else None,
            "generated": True,
        },
        "info_complete_turn": compute_info_complete_turns(transcript, expected_tools) if not is_negative else {},
    }

    # Intent meta (legacy, kept for analysis)
    if intent_meta:
        task["intent"] = intent_meta

    # ─── v7: proactive schema fields ───
    if not is_reactive:
        from scripts.task_gen.tool_graph import READ_TOOLS, WRITE_TOOLS

        task["strength"] = strength

        # tool_universe: split sampled tools into read / write
        # Uses the explicit READ_TOOLS / WRITE_TOOLS lists in tool_graph (with assert self-check).
        # More reliable than prefix heuristics; covers standalone reads like search_medicine / track_package.
        read_tools  = [t for t in sampled.tools if t in READ_TOOLS]
        write_tools = [t for t in sampled.tools if t in WRITE_TOOLS]
        task["tool_universe"] = {
            "read_tools":  sorted(set(read_tools)),
            "write_tools": sorted(set(write_tools)),
        }

        # Per-strength ground-truth fields
        if strength == "strong":
            read_set = set(task["tool_universe"]["read_tools"])
            # Prefer a read tool that has params (parameter matching is only meaningful when scoring)
            read_with_params = [e for e in expected_tools
                                 if e["tool"] in read_set and e.get("params")]
            if read_with_params:
                chosen = read_with_params[0]
            else:
                # fallback: any read tool (e.g. search_books with no parameter list)
                read_in_chain = [e for e in expected_tools if e["tool"] in read_set]
                if not read_in_chain:
                    print(f"  Strong task has no read tool in chain, skipping")
                    return None
                chosen = read_in_chain[0]
            task["expected_tool_if_act"]   = chosen["tool"]
            task["expected_params_if_act"] = chosen["params"]
        elif strength == "ambiguous":
            task["acceptable_decisions"] = ["offer", "ask"]
        else:  # negative
            from scripts.task_gen.distractor_gen import auto_distractor_tools
            task["distractor_tools"] = auto_distractor_tools(sampled.tools, max_distractors=8)

    # 5. Validate
    if is_negative:
        # Negative: expected_tools is empty, so we skip the standard rule_check
        if not task["transcript"]:
            print("  validation failed: empty transcript")
            return None
    else:
        ok, reason = validate_task(task, use_model_check=False)
        if not ok:
            print(f"  validation failed: {reason}")
            return None

    return task


# ============================================================
# Batch generation
# ============================================================

# ============================================================
# Parameter-level quotas (deduplication)
# ============================================================

_NAME_PARAM_KEYS = {
    "passenger_name", "guest_name", "renter_name", "driver_name",
    "student_name", "reader_name", "patient_name", "buyer_name",
    "contact_name", "holder_name", "borrower_name", "customer_name",
    "name",
}
_CITY_PARAM_KEYS = {
    "city", "departure_city", "destination_city",
    "origin", "destination", "pickup_city",
}


def _extract_task_signals(task: Dict) -> Tuple[Tuple[str, ...], Set[str], Set[str]]:
    """Extract quota signals from a task: tool chain + set of names + set of cities."""
    chain = tuple(task.get("tools", []))
    names: Set[str] = set()
    cities: Set[str] = set()
    for et in task.get("expected_tools", []):
        params = et.get("params") or {}
        for k, v in params.items():
            if not isinstance(v, str):
                continue
            if k in _NAME_PARAM_KEYS:
                names.add(v)
            elif k in _CITY_PARAM_KEYS:
                cities.add(v)
    return chain, names, cities


def _load_quota_state(dirs: List[Path]) -> Tuple[Counter, Counter, Counter]:
    """Scan *.json tasks in the given directories and initialize chain/name/city counters."""
    chain_counter: Counter = Counter()
    name_counter: Counter = Counter()
    city_counter: Counter = Counter()
    for d in dirs:
        if not d.exists():
            continue
        for f in sorted(d.glob("*.json")):
            try:
                t = json.load(open(f, "r", encoding="utf-8"))
            except Exception:
                continue
            chain, names, cities = _extract_task_signals(t)
            chain_counter[chain] += 1
            for n in names:
                name_counter[n] += 1
            for c in cities:
                city_counter[c] += 1
    return chain_counter, name_counter, city_counter


def generate_batch(
    output_dir: Path,
    count: int = 100,
    use_llm: bool = True,
    seed: int = 42,
    style: str = "conversational",
    start: int = 0,
    existing_dirs: Optional[List[Path]] = None,
    chain_quota: int = 5,
    name_quota: int = 25,
    city_quota: int = 80,
    max_attempts: int = 5,
) -> Tuple[int, int]:
    """
    Generate tasks in batch (tool count uniformly distributed in 4-8).

    Args:
        output_dir: output directory
        count: number of tasks to generate
        use_llm: whether to use an LLM
        seed: random seed
        style: transcript style
        start: starting index
        existing_dirs: additional directories included in the quota accounting
            (shared across the corpus); output_dir is always included.
        chain_quota: upper limit per tool chain
        name_quota: upper limit per person name
        city_quota: upper limit per city
        max_attempts: maximum attempts per task_id (including quota retries)

    Returns:
        (number successfully generated, total attempts)
    """
    random.seed(seed)
    output_dir.mkdir(parents=True, exist_ok=True)

    # Task ID prefix
    if style == "proactive_weak":
        prefix = "neg"
    elif style == "conversational":
        prefix = "gen"
    elif style in PROACTIVE_STYLES:
        prefix = "pro"
    else:
        prefix = "gen"

    # Initialize quota counters (output_dir + additional directories)
    quota_dirs = [output_dir]
    if existing_dirs:
        quota_dirs.extend(existing_dirs)
    chain_counter, name_counter, city_counter = _load_quota_state(quota_dirs)
    print(f"Quota init from {len(quota_dirs)} dir(s): "
          f"{sum(chain_counter.values())} existing tasks, "
          f"{len(chain_counter)} distinct chains, "
          f"{len(name_counter)} names, {len(city_counter)} cities")
    print(f"Quota limits: chain<={chain_quota}, name<={name_quota}, city<={city_quota}")

    total_generated = 0
    total_attempted = 0
    dropped_by_quota = 0

    for i in range(start, start + count):
        total_attempted += 1

        # Build the task ID
        task_id = f"{prefix}_{i:06d}"

        task = None
        for attempt in range(max_attempts):
            # Reseed each attempt so different attempts explore different paths
            if attempt > 0:
                random.seed(seed + i * 100 + attempt)
            # Tool count uniformly distributed in 4-8 (sampled independently per attempt)
            tool_count = random.randint(4, 8)
            candidate = generate_task(
                task_id=task_id,
                tool_count=tool_count,
                use_llm=use_llm,
                style=style,
            )
            if not candidate:
                continue

            chain, names, cities = _extract_task_signals(candidate)
            quota_fail = None
            if chain_counter[chain] >= chain_quota:
                quota_fail = f"chain {chain_counter[chain]}/{chain_quota}"
            else:
                for n in names:
                    if name_counter[n] >= name_quota:
                        quota_fail = f"name '{n}' {name_counter[n]}/{name_quota}"
                        break
            if not quota_fail:
                for c in cities:
                    if city_counter[c] >= city_quota:
                        quota_fail = f"city '{c}' {city_counter[c]}/{city_quota}"
                        break

            if quota_fail:
                dropped_by_quota += 1
                print(f"  [quota] {task_id} attempt {attempt+1}: dropped ({quota_fail}), retrying")
                continue

            task = candidate
            chain_counter[chain] += 1
            for n in names:
                name_counter[n] += 1
            for c in cities:
                city_counter[c] += 1
            break

        if task:
            output_file = output_dir / f"{task_id}.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(task, f, ensure_ascii=False, indent=2)

            total_generated += 1
            tpl = task.get("metadata", {}).get("template") or "(chain_walk)"
            print(f"  {task_id} (tools={task['metadata']['tool_count']}, "
                  f"turns={task['metadata']['turn_count']}, template={tpl})")
        else:
            print(f"  {task_id} failed (after {max_attempts} attempts, {dropped_by_quota} dropped by quota)")

    print(f"\n[quota summary] dropped by quota: {dropped_by_quota}; "
          f"final chains: {len(chain_counter)}; names: {len(name_counter)}; cities: {len(city_counter)}")
    return total_generated, total_attempted


# ============================================================
# Main entry point
# ============================================================

def main():
    parser = argparse.ArgumentParser(description="Graph-based Task Generator")
    parser.add_argument("--output", "-o", type=str, default="data/tasks/generated",
                        help="output directory")
    parser.add_argument("--count", "-n", type=int, default=1,
                        help="number of tasks to generate")
    parser.add_argument("--seed", "-s", type=int, default=42,
                        help="random seed")
    parser.add_argument("--use-llm", action="store_true",
                        help="use the LLM to generate transcripts")
    parser.add_argument("--style", type=str, default="conversational",
                        choices=["direct", "natural", "conversational",
                                 # v7 official styles
                                 "proactive_strong", "proactive_ambiguous", "proactive_negative",
                                 # legacy aliases (backward compatible)
                                 "proactive_medium", "proactive_weak"],
                        help="transcript style")
    parser.add_argument("--start", type=int, default=0,
                        help="starting index")
    parser.add_argument("--existing-dirs", type=str, default="",
                        help="extra directories included in quota accounting (comma-separated). output_dir is always included.")
    parser.add_argument("--chain-quota", type=int, default=5,
                        help="upper limit per tool chain (default 5)")
    parser.add_argument("--name-quota", type=int, default=25,
                        help="upper limit per person name (default 25)")
    parser.add_argument("--city-quota", type=int, default=80,
                        help="upper limit per city (default 80)")
    parser.add_argument("--max-attempts", type=int, default=5,
                        help="maximum attempts per task_id (including quota retries, default 5)")

    args = parser.parse_args()
    output_dir = Path(args.output)
    existing_dirs = [Path(p.strip()) for p in args.existing_dirs.split(",") if p.strip()]

    print("=" * 60)
    print("Task Generator")
    print("=" * 60)
    print(f"Task count: {args.count}")
    print(f"Start index: {args.start}")
    print(f"Tool count: uniform in 4-8")
    print(f"Use LLM: {args.use_llm}")
    print(f"Transcript style: {args.style}")
    print(f"Output directory: {output_dir}")
    if existing_dirs:
        print(f"Extra quota directories: {[str(d) for d in existing_dirs]}")
    print()

    generated, attempted = generate_batch(
        output_dir=output_dir,
        count=args.count,
        use_llm=args.use_llm,
        seed=args.seed,
        style=args.style,
        start=args.start,
        existing_dirs=existing_dirs,
        chain_quota=args.chain_quota,
        name_quota=args.name_quota,
        city_quota=args.city_quota,
        max_attempts=args.max_attempts,
    )

    print()
    print("=" * 60)
    print(f"Done: {generated}/{attempted} ({generated/attempted*100:.1f}%)")
    print(f"Output directory: {output_dir}")
    print("=" * 60)


if __name__ == "__main__":
    main()
