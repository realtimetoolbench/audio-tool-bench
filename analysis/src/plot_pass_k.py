"""Table 1 + Fig 5 - pass@k reliability.

Table 1: pass@1 / pass@3 / pass^3 for the 3 OpenAI voice models (the only
models with 3 runs currently). Saved as CSV + LaTeX.

Fig 5: per-task pass^3 histogram — how many of the 3 runs each task passed.
Shows whether failures are deterministic (bimodal 0/3) or stochastic (spread).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import load_all, nice_model_name

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"
TBL_DIR = Path(__file__).resolve().parent.parent / "tables"

PASS_K_MODELS = [
    ("openai_gpt-realtime-1.5", "gpt-realtime-1.5", "#1f77b4"),
    ("openai_gpt-realtime", "gpt-realtime", "#ff7f0e"),
    ("openai_gpt-realtime-mini", "gpt-realtime-mini", "#7f7f7f"),
]

RUNS = ["run1", "run2", "run3"]


def per_task_passes(df: pd.DataFrame, model: str):
    """Return DataFrame indexed by task_id: each column is pass (bool) per run.

    A task is treated as passed in a run iff the run produced a valid trace
    (is_crashed=False) AND evaluation.passed=True. A run crashed on a task
    counts as failed for that run (conservative)."""
    sub = df[(df["model"] == model) & df["run"].isin(RUNS)].copy()
    sub["effective_pass"] = sub["passed"] & (~sub["is_crashed"])
    wide = sub.pivot_table(index=["subset", "task_id"], columns="run", values="effective_pass", aggfunc="first")
    # keep only tasks present in all 3 runs
    wide = wide.dropna()
    return wide


def compute_passk(wide: pd.DataFrame) -> dict:
    runs = wide.shape[1]
    passes = wide.sum(axis=1)  # count of True per task
    n = len(wide)
    pass_at_1 = wide[RUNS[0]].mean() * 100
    pass_at_k = (passes >= 1).mean() * 100  # pass@3 = any of 3 passes
    pass_pow_k = (passes == runs).mean() * 100  # pass^3 = all 3 pass
    return {
        "n_tasks": n,
        "pass@1 (single run)": pass_at_1,
        "pass@3 (any of 3)": pass_at_k,
        "pass^3 (all 3)": pass_pow_k,
        "reliability_loss_pct": (1 - pass_pow_k / max(pass_at_1, 1e-9)) * 100,
    }


def make_table(df: pd.DataFrame):
    rows = []
    for model, label, _color in PASS_K_MODELS:
        wide = per_task_passes(df, model)
        stats = compute_passk(wide)
        rows.append({"model": label, **stats})
    t = pd.DataFrame(rows)
    t = t.set_index("model")
    TBL_DIR.mkdir(parents=True, exist_ok=True)
    t.to_csv(TBL_DIR / "table1_pass_k.csv")
    # LaTeX version
    latex = t[["n_tasks", "pass@1 (single run)", "pass@3 (any of 3)", "pass^3 (all 3)", "reliability_loss_pct"]].round(1).to_latex(
        column_format="lrrrrr",
        float_format="%.1f",
    )
    (TBL_DIR / "table1_pass_k.tex").write_text(latex)
    print("\nTable 1 (pass@k, k=3 runs):")
    print(t.round(2).to_string())
    return t


def plot_histogram(df: pd.DataFrame):
    FIG_DIR.mkdir(parents=True, exist_ok=True)
    fig, axes = plt.subplots(1, len(PASS_K_MODELS), figsize=(13, 3.6), dpi=140, sharey=True)
    for ax, (model, label, color) in zip(axes, PASS_K_MODELS):
        wide = per_task_passes(df, model)
        passes = wide.sum(axis=1).astype(int)
        counts = passes.value_counts().reindex([0, 1, 2, 3], fill_value=0)
        bars = ax.bar([0, 1, 2, 3], counts.values, color=color, edgecolor="black", linewidth=0.5)
        for b, v in zip(bars, counts.values):
            ax.text(b.get_x() + b.get_width() / 2, b.get_height() + 4, str(int(v)), ha="center", fontsize=9)
        ax.set_xticks([0, 1, 2, 3])
        ax.set_xticklabels(["0/3", "1/3", "2/3", "3/3"])
        ax.set_xlabel("Runs passed (out of 3)")
        total = counts.sum()
        stoch = counts[[1, 2]].sum()
        stoch_pct = stoch / total * 100 if total else 0
        ax.set_title(f"{label}\n(n={total} tasks; stochastic = {stoch_pct:.1f}%)", fontsize=10)
        ax.grid(axis="y", alpha=0.3)
    axes[0].set_ylabel("Number of tasks")
    fig.suptitle("Per-task pass^3 distribution: how many of the 3 runs passed each task", fontsize=11, y=1.03)
    plt.tight_layout()
    out = FIG_DIR / "fig5_pass3_histogram.pdf"
    out_png = out.with_suffix(".png")
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out_png, dpi=180, bbox_inches="tight")
    print(f"Saved: {out}")
    print(f"Saved: {out_png}")


def main():
    df = load_all()
    make_table(df)
    plot_histogram(df)


if __name__ == "__main__":
    main()
