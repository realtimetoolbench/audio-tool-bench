"""Appendix figure - Top-15 error-prone tools.

For each tool appearing as the offending tool in an error_attribution across
the 3 voice checkpoints, count failures. Color each bar by the dominant error
type (ASR / Missing / Premature / Parameter / Unexpected).
"""
from __future__ import annotations

from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import load_all

OUT = Path(__file__).resolve().parent.parent / "figures" / "appendix_top_error_tools.pdf"

MODELS = [
    "openai_gpt-realtime-1.5",
    "openai_gpt-realtime",
    "openai_gpt-realtime-mini",
]

ERR_COLORS = {
    "asr_error": "#1565C0",
    "missing_call": "#E65100",
    "premature_call": "#FFA726",
    "param_error": "#7B1FA2",
    "unexpected_call": "#00796B",
    "wrong_tool": "#D32F2F",
}
ERR_DISPLAY = {
    "asr_error": "ASR",
    "missing_call": "Missing",
    "premature_call": "Premature",
    "param_error": "Parameter",
    "unexpected_call": "Unexpected",
    "wrong_tool": "Wrong tool",
}


def main():
    df = load_all()
    run1 = df[(df["run"] == "run1") & (~df["is_crashed"]) & (df["model"].isin(MODELS))]

    # per-tool error-type tallies
    tool_by_err = defaultdict(lambda: defaultdict(int))
    # We need to look inside error_attribution.errors list which is not in the
    # flat row; re-read trace files for failed rows.
    import json
    from pathlib import Path as _P

    repo_root = _P(__file__).resolve().parent.parent.parent

    def get_trace_path(model: str, subset: str, task_id: str, run: str) -> _P | None:
        # Same convention as data_loader.
        candidates = [repo_root / "data/traces" / model]
        # subset folder alias: reactive stays reactive, strong -> strong or strong_v2 etc.
        subset_aliases = {
            "reactive": ["reactive"],
            "strong": ["strong", "strong_v2", "proactive_strong"],
            "medium": ["medium", "medium_v2", "proactive_medium"],
            "weak": ["weak", "weak_v2", "proactive_weak"],
            "interruption": ["interruption", "interrupt_speech"],
            "v31_tool_phase": ["v31_tool_phase", "interrupt_tool"],
            "v31_extra": ["v31_extra", "interrupt_tool_extra"],
        }
        for base in candidates:
            for sub in subset_aliases.get(subset, [subset]):
                # run1 = direct subset folder; runN = runs/runN/subset
                if run == "run1":
                    p = base / sub / f"{task_id}.json"
                    if p.exists():
                        return p
                else:
                    p = base / "runs" / run / sub / f"{task_id}.json"
                    if p.exists():
                        return p
        return None

    for _, row in run1.iterrows():
        if row["passed"]:
            continue
        p = get_trace_path(row["model"], row["subset"], row["task_id"], row["run"])
        if p is None:
            continue
        try:
            with p.open() as f:
                d = json.load(f)
        except Exception:
            continue
        errs = (d.get("evaluation") or {}).get("error_attribution") or {}
        for e in errs.get("errors") or []:
            tool = e.get("tool") or "(unknown)"
            et = e.get("error_type") or "other"
            tool_by_err[tool][et] += 1

    # rank by total
    ranked = sorted(tool_by_err.items(), key=lambda kv: -sum(kv[1].values()))[:15]

    fig, ax = plt.subplots(figsize=(9, 5.5), dpi=140)
    y = np.arange(len(ranked))[::-1]
    bottoms = np.zeros(len(ranked))
    error_types_order = ["asr_error", "missing_call", "premature_call", "param_error",
                         "unexpected_call", "wrong_tool"]
    for et in error_types_order:
        widths = np.array([tool_by_err[t].get(et, 0) for t, _ in ranked])
        ax.barh(y, widths, left=bottoms, color=ERR_COLORS[et], label=ERR_DISPLAY[et],
                edgecolor="white", linewidth=0.4)
        for yi, (w, b) in enumerate(zip(widths, bottoms)):
            if w >= 3:
                ax.text(b + w / 2, y[yi], str(int(w)), ha="center", va="center",
                        color="white", fontsize=7.5, fontweight="bold")
        bottoms += widths

    # totals
    for yi, (tool, _) in enumerate(ranked):
        total = int(bottoms[yi])
        ax.text(bottoms[yi] + max(bottoms) * 0.01, y[yi], f" Σ={total}", va="center", fontsize=8)

    ax.set_yticks(y)
    ax.set_yticklabels([t for t, _ in ranked], fontsize=9)
    ax.set_xlabel("Failure count (aggregated across 3 voice checkpoints, run1)")
    ax.grid(axis="x", alpha=0.3)
    ax.legend(loc="lower right", fontsize=8, title="Error type")
    ax.set_title("Top-15 error-prone tools (colored by dominant error type)", fontsize=10, pad=6)

    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".png"), dpi=180, bbox_inches="tight")
    print(f"Saved: {OUT}")
    for tool, counts in ranked:
        print(f"  {tool:30s} {dict(counts)}")


if __name__ == "__main__":
    main()
