"""Fig 3 - Voice-gap decomposition (paired version).

Same model (gpt-realtime), two input modes, 519 matched tasks.

Two horizontal bars, left-aligned. The leftmost (gray) segment is the number
of tasks that both modes fail — these are reasoning-hard tasks where voice
cannot be blamed. Everything to the right of that segment is mode-specific
failure: for voice it's split into ASR / Realtime-streaming / Tool-use
reasoning (voice-only); for text it's just the handful of tasks voice got
right but text missed.

The visual overhang of Voice past Text = genuine voice-modality overhead.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import load_all

OUT = Path(__file__).resolve().parent.parent / "figures" / "fig3_voice_gap.pdf"
OUT_PNG = OUT.with_suffix(".png")

VOICE_MODEL = "openai_gpt-realtime"
TEXT_MODEL = "openai_gpt-realtime_text"
MODEL_LABEL = "gpt-realtime"

SHARED_COLOR = "#9E9E9E"
TOOL_COLOR = "#6A1B9A"
ASR_COLOR = "#1565C0"
STREAM_COLOR = "#EF6C00"
TEXT_ONLY_COLOR = "#2E7D32"


def classify_voice_fail(row) -> str:
    if row["subset"] in ("interruption", "v31_tool_phase", "v31_extra"):
        return "Streaming"
    if row["v_primary"] == "asr_error":
        return "ASR"
    return "Tool-reasoning"


def main():
    df = load_all()
    run1 = df[(df["run"] == "run1") & (~df["is_crashed"])]
    V = run1[run1["model"] == VOICE_MODEL][["subset", "task_id", "passed", "primary_error"]].rename(columns={"passed": "v_pass", "primary_error": "v_primary"})
    T = run1[run1["model"] == TEXT_MODEL][["subset", "task_id", "passed"]].rename(columns={"passed": "t_pass"})
    m = V.merge(T, on=["subset", "task_id"], how="inner")
    n_matched = len(m)

    fail = m[~m["v_pass"]].copy()
    fail["v_bucket"] = fail.apply(classify_voice_fail, axis=1)

    # shared voice failures (both fail)
    shared = fail[~fail["t_pass"]]
    voice_only = fail[fail["t_pass"]]
    shared_by_bucket = shared["v_bucket"].value_counts().to_dict()
    voice_only_by_bucket = voice_only["v_bucket"].value_counts().to_dict()

    n_shared_fail = len(shared)  # both fail
    n_voice_only = len(voice_only)
    n_voice_fail = len(fail)
    n_text_fail = int((~m["t_pass"]).sum())
    n_text_only = n_text_fail - n_shared_fail
    n_both_pass = int((m["t_pass"] & m["v_pass"]).sum())

    # -------- plot --------
    fig, ax = plt.subplots(figsize=(11, 3.6), dpi=140)
    bar_h = 0.55
    y_voice, y_text = 1, 0

    # Voice bar: left = shared fails (gray), right = voice-specific fails split by bucket
    left = 0
    ax.barh(y_voice, n_shared_fail, left=left, height=bar_h,
            color=SHARED_COLOR, edgecolor="white", linewidth=0.6)
    ax.text(n_shared_fail / 2, y_voice, f"Both fail\n{n_shared_fail}",
            ha="center", va="center", color="white", fontsize=9, fontweight="bold")
    left = n_shared_fail
    # voice-only breakdown: Tool-reasoning → ASR → Streaming
    for bucket, color in [("Tool-reasoning", TOOL_COLOR), ("ASR", ASR_COLOR), ("Streaming", STREAM_COLOR)]:
        w = voice_only_by_bucket.get(bucket, 0)
        if w <= 0:
            continue
        ax.barh(y_voice, w, left=left, height=bar_h,
                color=color, edgecolor="white", linewidth=0.6)
        ax.text(left + w / 2, y_voice, f"{bucket}\n{w}",
                ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
        left += w
    v_end = left
    ax.text(v_end + n_voice_fail * 0.01, y_voice, f"  {n_voice_fail} fail / {n_matched} ({n_voice_fail/n_matched*100:.1f}%)",
            va="center", fontsize=9)

    # Text bar: shared + text-only (usually tiny)
    left = 0
    ax.barh(y_text, n_shared_fail, left=left, height=bar_h,
            color=SHARED_COLOR, edgecolor="white", linewidth=0.6)
    ax.text(n_shared_fail / 2, y_text, f"Both fail\n{n_shared_fail}",
            ha="center", va="center", color="white", fontsize=9, fontweight="bold")
    left = n_shared_fail
    if n_text_only > 0:
        ax.barh(y_text, n_text_only, left=left, height=bar_h,
                color=TEXT_ONLY_COLOR, edgecolor="white", linewidth=0.6)
        ax.text(left + n_text_only / 2, y_text, f"text-only\n{n_text_only}",
                ha="center", va="center", color="white", fontsize=8.5, fontweight="bold")
    t_end = n_shared_fail + n_text_only
    ax.text(t_end + n_voice_fail * 0.01, y_text, f"  {n_text_fail} fail / {n_matched} ({n_text_fail/n_matched*100:.1f}%)",
            va="center", fontsize=9)

    # dashed vertical at text_fail end for alignment
    ax.axvline(t_end, color="#666", linestyle=":", lw=0.9, alpha=0.55)

    # bracket showing voice overhead (extra failures past text)
    bracket_y = y_text - 0.55
    overhead = v_end - t_end
    ax.annotate("", xy=(t_end, bracket_y), xytext=(v_end, bracket_y),
                arrowprops=dict(arrowstyle="-", color="#333", lw=1.1))
    ax.annotate(
        f"voice-modality overhead: +{overhead} extra failures over text   "
        f"({overhead/n_text_fail*100:.0f}% over text)",
        xy=((t_end + v_end) / 2, bracket_y),
        xytext=((t_end + v_end) / 2, bracket_y - 0.20),
        ha="center", va="top", fontsize=9, color="#333",
    )

    # y labels
    ax.set_yticks([y_text, y_voice])
    ax.set_yticklabels([f"Text mode\n({MODEL_LABEL})", f"Voice mode\n({MODEL_LABEL})"], fontsize=10)
    ax.set_ylim(-0.95, 1.75)

    ax.set_xlim(0, v_end * 1.22)
    ax.set_xlabel(f"Failure count on {n_matched} matched tasks (run1, valid traces)", fontsize=10)

    # legend
    from matplotlib.patches import Patch
    handles = [
        Patch(color=SHARED_COLOR, label=f"Shared (both fail) — reasoning-hard, not voice-specific"),
        Patch(color=TOOL_COLOR, label="Voice-only: Tool-use reasoning"),
        Patch(color=ASR_COLOR, label="Voice-only: ASR-induced"),
        Patch(color=STREAM_COLOR, label="Voice-only: Realtime-streaming"),
        Patch(color=TEXT_ONLY_COLOR, label="Text-only fail (voice corrects)"),
    ]
    ax.legend(handles=handles, loc="upper right", fontsize=8.2, frameon=True, framealpha=0.95,
              bbox_to_anchor=(1.0, 1.0))
    ax.grid(axis="x", alpha=0.2)
    ax.spines[["top", "right"]].set_visible(False)
    ax.set_title(
        f"Paired voice-vs-text failure decomposition (n={n_matched} matched tasks, same model)\n"
        f"Shared gray block = reasoning-hard tasks both modes fail; overhang past text = voice-modality overhead",
        fontsize=10, pad=8,
    )

    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=180, bbox_inches="tight")
    print(f"Saved: {OUT}")

    print(f"\nPaired summary (n={n_matched}):")
    print(f"  Both pass:           {n_both_pass}")
    print(f"  Both fail (shared):  {n_shared_fail}   → {shared_by_bucket}")
    print(f"  Voice-only fail:     {n_voice_only}   → {voice_only_by_bucket}")
    print(f"  Text-only fail:      {n_text_only}")
    print(f"  Voice total fail:    {n_voice_fail}   ({n_voice_fail/n_matched*100:.1f}%)")
    print(f"  Text total fail:     {n_text_fail}   ({n_text_fail/n_matched*100:.1f}%)")
    print(f"  Voice overhead over text: +{v_end - t_end} failures")


if __name__ == "__main__":
    main()
