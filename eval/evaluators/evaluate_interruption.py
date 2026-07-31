#!/usr/bin/env python3
"""
Audio Tool Bench — Interruption evaluator (speech + tool)

Usage:
    python3 eval/evaluators/evaluate_interruption.py <task_dir> <trace_dir>

Example:
    python3 scripts/benchmark.py eval --trace-root outputs/traces/default_1040 --model-dir openai_gpt-realtime

Automatically handles two interruption subtypes:
  speech/  — speech-level interruptions (correction / cancellation / redirection).
             Reuses the core evaluator from evaluate_reactive (same tool-call correctness +
             timing + anti-hallucination rules, plus check_interruption_semantics to verify
             post-interruption semantics).
  tool/    — tool-phase interruptions with priority-aware semantics (tool_cancel /
             tool_correction / priority_no_return / priority_late_return / priority_early_return).
             Realtime semantics: behaviour checks for re-querying / not re-querying / respecting
             cancellation on dangling tools.

If either subdirectory is missing it is skipped; the final output reports speech / tool / overall pass rates.
"""

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from scripts.evaluate_reactive import (
    check_expected_tools,
    check_call_timing,
    classify_errors,
    evaluate_directory,
)


# ---------- tool-phase priority-aware evaluation (ported from eval_v31_priority_aware.py) ----------

def _find_dangling_info(task: dict):
    """Return (dangling_tool, interruption_type)."""
    itype = task.get("interruption_type")
    dangling = None
    for c in task.get("transcript", []):
        trig = c.get("metadata", {}).get("interrupt_trigger", {})
        if trig.get("dangling_tool"):
            dangling = trig["dangling_tool"]
            break
    return dangling, itype


def _phase_to_step_ids(task: dict, target_phase: str):
    """transcript index → trace step_id (the runner only counts user chunks as steps)."""
    step_ids = []
    user_idx = 0
    for c in task.get("transcript", []):
        if c.get("speaker") != "user":
            continue
        user_idx += 1
        if c.get("metadata", {}).get("phase") == target_phase:
            step_ids.append(user_idx)
    return step_ids


def _tools_called_in_steps(trace: dict, step_ids: set):
    tools = []
    for s in trace.get("steps", []):
        if s.get("step_id") not in step_ids:
            continue
        for e in s.get("tool_executions", []):
            tools.append(e["tool_name"])
    return tools


def _domain_of(tool: str):
    """Shared domain for search_X / book_X."""
    for prefix in ("search_", "book_"):
        if tool.startswith(prefix):
            return tool[len(prefix):]
    return tool


def evaluate_tool_trace(trace: dict, task: dict) -> dict:
    """Priority-aware tool-phase interruption evaluation."""
    dangling, itype = _find_dangling_info(task)
    if not dangling or not itype:
        return {"passed": None, "reason": "no interrupt metadata"}

    exp = check_expected_tools(trace, task)
    timing = check_call_timing(trace, task)
    base_pass = bool(exp.get("passed") and timing.get("passed"))

    post_return_ids = set(_phase_to_step_ids(task, "post_return"))
    inserted_ids = set(_phase_to_step_ids(task, "inserted"))
    post_interrupt_ids = set(_phase_to_step_ids(task, "post_interrupt"))
    interruption_ids = set(_phase_to_step_ids(task, "interruption"))

    post_tools = _tools_called_in_steps(trace, post_return_ids)
    post_called_dangling = dangling in post_tools
    inserted_tools = _tools_called_in_steps(trace, inserted_ids)
    post_interrupt_tools = _tools_called_in_steps(trace, post_interrupt_ids)
    interruption_tools = _tools_called_in_steps(trace, interruption_ids)
    all_after_tools = post_tools + inserted_tools + post_interrupt_tools + interruption_tools

    if itype == "priority_no_return":
        priority_ok = post_called_dangling
        priority_reason = "re-called dangling" if priority_ok else "no re-call (hallucinated)"
    elif itype in ("priority_late_return", "priority_early_return"):
        priority_ok = not post_called_dangling
        priority_reason = "no redundant re-call" if priority_ok else "redundant re-call"
    elif itype == "tool_cancel":
        dangling_domain = _domain_of(dangling)
        forbidden = [t for t in all_after_tools if _domain_of(t) == dangling_domain]
        priority_ok = len(forbidden) == 0
        priority_reason = "respected cancel" if priority_ok else f"ignored cancel ({forbidden})"
    elif itype == "tool_correction":
        priority_ok = dangling in all_after_tools
        priority_reason = "re-called with correction" if priority_ok else "no re-call after correction"
    else:
        return {"passed": None, "reason": f"unknown itype: {itype}"}

    passed = base_pass and priority_ok
    base_label = "tool+timing OK" if base_pass else f"tool={exp.get('passed')} timing={timing.get('passed')}"
    reason = f"base[{base_label}] + priority[{priority_reason}]"

    # 6-class attribution (shared with reactive / speech) — used for the unified 388-task confusion matrix
    attribution = classify_errors(trace, task) if not passed else {"errors": [], "error_types": {}}

    return {
        "passed": passed,
        "base_pass": base_pass,
        "priority_pass": priority_ok,
        "reason": reason,
        "itype": itype,
        "attribution": attribution,
    }


