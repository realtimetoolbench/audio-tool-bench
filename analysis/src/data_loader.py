"""Unified loader for Audio Tool Bench traces across worktrees.

Returns pandas DataFrame with columns:
  model, subset, category, task_id, run, passed, primary_error,
  asr_error, missing_call, premature_call, param_error, unexpected_call,
  wrong_tool, n_tools, n_turns, n_params, detail_list, is_id_like, is_name_like

Subsets (directory names) are mapped to paper-facing categories:
  reactive            -> Reactive
  strong/medium/weak  -> Proactive
  interruption        -> Intra-turn (speech-phase interrupt)
  v31_tool_phase      -> Inter-turn (tool-phase interrupt)
  v31_extra           -> Inter-turn (tool-phase extra)
"""
from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path

import pandas as pd

# Paths are resolved relative to the repo root (this file lives at analysis/src/data_loader.py).
ROOT = Path(__file__).resolve().parent.parent.parent
WORKTREES = [ROOT]

SUBSETS = ["reactive", "strong", "medium", "weak", "interruption", "v31_tool_phase", "v31_extra"]

CATEGORY_MAP = {
    "reactive": "Reactive",
    "strong": "Proactive",
    "medium": "Proactive",
    "weak": "Proactive",
    "interruption": "Intra-turn",
    "v31_tool_phase": "Inter-turn",
    "v31_extra": "Inter-turn",
}

# Maps any directory name found in data/traces/<model>/<dir>/ to a canonical subset.
# Unknown dirs (timestamps, archives, smoke tests, log files) are silently skipped.
SUBSET_ALIAS = {
    "reactive": "reactive",
    "strong": "strong", "strong_v2": "strong", "proactive_strong": "strong",
    "medium": "medium", "medium_v2": "medium", "proactive_medium": "medium",
    "weak": "weak", "weak_v2": "weak", "proactive_weak": "weak",
    "interruption": "interruption", "interrupt_speech": "interruption",
    "v31_tool_phase": "v31_tool_phase", "interrupt_tool": "v31_tool_phase",
    "interruption_tool_cancel": "v31_tool_phase",
    "interruption_tool_correction": "v31_tool_phase",
    "interruption_priority_no_return": "v31_tool_phase",
    "interruption_priority_late_return": "v31_tool_phase",
    "interruption_priority_early_return": "v31_tool_phase",
    "v31_extra": "v31_extra", "interrupt_tool_extra": "v31_extra",
}

ERROR_TYPES = ["asr_error", "missing_call", "premature_call", "param_error", "unexpected_call", "wrong_tool"]

TASK_DIR_MAP = {
    "reactive": ("reactive", None),
    "strong": ("proactive", "strong_v2"),
    "medium": ("proactive", "medium_v2"),
    "weak": ("proactive", "weak_v2"),
    "interruption": ("interruption", None),
    "v31_tool_phase": ("interruption_v31", None),
    "v31_extra": ("interruption_v31_extra", None),
}

TASKS_ROOT = ROOT / "data" / "tasks"


@lru_cache(maxsize=None)
def _load_task(subset: str, task_id: str) -> dict | None:
    head, sub = TASK_DIR_MAP[subset]
    p = TASKS_ROOT / head / sub / f"{task_id}.json" if sub else TASKS_ROOT / head / f"{task_id}.json"
    if not p.exists():
        return None
    with p.open() as f:
        return json.load(f)


def _count_params(task: dict) -> int:
    names = set()
    for turn in task.get("transcript", []):
        for p in turn.get("metadata", {}).get("contains_params", []) or []:
            names.add(p.split("=")[0])
    return len(names)


_ID_RE = re.compile(r"^[A-Za-z]*\d{4,}$|^\d{7,}$")
_NAME_RE = re.compile(r"^[A-Z][a-z]+(\s+[A-Z][a-z]+)+$")


def _classify_detail(detail: str) -> tuple[bool, bool]:
    """Return (is_id_like, is_name_like) for the expected/actual value in a detail string.

    Detail format example: "guest_name: 'Li Na' vs 'Lina'".
    """
    if not detail:
        return False, False
    m = re.search(r"'([^']*)'\s*vs\s*'([^']*)'", detail)
    if not m:
        return False, False
    exp = m.group(1)
    is_id = bool(_ID_RE.match(exp.replace(" ", "")))
    param_name = detail.split(":", 1)[0].lower()
    is_name = "name" in param_name or "city" in param_name or bool(_NAME_RE.match(exp))
    return is_id, is_name


