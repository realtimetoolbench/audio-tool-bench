"""Shared filesystem path helpers."""
from pathlib import Path
import os


REPO_ROOT = Path(__file__).resolve().parent.parent


def project_root() -> Path:
    if REPO_ROOT.parent.name == "code":
        return REPO_ROOT.parent.parent
    return REPO_ROOT


def output_root() -> Path:
    override = os.getenv("AUDIO_TOOL_BENCH_OUTPUT_ROOT")
    if override:
        return Path(override).expanduser()
    return project_root() / "outputs"


def trace_root() -> Path:
    override = os.getenv("AUDIO_TOOL_BENCH_TRACE_ROOT")
    if override:
        return Path(override).expanduser()
    return output_root() / "traces"


def audio_cache_root() -> Path:
    override = os.getenv("AUDIO_TOOL_BENCH_AUDIO_ROOT")
    if override:
        return Path(override).expanduser()
    return output_root() / "audio"
