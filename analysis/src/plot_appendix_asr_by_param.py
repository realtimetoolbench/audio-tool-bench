"""Appendix figure - ASR error distribution by parameter type.

For each voice checkpoint, iterate over failures with primary_error == 'asr_error',
parse the detail string ("<param_name>: '<expected>' vs '<actual>'"), classify
the expected value into one of:
  - Name (person name)
  - City / Location
  - Phone / ID / Numeric string
  - Date / Time
  - Other

Stacked bar per model, absolute counts + percent labels.
"""
from __future__ import annotations

import re
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from data_loader import load_all

OUT = Path(__file__).resolve().parent.parent / "figures" / "appendix_asr_by_param.pdf"

MODELS = [
    ("openai_gpt-realtime-1.5", "gpt-realtime-1.5", "#1565C0"),
    ("openai_gpt-realtime", "gpt-realtime", "#1976D2"),
    ("openai_gpt-realtime-mini", "gpt-realtime-mini", "#42A5F5"),
]

CATS = ["Person name", "City / place", "Phone / ID", "Date / time", "Other"]
CAT_COLORS = ["#D32F2F", "#F57C00", "#7B1FA2", "#00796B", "#616161"]

DATE_RE = re.compile(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}|am|pm", re.IGNORECASE)
ID_RE = re.compile(r"^[A-Z]{0,4}\d{4,}$|^\d{7,}$")
NAME_PARAM_KW = ("name", "guest", "passenger", "buyer", "customer")
CITY_PARAM_KW = ("city", "origin", "destination", "location", "place", "from", "to")
DATE_PARAM_KW = ("date", "time", "checkin", "checkout", "when")
ID_PARAM_KW = ("id", "phone", "mobile", "tel", "number", "reservation", "booking")


def classify_detail(detail: str) -> str:
    if not detail:
        return "Other"
    # detail: "param_name: 'expected' vs 'actual'"
    head = detail.split(":", 1)[0].lower()
    m = re.search(r"'([^']*)'", detail)
    expected = m.group(1) if m else ""

    if any(k in head for k in DATE_PARAM_KW) or DATE_RE.search(expected):
        return "Date / time"
    if any(k in head for k in ID_PARAM_KW) or ID_RE.match(expected.replace(" ", "")):
        return "Phone / ID"
    if any(k in head for k in NAME_PARAM_KW):
        return "Person name"
    if any(k in head for k in CITY_PARAM_KW):
        return "City / place"
    return "Other"


def main():
    df = load_all()
    run1 = df[(df["run"] == "run1") & (~df["is_crashed"])]

    per_model = {}
    for model, label, color in MODELS:
        sub = run1[(run1["model"] == model) & (run1["primary_error"] == "asr_error")]
        counter = {c: 0 for c in CATS}
        for details in sub["detail_list"]:
            for d in details:
                counter[classify_detail(d)] += 1
        per_model[label] = counter

    # --- plot ---
    labels = list(per_model.keys())
    x = np.arange(len(labels))
    fig, ax = plt.subplots(figsize=(8.5, 4.8), dpi=140)
    bottom = np.zeros(len(labels))
    for cat, color in zip(CATS, CAT_COLORS):
        heights = np.array([per_model[l][cat] for l in labels])
        bars = ax.bar(x, heights, 0.55, bottom=bottom, color=color, label=cat,
                      edgecolor="white", linewidth=0.5)
        for b, h, bt in zip(bars, heights, bottom):
            if h > 0:
                ax.text(b.get_x() + b.get_width() / 2, bt + h / 2, f"{int(h)}",
                        ha="center", va="center", color="white", fontsize=8, fontweight="bold")
        bottom += heights
    # totals above
    for i, total in enumerate(bottom):
        ax.text(i, total + max(bottom) * 0.02, f"Σ={int(total)}", ha="center", fontsize=9, fontweight="bold")

    ax.set_xticks(x)
    ax.set_xticklabels(labels, fontsize=10)
    ax.set_ylabel("ASR error count (per-parameter)")
    ax.set_ylim(0, max(bottom) * 1.20)
    ax.grid(axis="y", alpha=0.3)
    ax.legend(loc="upper right", fontsize=9, title="Parameter type")
    ax.set_title("ASR-induced parameter errors by parameter type (run1, valid failures)",
                 fontsize=10, pad=8)
    plt.tight_layout()
    OUT.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT, bbox_inches="tight")
    fig.savefig(OUT.with_suffix(".png"), dpi=180, bbox_inches="tight")
    print(f"Saved: {OUT}")
    for label, counter in per_model.items():
        print(f"  {label}: {counter}  total={sum(counter.values())}")


if __name__ == "__main__":
    main()
