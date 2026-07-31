"""Claim 2 validation: voice × interrupt interaction effect.

Hypothesis: voice modality hurts more on interrupt tasks than on non-interrupt
tasks. i.e., the voice-text gap is significantly larger on interrupt-class
subsets than on non-interrupt subsets.

Uses paired gpt-realtime voice vs text data (n=519 matched tasks).
Runs logistic regression with mode × is_interrupt interaction term.
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import statsmodels.formula.api as smf
from scipy import stats

from data_loader import load_all

OUT = Path(__file__).resolve().parent.parent / "figures" / "claim2_interaction.pdf"
VOICE_MODEL = "openai_gpt-realtime"
TEXT_MODEL = "openai_gpt-realtime_text"
INTERRUPT_SUBS = {"interruption", "v31_tool_phase", "v31_extra"}


def main():
    df = load_all()
    run1 = df[(df["run"] == "run1") & (~df["is_crashed"])]
    V = run1[run1["model"] == VOICE_MODEL][["subset", "task_id", "passed"]].rename(columns={"passed": "v_pass"})
    T = run1[run1["model"] == TEXT_MODEL][["subset", "task_id", "passed"]].rename(columns={"passed": "t_pass"})
    m = V.merge(T, on=["subset", "task_id"], how="inner")

    # long format for regression: one row per (task, mode)
    m["is_interrupt"] = m["subset"].isin(INTERRUPT_SUBS).astype(int)
    long = pd.concat([
        m[["subset", "task_id", "is_interrupt", "v_pass"]].rename(columns={"v_pass": "passed"}).assign(mode="voice", is_voice=1),
        m[["subset", "task_id", "is_interrupt", "t_pass"]].rename(columns={"t_pass": "passed"}).assign(mode="text", is_voice=0),
    ], ignore_index=True)
    long["passed_i"] = long["passed"].astype(int)

    # summary table
    summary = long.groupby(["is_interrupt", "mode"]).agg(
        n=("passed", "count"),
        pass_rate=("passed", lambda s: s.mean() * 100),
    ).reset_index()
    print("=== Per-cell pass rate ===")
    print(summary.to_string(index=False))

    # 2-proportion z on each slice
    for is_int in [0, 1]:
        sub = long[long["is_interrupt"] == is_int]
        v = sub[sub["is_voice"] == 1]["passed_i"]
        t = sub[sub["is_voice"] == 0]["passed_i"]
        pv = v.mean(); pt = t.mean(); nv = len(v); nt = len(t)
        pool = (v.sum() + t.sum()) / (nv + nt)
        se = (pool * (1 - pool) * (1/nv + 1/nt)) ** 0.5
        z = (pv - pt) / se
        p = 2 * (1 - stats.norm.cdf(abs(z)))
        label = "interrupt" if is_int else "non-interrupt"
        print(f"  {label:14s} voice={pv*100:.1f}% text={pt*100:.1f}%  gap={pt*100-pv*100:.1f}pp  z={z:.2f} p={p:.3g}")

    # === logistic regression with interaction ===
    model = smf.logit("passed_i ~ is_voice * is_interrupt", data=long).fit(disp=False)
    print("\n=== Logit: passed ~ is_voice * is_interrupt ===")
    print(model.summary2().tables[1].round(4))

    # --- plot ---
    fig, axes = plt.subplots(1, 2, figsize=(11, 4.2), dpi=140, gridspec_kw={"width_ratios": [1.2, 1.0]})
    ax = axes[0]
    # interaction plot: two lines (text, voice) across non-interrupt / interrupt
    x = [0, 1]
    labels = ["Non-interrupt\n(reactive + proactive)", "Interrupt\n(intra-/inter-turn)"]
    series = {
        "Text mode":  [summary.query("is_interrupt==0 and mode=='text'")["pass_rate"].iloc[0],
                       summary.query("is_interrupt==1 and mode=='text'")["pass_rate"].iloc[0]],
        "Voice mode": [summary.query("is_interrupt==0 and mode=='voice'")["pass_rate"].iloc[0],
                       summary.query("is_interrupt==1 and mode=='voice'")["pass_rate"].iloc[0]],
    }
    colors = {"Text mode": "#2E7D32", "Voice mode": "#1565C0"}
    for name, ys in series.items():
        ax.plot(x, ys, marker="o", markersize=9, lw=2.2, color=colors[name], label=name)
        for xi, yi in zip(x, ys):
            ax.text(xi + 0.03, yi, f"{yi:.1f}%", va="center", fontsize=9, color=colors[name])
    # gap arrows
    for xi in x:
        t_y = series["Text mode"][xi]
        v_y = series["Voice mode"][xi]
        ax.annotate("", xy=(xi - 0.06, v_y), xytext=(xi - 0.06, t_y),
                    arrowprops=dict(arrowstyle="<->", color="gray", lw=0.9))
        ax.text(xi - 0.10, (t_y + v_y) / 2, f"−{t_y - v_y:.1f}pp", fontsize=9, ha="right", va="center", color="gray")
    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_xlim(-0.35, 1.35)
    ax.set_ylabel("Pass rate (%)")
    ax.set_ylim(0, 80)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper right", fontsize=9)
    ax.set_title("Voice × Interrupt interaction: gap widens on interrupt tasks", fontsize=10)

    # panel 2: interaction coefficient + CI
    ax2 = axes[1]
    params = model.params
    conf = model.conf_int()
    conf.columns = ["lo", "hi"]
    order = ["is_voice", "is_interrupt", "is_voice:is_interrupt"]
    labels2 = ["is_voice\n(main effect)", "is_interrupt\n(main effect)", "is_voice × is_interrupt\n(interaction)"]
    ys = np.arange(len(order))
    pts = [params[k] for k in order]
    los = [conf.loc[k, "lo"] for k in order]
    his = [conf.loc[k, "hi"] for k in order]
    ax2.errorbar(pts, ys, xerr=[[p - lo for p, lo in zip(pts, los)], [hi - p for p, hi in zip(pts, his)]],
                 fmt="o", color="black", capsize=4, markersize=8)
    for i, k in enumerate(order):
        ax2.text(pts[i] + 0.05, i, f"β={pts[i]:+.2f}  p={model.pvalues[k]:.2g}", va="center", fontsize=8.5)
    ax2.axvline(0, color="red", linestyle=":", lw=1)
    ax2.set_yticks(ys)
    ax2.set_yticklabels(labels2, fontsize=9)
    ax2.set_xlabel("Logit coefficient (with 95% CI)")
    ax2.invert_yaxis()
    ax2.set_title("Logistic regression coefficients\n(passed ~ is_voice × is_interrupt)", fontsize=10)
    ax2.grid(axis="x", alpha=0.3)

    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".png"), dpi=180, bbox_inches="tight")
    print(f"\nSaved: {OUT}")


if __name__ == "__main__":
    main()