def _load_trace_row(trace_path: Path, model: str, subset: str, run: str) -> dict | None:
    try:
        with trace_path.open() as f:
            t = json.load(f)
    except Exception:
        return None
    ev = t.get("evaluation") or {}
    passed = ev.get("passed")
    if passed is None:
        return None
    task_id = t.get("task_name") or trace_path.stem
    task = _load_task(subset, task_id)
    n_params = _count_params(task) if task else None
    n_tools = len(task.get("tools", [])) if task else None
    n_turns = len(task.get("transcript", [])) if task else None
    expected_tools = task.get("expected_tools") if task else None

    attr = ev.get("error_attribution") or {}
    etypes = attr.get("error_types") or {}
    errors = attr.get("errors") or []
    detail_list = [e.get("detail", "") for e in errors]
    any_id = any(_classify_detail(d)[0] for d in detail_list)
    any_name = any(_classify_detail(d)[1] for d in detail_list)

    # Crashed-session detection: the task expected tool calls but the model
    # emitted zero calls (harness crash / auth failure / connection drop).
    # proactive-weak tasks legitimately have zero expected calls — exclude.
    summary = t.get("summary") or {}
    total_tool_calls = summary.get("total_tool_calls", 0) or 0
    has_expected_tools = bool(expected_tools) if expected_tools is not None else (subset != "weak")
    is_crashed = (total_tool_calls == 0) and has_expected_tools

    row = {
        "model": model,
        "subset": subset,
        "category": CATEGORY_MAP[subset],
        "task_id": task_id,
        "run": run,
        "passed": bool(passed),
        "primary_error": attr.get("primary_error"),
        "n_tools": n_tools,
        "n_turns": n_turns,
        "n_params": n_params,
        "total_tool_calls": total_tool_calls,
        "is_crashed": is_crashed,
        "detail_list": detail_list,
        "is_id_like": any_id,
        "is_name_like": any_name,
    }
    for et in ERROR_TYPES:
        row[et] = int(etypes.get(et, 0))
    return row


def _iter_subset_dirs(parent: Path):
    """Yield (canonical_subset, Path) for every recognized subset dir under parent."""
    if not parent.is_dir():
        return
    for d in parent.iterdir():
        if not d.is_dir():
            continue
        canon = SUBSET_ALIAS.get(d.name)
        if canon is not None:
            yield canon, d


def _iter_model_runs(worktree: Path, provider_model: str):
    base = worktree / "data/traces" / provider_model
    if not base.is_dir():
        return
    for canon, sd in _iter_subset_dirs(base):
        for p in sd.glob("*.json"):
            yield (canon, "run1", p)
    runs_dir = base / "runs"
    if runs_dir.is_dir():
        for run_d in sorted(runs_dir.iterdir()):
            if not run_d.is_dir() or not run_d.name.startswith("run"):
                continue
            for canon, sd in _iter_subset_dirs(run_d):
                for p in sd.glob("*.json"):
                    yield (canon, run_d.name, p)


def enumerate_models() -> list[tuple[Path, str]]:
    """Return (worktree, provider_model) pairs that actually contain traces."""
    pairs = []
    seen = set()
    for wt in WORKTREES:
        traces = wt / "data/traces"
        if not traces.is_dir():
            continue
        for d in traces.iterdir():
            if not d.is_dir():
                continue
            pm = d.name
            if pm in seen:
                continue
            if any(1 for _ in _iter_model_runs(wt, pm)):
                pairs.append((wt, pm))
                seen.add(pm)
    return pairs


def load_all(verbose: bool = False) -> pd.DataFrame:
    rows = []
    for wt, pm in enumerate_models():
        n_before = len(rows)
        for sub, run, p in _iter_model_runs(wt, pm):
            r = _load_trace_row(p, pm, sub, run)
            if r is not None:
                rows.append(r)
        if verbose:
            print(f"  {pm:50s} +{len(rows)-n_before}  (from {wt.name})")
    df = pd.DataFrame(rows)
    return df


def nice_model_name(pm: str) -> str:
    """Strip provider prefix + append _text/_cascade suffix."""
    for prefix in ("openai-cascade_", "openai-chat_", "openai_", "gemini-chat_", "gemini_", "grok_", "glm_"):
        if pm.startswith(prefix):
            return pm[len(prefix):]
    return pm


def provider_of(pm: str) -> str:
    if pm.startswith("openai-cascade_"):
        return "cascade"
    if pm.startswith("openai-chat_"):
        return "openai-chat"
    if pm.startswith("openai_"):
        return "openai"
    if pm.startswith("gemini-chat_"):
        return "gemini-chat"
    if pm.startswith("gemini_"):
        return "gemini"
    if pm.startswith("grok_"):
        return "grok"
    if pm.startswith("glm_"):
        return "glm"
    return "other"


if __name__ == "__main__":
    df = load_all(verbose=True)
    print(f"\nTotal rows: {len(df)}")
    print(f"Unique models: {df['model'].nunique()}")
    print("\nCoverage (model × subset × run, subset counts):")
    cov = df.groupby(["model", "subset", "run"]).size().unstack(fill_value=0)
    print(cov.to_string())
    print("\nPass rate per model (run1, across all subsets):")
    run1 = df[df["run"] == "run1"]
    pr = run1.groupby("model")["passed"].agg(["sum", "count"]).assign(rate=lambda x: x["sum"]/x["count"]*100)
    print(pr.sort_values("rate", ascending=False).to_string())
