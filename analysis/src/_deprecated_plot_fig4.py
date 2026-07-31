"""Fig 4 - Cross-category rank correlation heatmap.

Left panel: 4x4 Spearman heatmap of per-model pass rates across categories.
Each cell annotates (rho, n) where n is the number of models with adequate
coverage (>=10 evaluated tasks in both categories). Cells with n<3 are grayed.

Right panel: the underlying pass-rate matrix (category x model) for reference.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

from data_loader import load_all, nice_model_name, provider_of

OUT = Path(__file__).resolve().parent.parent / "figures" / "fig4_rank_correlation.pdf"
OUT_PNG = OUT.with_suffix(".png")

CATEGORIES = ["Reactive", "Proactive", "Intra-turn", "Inter-turn"]
MIN_TASKS = 10


EXCLUDED_MODELS = {"glm_glm-realtime"}  # too many crashed sessions


def compute_pass_rate_matrix(df: pd.DataFrame) -> pd.DataFrame:
    """Return DataFrame indexed by model, columns=category, values=pass rate.
    Only uses run1, only valid (non-crashed) traces. Cells with <MIN_TASKS become NaN."""
    run1 = df[(df["run"] == "run1") & (~df["is_crashed"])]
    voice = run1[~run1["model"].str.endswith("_text") & ~run1["model"].str.startswith("openai-cascade_")]
    voice = voice[~voice["model"].isin(EXCLUDED_MODELS)]
    rows = {}
    for model, g in voice.groupby("model"):
        row = {}
        for cat in CATEGORIES:
            sub = g[g["category"] == cat]
            if len(sub) >= MIN_TASKS:
                row[cat] = sub["passed"].mean() * 100
            else:
                row[cat] = np.nan
        rows[model] = row
    return pd.DataFrame(rows).T[CATEGORIES]


def compute_corr_matrix(mat: pd.DataFrame):
    n_cats = len(CATEGORIES)
    corr = np.full((n_cats, n_cats), np.nan)
    nobs = np.zeros((n_cats, n_cats), dtype=int)
    for i, ci in enumerate(CATEGORIES):
        for j, cj in enumerate(CATEGORIES):
            if i == j:
                sub = mat[[ci]].dropna()
                nobs[i, j] = len(sub)
                corr[i, j] = 1.0 if len(sub) >= 3 else np.nan
                continue
            sub = mat[[ci, cj]].dropna()
            nobs[i, j] = len(sub)
            if len(sub) >= 3:
                res = stats.spearmanr(sub[ci].to_numpy(), sub[cj].to_numpy())
                corr[i, j] = float(res.statistic)
    return corr, nobs


def main():
    df = load_all()
    mat = compute_pass_rate_matrix(df)
    mat = mat.sort_values("Reactive", ascending=False)
    # Pretty names for rows
    mat.index = [nice_model_name(m) for m in mat.index]

    corr, nobs = compute_corr_matrix(mat)

    fig = plt.figure(figsize=(13, 5.5), dpi=140)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.6], wspace=0.3)
    ax1 = fig.add_subplot(gs[0, 0])
    ax2 = fig.add_subplot(gs[0, 1])

    # --- Panel 1: Spearman heatmap ---
    masked = np.ma.masked_invalid(corr)
    im = ax1.imshow(masked, cmap="RdBu_r", vmin=-1, vmax=1, aspect="equal")
    for i in range(len(CATEGORIES)):
        for j in range(len(CATEGORIES)):
            v = corr[i, j]
            n = nobs[i, j]
            if np.isnan(v):
                ax1.text(j, i, "—", ha="center", va="center", color="gray", fontsize=10)
            else:
                color = "white" if abs(v) > 0.5 else "black"
                ax1.text(j, i, f"{v:+.2f}\n(n={n})", ha="center", va="center", color=color, fontsize=9)
    ax1.set_xticks(range(len(CATEGORIES)))
    ax1.set_yticks(range(len(CATEGORIES)))
    ax1.set_xticklabels(CATEGORIES, rotation=25, ha="right")
    ax1.set_yticklabels(CATEGORIES)
    ax1.set_title("Spearman rank correlation between categories\n(across models with coverage ≥10 tasks)", fontsize=10)
    cbar = fig.colorbar(im, ax=ax1, fraction=0.046, pad=0.04)
    cbar.set_label("ρ", rotation=0, labelpad=10)

    # --- Panel 2: model × category pass rate matrix ---
    pr_matrix = mat.copy()
    im2 = ax2.imshow(pr_matrix.values, cmap="YlGnBu", aspect="auto", vmin=0, vmax=100)
    for i in range(pr_matrix.shape[0]):
        for j in range(pr_matrix.shape[1]):
            v = pr_matrix.iloc[i, j]
            if pd.isna(v):
                ax2.text(j, i, "—", ha="center", va="center", color="gray", fontsize=8)
            else:
                color = "white" if v > 55 else "black"
                ax2.text(j, i, f"{v:.0f}", ha="center", va="center", color=color, fontsize=8)
    ax2.set_xticks(range(len(CATEGORIES)))
    ax2.set_yticks(range(len(pr_matrix.index)))
    ax2.set_xticklabels(CATEGORIES, rotation=25, ha="right")
    ax2.set_yticklabels(pr_matrix.index, fontsize=9)
    ax2.set_title("Per-model pass rate by category (%)\n(input to the correlation matrix)", fontsize=10)
    cbar2 = fig.colorbar(im2, ax=ax2, fraction=0.03, pad=0.02)
    cbar2.set_label("Pass rate (%)", labelpad=6)

    fig.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=180, bbox_inches="tight")
    print(f"Saved: {OUT}")
    print(f"Saved: {OUT_PNG}")
    print("\nPass rate matrix:")
    print(mat.round(1).to_string())
    print("\nSpearman ρ matrix (row=row cat, col=col cat, NaN if n<3):")
    import pandas as _pd
    print(_pd.DataFrame(corr, index=CATEGORIES, columns=CATEGORIES).round(2).to_string())
    print("\nn observations matrix:")
    print(_pd.DataFrame(nobs, index=CATEGORIES, columns=CATEGORIES).to_string())


if __name__ == "__main__":
    main()
