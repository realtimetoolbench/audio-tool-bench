"""Appendix figure - Interruption subscenarios across 3 voice checkpoints.

Two panels:
  (a) Speech-phase (intra-turn) interruption — n=33 tasks — broken into
      correction / cancellation / redirection from task metadata.
  (b) Tool-phase (inter-turn) interruption — n=87 = 75 v31 main + 12 extra —
      broken into tool_cancel / tool_correction / prio_no_ret / prio_late_ret /
      prio_early_ret from task metadata.intent (or subset-level fallback).

For each subscenario × model, plot pass rate with task count.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import load_all, nice_model_name, TASKS_ROOT, TASK_DIR_MAP

OUT = Path(__file__).resolve().parent.parent / "figures" / "appendix_interruption_scenarios.pdf"

MODELS = [
    ("openai_gpt-realtime-1.5", "gpt-realtime-1.5", "#1565C0"),
    ("openai_gpt-realtime", "gpt-realtime", "#1976D2"),
    ("openai_gpt-realtime-mini", "gpt-realtime-mini", "#42A5F5"),
]

INTRA_SUBS = ["correction", "cancellation", "redirection"]
INTER_SUBS = ["tool_cancel", "tool_correction", "prio_no_ret", "prio_late_ret", "prio_early_ret"]


def task_intent(subset: str, task_id: str) -> str | None:
    head, sub = TASK_DIR_MAP[subset]
    p = TASKS_ROOT / head / sub / f"{task_id}.json" if sub else TASKS_ROOT / head / f"{task_id}.json"
    if not p.exists():
        return None
    with p.open() as f:
        d = json.load(f)
    intent = d.get("intent") or d.get("interruption_type") or d.get("metadata", {}).get("intent")
    return intent


def classify_intra(intent: str | None) -> str | None:
    if not intent:
        return None
    s = str(intent).lower()
    if "correct" in s or "revis" in s:
        return "correction"
    if "cancel" in s:
        return "cancellation"
    if "redirect" in s or "switch" in s or "change" in s:
        return "redirection"
    return None


def classify_inter(intent: str | None) -> str | None:
    if not intent:
        return None
    s = str(intent).lower()
    if "tool_cancel" in s or (s.startswith("cancel") and "tool" in s):
        return "tool_cancel"
    if "tool_correct" in s or ("correct" in s and "tool" in s):
        return "tool_correction"
    if "priority" in s or "prio" in s:
        if "no" in s and "return" in s:
            return "prio_no_ret"
        if "late" in s:
            return "prio_late_ret"
        if "early" in s:
            return "prio_early_ret"
    return None


def main():
    df = load_all()
    run1 = df[(df["run"] == "run1") & (~df["is_crashed"])]

    # attach subscenario per row for intra-turn / inter-turn
    intra = run1[run1["subset"] == "interruption"].copy()
    inter = run1[run1["subset"].isin(["v31_tool_phase", "v31_extra"])].copy()

    def attach(df_sub, cls_fn):
        sc = []
        for _, r in df_sub.iterrows():
            intent = task_intent(r["subset"], r["task_id"])
            sc.append(cls_fn(intent))
        df_sub = df_sub.copy()
        df_sub["scenario"] = sc
        return df_sub

    intra = attach(intra, classify_intra)
    inter = attach(inter, classify_inter)

    print("Intra scenarios found:", intra["scenario"].value_counts(dropna=False).to_dict())
    print("Inter scenarios found:", inter["scenario"].value_counts(dropna=False).to_dict())

    # If everything is None we fall back to subset-level: put all intra under "all-intra" bucket.
    intra_counts = intra["scenario"].value_counts(dropna=True)
    inter_counts = inter["scenario"].value_counts(dropna=True)
    use_intra_breakdown = len(intra_counts) >= 2
    use_inter_breakdown = len(inter_counts) >= 2

    intra_subs_active = [s for s in INTRA_SUBS if intra_counts.get(s, 0) > 0] if use_intra_breakdown else ["all"]
    inter_subs_active = [s for s in INTER_SUBS if inter_counts.get(s, 0) > 0] if use_inter_breakdown else ["all"]

    fig, axes = plt.subplots(1, 2, figsize=(14, 4.8), dpi=140, gridspec_kw={"width_ratios": [1.0, 1.6]})
    ax_a, ax_b = axes

    def plot_grouped(ax, data, subs_active, title, total_tasks):
        x = np.arange(len(subs_active))
        width = 0.25
        for k, (model, label, color) in enumerate(MODELS):
            sub = data[data["model"] == model]
            rates, ns = [], []
            for s in subs_active:
                if s == "all":
                    bucket = sub
                else:
                    bucket = sub[sub["scenario"] == s]
                n = len(bucket)
                rates.append(bucket["passed"].mean() * 100 if n else 0)
                ns.append(n)
            pos = x + (k - 1) * width
            bars = ax.bar(pos, rates, width, color=color, edgecolor="black", linewidth=0.4, label=label)
            for p, r, n in zip(pos, rates, ns):
                if n:
                    ax.text(p, r + 1.5, f"{r:.0f}%\n(n={n})", ha="center", fontsize=7)
        ax.set_xticks(x)
        ax.set_xticklabels(subs_active, fontsize=9)
        ax.set_ylabel("Pass rate (%)")
        ax.set_ylim(0, 105)
        ax.grid(axis="y", alpha=0.3)
        ax.set_title(f"{title} (total {total_tasks} tasks)", fontsize=10)
        ax.legend(fontsize=8, loc="upper right")

    plot_grouped(ax_a, intra, intra_subs_active,
                 "(a) Speech-phase (intra-turn) interruption",
                 int(intra.groupby("model").size().max() if len(intra) else 0))
    plot_grouped(ax_b, inter, inter_subs_active,
                 "(b) Tool-phase (inter-turn) interruption",
                 int(inter.groupby("model").size().max() if len(inter) else 0))

    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".png"), dpi=180, bbox_inches="tight")
    print(f"Saved: {OUT}")


if __name__ == "__main__":
    main()
