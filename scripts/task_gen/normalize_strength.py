#!/usr/bin/env python3
"""
Normalize proactive task strength field from v7 legacy alias output to v2 names.

Reactive generator's --style proactive_medium / proactive_weak emit
strength = "ambiguous" / "negative" (v7 names), but downstream evaluator
(eval/evaluators/evaluate_traces.py) and TTS cache
(eval/audio/tts_cache.py:86 weak special case) expect v2 names
"medium" / "weak". This one-shot script rewrites both task.strength and
task.intent.strength so the rest of the pipeline sees consistent v2 schema.

Usage:
    python scripts/task_gen/normalize_strength.py <task_dir>

Idempotent: tasks already using medium/weak are left unchanged.
"""
import json
import sys
from pathlib import Path

V7_TO_V2 = {"ambiguous": "medium", "negative": "weak"}


def normalize_file(path: Path) -> bool:
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    changed = False

    top = data.get("strength")
    if top in V7_TO_V2:
        data["strength"] = V7_TO_V2[top]
        changed = True

    intent = data.get("intent")
    if isinstance(intent, dict):
        nested = intent.get("strength")
        if nested in V7_TO_V2:
            intent["strength"] = V7_TO_V2[nested]
            changed = True

    if changed:
        with path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    return changed


def main():
    if len(sys.argv) != 2:
        print(f"Usage: {sys.argv[0]} <task_dir>", file=sys.stderr)
        sys.exit(2)

    target = Path(sys.argv[1])
    if not target.exists():
        print(f"Path not found: {target}", file=sys.stderr)
        sys.exit(1)

    files = sorted(target.rglob("*.json"))
    n_changed = 0
    for fp in files:
        if normalize_file(fp):
            n_changed += 1
    print(f"normalized {n_changed}/{len(files)} files under {target}")


if __name__ == "__main__":
    main()
