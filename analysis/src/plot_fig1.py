"""Fig 1 - Teaser (revised for 3-OpenAI study).

Left panel : Pass rate of the 3 voice checkpoints (gpt-realtime-1.5 / gpt-realtime
             / gpt-realtime-mini) plus the gpt-realtime text baseline as a
             ceiling reference. All on the same 520-task set (no crashes).
Right panel: Nested donut — failure composition of gpt-realtime-1.5 (best voice
             checkpoint). Inner ring = Voice vs Tool-use; outer ring = 8
             heuristic subcategories.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import load_all, nice_model_name

FIG_DIR = Path(__file__).resolve().parent.parent / "figures"

BEST_VOICE_MODEL = "openai_gpt-realtime-1.5"

# (model_id, display, color)
LEFT_MODELS = [
    ("openai_gpt-realtime_text", "gpt-realtime (text ceiling)", "#2E7D32"),
    ("openai_gpt-realtime-1.5", "gpt-realtime-1.5 (voice)", "#1565C0"),
    ("openai_gpt-realtime", "gpt-realtime (voice)", "#1976D2"),
    ("openai_gpt-realtime-mini", "gpt-realtime-mini (voice)", "#42A5F5"),
]

VOICE_SUBS = ["Entity mishearing", "Numerical/ID", "Streaming commitment", "Interruption state"]
TOOL_SUBS = ["Missing", "Unexpected", "Premature", "Parameter"]
VOICE_COLORS = ["#1565C0", "#1976D2", "#1E88E5", "#42A5F5"]
TOOL_COLORS = ["#E65100", "#EF6C00", "#FB8C00", "#FFA726"]


def classify_failure(row) -> str:
    subset = row["subset"]
    if subset == "interruption":
        return "Streaming commitment"
    if subset in ("v31_tool_phase", "v31_extra"):
        return "Interruption state"
    primary = row["primary_error"]
    if primary == "asr_error":
        return "Numerical/ID" if row["is_id_like"] else "Entity mishearing"
    if primary == "missing_call":
        return "Missing"
    if primary == "premature_call":
        return "Premature"
    if primary == "param_error":
        return "Parameter"
    if primary in ("unexpected_call", "wrong_tool"):
        return "Unexpected"
    return "Other"


def left_panel_data(df: pd.DataFrame):
    run1 = df[(df["run"] == "run1") & (~df["is_crashed"])]
    rows = []
    for model, label, color in LEFT_MODELS:
        g = run1[run1["model"] == model]
        rows.append({
            "model": model, "label": label, "color": color,
            "n": len(g),
            "pass_rate": g["passed"].mean() * 100 if len(g) else 0.0,
        })
    return pd.DataFrame(rows)


def best_model_failure_counts(df: pd.DataFrame):
    run1 = df[(df["model"] == BEST_VOICE_MODEL) & (df["run"] == "run1") & (~df["is_crashed"])]
    fails = run1[~run1["passed"]].copy()
    fails["bucket"] = fails.apply(classify_failure, axis=1)
    counts = fails["bucket"].value_counts()
    voice_counts = {k: int(counts.get(k, 0)) for k in VOICE_SUBS}
    tool_counts = {k: int(counts.get(k, 0)) for k in TOOL_SUBS}
    other = int(counts.get("Other", 0))
    if other:
        tool_counts["Unexpected"] += other
    return voice_counts, tool_counts, len(fails), len(run1)


def main():
    df = load_all()
    FIG_DIR.mkdir(parents=True, exist_ok=True)

    fig = plt.figure(figsize=(13, 5.0), dpi=140)
    gs = fig.add_gridspec(1, 2, width_ratios=[1.0, 1.1], wspace=0.25)
    ax_left = fig.add_subplot(gs[0, 0])
    ax_right = fig.add_subplot(gs[0, 1])

    # ============ Left: voice bar + text ceiling ============
    data = left_panel_data(df)
    ypos = np.arange(len(data))[::-1]  # top = best
    bars = ax_left.barh(ypos, data["pass_rate"], color=data["color"],
                        edgecolor="black", linewidth=0.4, height=0.6)
    for y, row in zip(ypos, data.itertuples()):
        ax_left.text(row.pass_rate + 1.0, y, f"{row.pass_rate:.1f}%  (n={row.n})",
                     va="center", fontsize=9)
        if row.model == BEST_VOICE_MODEL:
            bars[list(data["model"]).index(row.model)].set_edgecolor("#B30000")
            bars[list(data["model"]).index(row.model)].set_linewidth(1.5)
    ax_left.set_yticks(ypos)
    ax_left.set_yticklabels(data["label"], fontsize=9)
    ax_left.set_xlabel("Pass rate on 520-task benchmark (%)", fontsize=10)
    ax_left.set_xlim(0, max(data["pass_rate"]) * 1.35 + 5)
    ax_left.grid(axis="x", alpha=0.3)
    # headline gap arrow between text ceiling and best voice
    gap = data.iloc[0]["pass_rate"] - data.iloc[1]["pass_rate"]
    ax_left.annotate(
        f"voice–text gap:\n−{gap:.1f}pp",
        xy=(data.iloc[1]["pass_rate"], 2),
        xytext=(data.iloc[0]["pass_rate"] + 8, 2.0),
        fontsize=8.5, color="#B30000", ha="left", va="center",
        arrowprops=dict(arrowstyle="->", color="#B30000", lw=1.0),
    )
    ax_left.set_title(
        "(a) gpt-realtime family on audio tool-calling benchmark\n(520 matched tasks; text baseline = input_mode=\"text\" ceiling)",
        fontsize=10,
    )

    # ============ Right: nested donut ============
    voice_counts, tool_counts, total_fail, n_valid = best_model_failure_counts(df)

    inner_labels = ["Voice errors", "Tool-use errors"]
    inner_values = [sum(voice_counts.values()), sum(tool_counts.values())]
    inner_colors = ["#1565C0", "#E65100"]

    outer_labels = list(voice_counts.keys()) + list(tool_counts.keys())
    outer_values = list(voice_counts.values()) + list(tool_counts.values())
    outer_colors = VOICE_COLORS + TOOL_COLORS
    total = sum(inner_values)

    wedges_in, _ = ax_right.pie(
        inner_values, radius=0.62,
        colors=inner_colors,
        wedgeprops=dict(width=0.26, edgecolor="white"),
        startangle=90, counterclock=False,
    )
    for wedge, val, label in zip(wedges_in, inner_values, inner_labels):
        ang = (wedge.theta2 + wedge.theta1) / 2
        x = 0.31 * np.cos(np.deg2rad(ang))
        y = 0.31 * np.sin(np.deg2rad(ang))
        ax_right.text(x, y, f"{label}\n{val} ({val/total*100:.0f}%)",
                      ha="center", va="center", fontsize=8.5, color="white", fontweight="bold")

    wedges_out, _ = ax_right.pie(
        outer_values, radius=0.95,
        colors=outer_colors,
        wedgeprops=dict(width=0.32, edgecolor="white"),
        startangle=90, counterclock=False,
    )
    for wedge, val, label in zip(wedges_out, outer_values, outer_labels):
        if val == 0:
            continue
        ang = (wedge.theta2 + wedge.theta1) / 2
        x = 0.79 * np.cos(np.deg2rad(ang))
        y = 0.79 * np.sin(np.deg2rad(ang))
        pct = val / total * 100
        if pct >= 5:
            ax_right.text(x, y, f"{label}\n{val} ({pct:.0f}%)",
                          ha="center", va="center", fontsize=7.5, color="white")
        else:
            x2 = 1.18 * np.cos(np.deg2rad(ang))
            y2 = 1.18 * np.sin(np.deg2rad(ang))
            ax_right.annotate(f"{label}  {val} ({pct:.0f}%)",
                              xy=(x, y), xytext=(x2, y2),
                              fontsize=7, ha="center",
                              arrowprops=dict(arrowstyle="-", color="gray", lw=0.5))

    ax_right.set_title(
        f"(b) Failure composition of gpt-realtime-1.5\n(best voice checkpoint; {total_fail} failed / {n_valid} valid tasks)",
        fontsize=10,
    )

    out = FIG_DIR / "fig1_teaser.pdf"
    fig.savefig(out, bbox_inches="tight")
    fig.savefig(out.with_suffix(".png"), dpi=180, bbox_inches="tight")
    print(f"Saved: {out}")

    print("\nLeft panel data:")
    print(data[["label", "n", "pass_rate"]].round(2).to_string())
    print(f"\nRight panel: Voice {sum(voice_counts.values())} / Tool {sum(tool_counts.values())} / Total {total_fail} fails")
    print("  Voice:", voice_counts)
    print("  Tool :", tool_counts)


if __name__ == "__main__":
    main()
