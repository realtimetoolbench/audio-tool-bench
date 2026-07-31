"""Analyze intra-turn revision run vs reactive baseline.

For each of the 20 intra-turn revision tasks:
  - task has top-level `intra_turn_revision = {tool, param, pre_correction_value, post_correction_value, ...}`
  - trace contains tool calls executed by the voice model
  - we classify the run into one of:
      * pass                  : the target tool was called with post_correction_value
      * streaming_commitment  : the target tool was called with pre_correction_value → realtime early-commit failure
      * wrong_value           : the target tool was called with some other value
      * missing               : target tool was never called
      * pre_only_then_fixed   : both pre and post values were called — committed early but recovered

Baseline: same 20 task_ids in the reactive run (original uncorrected transcript)
          of gpt-realtime-1.5, loaded from data/traces/openai_gpt-realtime-1.5/reactive/.
"""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent.parent
TASKS_DIR = ROOT / "data" / "tasks" / "intra_turn_revision"
INTRA_TRACE_DIR = ROOT / "data" / "traces" / "openai_gpt-realtime-1.5" / "intra_turn_revision"
REACTIVE_TRACE_DIR = ROOT / "data" / "traces" / "openai_gpt-realtime-1.5" / "reactive"


def extract_tool_calls(trace: dict) -> list[dict]:
    """Return [{tool, args}, ...] in order from a trace.

    Trace schema: steps[].tool_executions[] with keys
      {tool_call_id, tool_name, arguments, result, latency_ms}."""
    calls = []
    for step in trace.get("steps", []) or []:
        for te in step.get("tool_executions", []) or []:
            name = te.get("tool_name") or te.get("tool") or te.get("name")
            args = te.get("arguments") or te.get("args") or {}
            if isinstance(args, str):
                try:
                    args = json.loads(args)
                except Exception:
                    args = {}
            if name:
                calls.append({"tool": name, "args": args})
    return calls


def classify_trace(task: dict, trace: dict) -> tuple[str, dict]:
    info = task["intra_turn_revision"]
    target_tool = info["tool"]
    param = info["param"]
    pre = info["pre_correction_value"]
    post = info["post_correction_value"]

    calls = extract_tool_calls(trace)
    target_calls = [c for c in calls if c["tool"] == target_tool]
    if not target_calls:
        return "missing", {"n_target_calls": 0}

    values = [str(c["args"].get(param, "")).strip() for c in target_calls]
    hit_pre = any(v == pre for v in values)
    hit_post = any(v == post for v in values)
    all_pre = values and all(v == pre for v in values)
    first_pre = values and values[0] == pre

    detail = {"n_target_calls": len(target_calls), "values": values, "pre": pre, "post": post}
    # Any call with post value and no pre → pass (also verify evaluation passed)
    passed_eval = bool(trace.get("evaluation", {}).get("passed"))
    if passed_eval and hit_post and not hit_pre:
        return "pass", detail
    if all_pre:
        return "streaming_commitment", detail
    if first_pre and hit_post:
        return "pre_only_then_fixed", detail
    if hit_pre and not hit_post:
        return "streaming_commitment", detail
    if not hit_pre and not hit_post:
        return "wrong_value", detail
    if hit_post and not passed_eval:
        # got the right param but still failed some later check
        return "other_fail", detail
    return "other_fail", detail


def main():
    tasks = {}
    for p in sorted(TASKS_DIR.glob("gen_*.json")):
        with p.open() as f:
            tasks[p.stem] = json.load(f)
    print(f"Loaded {len(tasks)} intra-turn tasks.\n")

    # --- intra-turn run ---
    if not INTRA_TRACE_DIR.is_dir():
        print(f"No trace dir yet at {INTRA_TRACE_DIR} — run is not finished.")
        return

    rows = []
    for tid, task in tasks.items():
        trace_path = INTRA_TRACE_DIR / f"{tid}.json"
        if not trace_path.exists():
            rows.append({"task_id": tid, "bucket": "no_trace", "values": None})
            continue
        with trace_path.open() as f:
            trace = json.load(f)
        bucket, detail = classify_trace(task, trace)
        passed_eval = bool(trace.get("evaluation", {}).get("passed"))
        rows.append({
            "task_id": tid,
            "bucket": bucket,
            "evaluation_passed": passed_eval,
            "target_tool": task["intra_turn_revision"]["tool"],
            "param": task["intra_turn_revision"]["param"],
            "pre": task["intra_turn_revision"]["pre_correction_value"],
            "post": task["intra_turn_revision"]["post_correction_value"],
            "calls": detail.get("values"),
        })

    print("=" * 90)
    print(f"{'task_id':<18} {'bucket':<24} {'eval':<6} {'pre → post':<30} calls")
    print("-" * 90)
    for r in rows:
        pre_post = f"{r.get('pre','-')} → {r.get('post','-')}"
        print(f"{r['task_id']:<18} {r['bucket']:<24} {str(r.get('evaluation_passed','')):5s} {pre_post:<30} {r.get('calls')}")

    counts = Counter(r["bucket"] for r in rows)
    n_with_trace = sum(1 for r in rows if r["bucket"] != "no_trace")
    print()
    print("Bucket summary (intra-turn revision, 20 tasks):")
    for k, v in counts.most_common():
        pct = v / len(rows) * 100
        print(f"  {k:<24} {v:3d}  ({pct:4.1f}%)")

    # --- reactive baseline on the same 20 task_ids ---
    if not REACTIVE_TRACE_DIR.is_dir():
        print("\n(no reactive trace dir — skip baseline)")
        return
    print("\n=== Reactive baseline (same 20 task_ids, original un-corrected transcripts) ===")
    base_pass = 0
    base_n = 0
    for tid in tasks:
        bp = REACTIVE_TRACE_DIR / f"{tid}.json"
        if not bp.exists():
            continue
        with bp.open() as f:
            bt = json.load(f)
        base_n += 1
        if bt.get("evaluation", {}).get("passed"):
            base_pass += 1
    print(f"  Reactive baseline pass: {base_pass}/{base_n} = {base_pass/base_n*100:.1f}%")

    intra_pass = counts.get("pass", 0)
    print(f"  Intra-turn revision pass: {intra_pass}/{n_with_trace} = {intra_pass/max(n_with_trace,1)*100:.1f}%")
    print(f"  Δ = {(intra_pass/max(n_with_trace,1) - base_pass/max(base_n,1))*100:+.1f}pp")
    print(f"  Streaming commitment failures: {counts.get('streaming_commitment',0)} "
          f"({counts.get('streaming_commitment',0)/max(n_with_trace,1)*100:.1f}%)")


if __name__ == "__main__":
    main()