def evaluate_tool_dir(task_dir: Path, trace_dir: Path) -> dict:
    """Run priority-aware evaluation on every task under the tool subdirectory.

    Returns {
        "by_variant": {variant: {pass, total}},
        "attribution_counts": {error_type: count},  # aggregated 6-class attribution
    }
    """
    by_variant = {}
    attribution_counts = {}
    print(f"--- tool-phase interruption: {trace_dir} ---")
    for tf in sorted(task_dir.glob("*.json")):
        try:
            task = json.loads(tf.read_text(encoding="utf-8"))
        except Exception:
            continue
        itype = task.get("interruption_type", "unknown")
        tid = task.get("task_id", tf.stem)
        trace_file = trace_dir / tf.name
        by_variant.setdefault(itype, {"pass": 0, "total": 0})
        if not trace_file.exists():
            by_variant[itype]["total"] += 1
            print(f"  {tid}: ❌ MISSING trace")
            continue
        trace = json.loads(trace_file.read_text(encoding="utf-8"))
        res = evaluate_tool_trace(trace, task)
        by_variant[itype]["total"] += 1
        if res["passed"] is True:
            by_variant[itype]["pass"] += 1
            mark = "✅"
        elif res["passed"] is False:
            mark = "❌"
        else:
            mark = "⚠"
        print(f"  {tid}: {mark} {res['reason']}")
        # Accumulate the 6-class attribution
        for et, cnt in (res.get("attribution", {}).get("error_types") or {}).items():
            attribution_counts[et] = attribution_counts.get(et, 0) + cnt
    return {"by_variant": by_variant, "attribution_counts": attribution_counts}


# ---------- main entry ----------

def main():
    import argparse
    ap = argparse.ArgumentParser(description="Interruption evaluator (speech + tool)")
    ap.add_argument("task_dir", help="Task root, expected to contain speech/ and/or tool/ subdirs")
    ap.add_argument("trace_dir", help="Trace root, with same speech/ tool/ layout")
    args = ap.parse_args()

    task_root = Path(args.task_dir)
    trace_root = Path(args.trace_dir)

    speech_task = task_root / "speech"
    speech_trace = trace_root / "speech"
    tool_task = task_root / "tool"
    tool_trace = trace_root / "tool"

    print("=" * 80)
    print(f"Interruption evaluation — {trace_root}")
    print("=" * 80)

    # ---- speech ----
    if speech_task.is_dir() and speech_trace.is_dir():
        print("\n>>> SPEECH interruption (correction / cancellation / redirection)")
        evaluate_directory(str(speech_trace), "*.json", task_dir=str(speech_task))
    else:
        print(f"\n[skip] speech: {speech_task} or {speech_trace} not found")

    # ---- tool ----
    if tool_task.is_dir() and tool_trace.is_dir():
        print("\n>>> TOOL-phase interruption (priority-aware)")
        tool_result = evaluate_tool_dir(tool_task, tool_trace)
        by_variant = tool_result["by_variant"]
        attribution_counts = tool_result["attribution_counts"]

        print()
        print(f"{'Variant':<40} {'Pass':>10} {'Rate':>8}")
        print("-" * 60)
        for v, d in by_variant.items():
            rate = (100.0 * d["pass"] / d["total"]) if d["total"] else 0.0
            print(f"{v:<40} {d['pass']:>3}/{d['total']:<3}   {rate:>6.1f}%")
        total_pass = sum(d["pass"] for d in by_variant.values())
        total = sum(d["total"] for d in by_variant.values())
        print("-" * 60)
        if total:
            print(f"{'Tool interruption (priority-aware)':<40} {total_pass:>3}/{total:<3}   {100.0*total_pass/total:>6.1f}%")

        # 6-class attribution (labels shared with reactive / speech for a cross-subset confusion matrix)
        if attribution_counts:
            ORDER = ["entity_mishearing", "numerical_id_error",
                     "missing_call", "unexpected_call", "premature_call", "parameter_reasoning"]
            print("\n6-class attribution (tool subset):")
            for et in ORDER:
                if et in attribution_counts:
                    print(f"  {et:<24} {attribution_counts[et]:>4}")
            for et in sorted(attribution_counts):
                if et not in ORDER:
                    print(f"  {et:<24} {attribution_counts[et]:>4}")
    else:
        print(f"\n[skip] tool: {tool_task} or {tool_trace} not found")


if __name__ == "__main__":
    main()
