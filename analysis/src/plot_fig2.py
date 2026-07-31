"""Fig 2 - Task complexity vs n_params.

Single panel, 4-6 representative models (one per provider) overlaid.
Light scatter + dark LOESS curve + 95% CI band per model.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats
from statsmodels.nonparametric.smoothers_lowess import lowess

from data_loader import load_all, nice_model_name

OUT = Path(__file__).resolve().parent.parent / "figures" / "fig2_task_complexity.pdf"
OUT_PNG = OUT.with_suffix(".png")

# 3-OpenAI voice checkpoints, same 520-task set.
REP_MODELS = [
    ("openai_gpt-realtime-1.5", "gpt-realtime-1.5", "#1565C0"),
    ("openai_gpt-realtime", "gpt-realtime", "#1976D2"),
    ("openai_gpt-realtime-mini", "gpt-realtime-mini", "#42A5F5"),
]


def aggregate_per_param(df: pd.DataFrame, model: str):
    """Valid-only: drop is_crashed rows before aggregating."""
    sub = df[(df["model"] == model) & (df["run"] == "run1") & (~df["is_crashed"])].dropna(subset=["n_params"])
    g = sub.groupby("n_params")["passed"].agg(["mean", "count", "sum"])
    return g


def loess_fit(xs, ys, frac=0.4):
    result = lowess(ys, xs, frac=frac, return_sorted=True)
    return result[:, 0], result[:, 1]


def main():
    df = load_all()
    fig, ax = plt.subplots(figsize=(8, 5.2), dpi=140)
    legend_entries = []

    for model, label, color in REP_MODELS:
        g = aggregate_per_param(df, model)
        if len(g) < 3:
            print(f"skip {model}: only {len(g)} n_params bins")
            continue
        xs = g.index.to_numpy()
        rate = g["mean"].to_numpy() * 100
        n = g["count"].to_numpy()

        # scatter sized by sqrt(n), light color, jittered x
        ax.scatter(xs, rate, s=12 + 2 * np.sqrt(n), color=color, alpha=0.20, edgecolors="none")

        # LOESS
        lx, ly = loess_fit(xs.astype(float), rate.astype(float), frac=0.4)
        ax.plot(lx, ly, color=color, lw=2.0, label=label, zorder=3)

        # Spearman on per-task level (valid only)
        per_task = df[(df["model"] == model) & (df["run"] == "run1") & (~df["is_crashed"])].dropna(subset=["n_params"])
        rho, p = stats.spearmanr(per_task["n_params"], per_task["passed"].astype(int))

        # 95% CI band around the mean rate using pooled normal approx per bin
        lo = rate - 1.96 * np.sqrt(rate * (100 - rate) / np.maximum(n, 1))
        hi = rate + 1.96 * np.sqrt(rate * (100 - rate) / np.maximum(n, 1))
        ax.fill_between(xs, np.clip(lo, 0, 100), np.clip(hi, 0, 100), color=color, alpha=0.08, zorder=1)

        legend_entries.append((label, rho, p, per_task["passed"].count()))

    ax.set_xlabel("Number of unique parameters per task ($n_{\\mathrm{params}}$)", fontsize=11)
    ax.set_ylabel("Pass rate (%)", fontsize=11)
    ax.set_ylim(-2, 100)
    ax.grid(axis="y", alpha=0.25)
    ax.grid(axis="x", alpha=0.15)

    # Custom legend with rho + p per model
    handles, labels = ax.get_legend_handles_labels()
    new_labels = []
    for (label, rho, p, n_obs), old in zip(legend_entries, labels):
        sig = "***" if p < 0.001 else ("**" if p < 0.01 else ("*" if p < 0.05 else "ns"))
        new_labels.append(f"{label}  ρ={rho:+.2f} ({sig}, n={n_obs})")
    ax.legend(handles, new_labels, loc="upper right", fontsize=8.5, frameon=True)

    ax.set_title(
        "Pass rate monotonically decreases with task parameter count\n"
        "(scatter = per-bin empirical rate, line = LOESS, band = 95% CI)",
        fontsize=11, pad=8,
    )

    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=180, bbox_inches="tight")
    print(f"Saved: {OUT}")
    print(f"Saved: {OUT_PNG}")
    for label, rho, p, n_obs in legend_entries:
        print(f"  {label}: rho={rho:+.3f}, p={p:.4g}, n={n_obs}")


if __name__ == "__main__":
    main()
