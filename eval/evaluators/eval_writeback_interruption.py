#!/usr/bin/env python3
"""
Write back evaluation field for interruption/tool traces (evaluate_interruption.py
only prints results for tool-phase, doesn't persist).

Usage:
    python3 eval/evaluators/eval_writeback_interruption.py <task_dir> <trace_dir>

Speech is already handled by evaluate_traces.evaluate_directory (writes back).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from evaluate_interruption import evaluate_tool_trace


def writeback(task_dir: Path, trace_dir: Path):
    written = 0
    for tf in sorted(task_dir.glob("*.json")):
        trace_file = trace_dir / tf.name
        if not trace_file.exists():
            continue
        try:
            task = json.loads(tf.read_text())
            trace = json.loads(trace_file.read_text())
        except Exception as e:
            print(f"  skip {tf.name}: {e}")
            continue
        result = evaluate_tool_trace(trace, task)
        # Persist evaluation
        trace["evaluation"] = {
            "passed": result.get("passed"),
            "reason": result.get("reason", ""),
            "attribution": result.get("attribution", {}),
        }
        with open(trace_file, "w") as fh:
            json.dump(trace, fh, ensure_ascii=False, indent=2)
        written += 1
    return written


def main():
    if len(sys.argv) != 3:
        print(f"Usage: {sys.argv[0]} <task_dir> <trace_dir>")
        sys.exit(1)
    task_root = Path(sys.argv[1])
    trace_root = Path(sys.argv[2])

    tool_task = task_root / "tool"
    tool_trace = trace_root / "tool"
    if tool_task.is_dir() and tool_trace.is_dir():
        n = writeback(tool_task, tool_trace)
        print(f"tool: wrote {n} trace evals")
    else:
        print(f"[skip] {tool_task} or {tool_trace} not found")


if __name__ == "__main__":
    main()
