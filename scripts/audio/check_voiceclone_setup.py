#!/usr/bin/env python3
"""Check optional XTTS/Common Voice/DEMAND setup before long runs."""

from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MANIFEST = ROOT / "data/voice_clones/commonvoice_28speaker_manifest.json"
DEMAND_CLASSES = ["DKITCHEN", "OOFFICE", "PCAFETER", "PRESTO", "TMETRO", "NRIVER"]


def ok(label: str, value: str = "") -> None:
    print(f"[ok] {label}{': ' + value if value else ''}")


def warn(label: str, value: str = "") -> None:
    print(f"[warn] {label}{': ' + value if value else ''}")


def fail(label: str, value: str = "") -> None:
    print(f"[fail] {label}{': ' + value if value else ''}")


def check_manifest(path: Path) -> bool:
    if not path.exists():
        fail("Common Voice manifest missing", str(path))
        return False
    data = json.loads(path.read_text(encoding="utf-8"))
    speakers = data.get("speakers", data if isinstance(data, list) else [])
    if not speakers:
        fail("Common Voice manifest has no speakers", str(path))
        return False

    missing_refs = []
    accents = Counter()
    for speaker in speakers:
        accents[str(speaker.get("accent") or "unknown")] += 1
        refs = speaker.get("reference_wavs") or speaker.get("reference_wav") or []
        if isinstance(refs, str):
            refs = [refs]
        for ref in refs:
            ref_path = Path(ref)
            if not ref_path.is_absolute():
                ref_path = path.parent / ref_path
            if not ref_path.exists():
                missing_refs.append(str(ref_path))
    if missing_refs:
        fail("Common Voice missing reference wavs", f"{len(missing_refs)} missing; first={missing_refs[0]}")
        return False
    ok("Common Voice manifest", f"{len(speakers)} speakers; accents={dict(sorted(accents.items()))}")
    return True


def check_xtts(import_xtts: bool) -> bool:
    model_path = os.getenv("VOICE_CLONING_MODEL_PATH")
    if model_path:
        path = Path(model_path).expanduser()
        if path.exists() and (path / "config.json").exists():
            ok("VOICE_CLONING_MODEL_PATH", str(path))
        else:
            fail("VOICE_CLONING_MODEL_PATH invalid", str(path))
            return False
    else:
        warn("VOICE_CLONING_MODEL_PATH not set", "Coqui TTS will download/load the named XTTS model on first use")

    if not import_xtts:
        warn("XTTS import skipped", "pass --import-xtts to test the installed Coqui TTS package")
        return True
    try:
        from TTS.api import TTS  # noqa: F401
    except Exception as exc:
        fail("Coqui TTS import failed", f"{type(exc).__name__}: {exc}")
        return False
    ok("Coqui TTS import")
    return True


def check_demand(path_arg: str | None) -> bool:
    raw = path_arg or os.getenv("AUDIO_TOOL_BENCH_DEMAND_ROOT")
    if not raw:
        warn("AUDIO_TOOL_BENCH_DEMAND_ROOT not set", "needed only for --audio-variant noisy")
        return True
    root = Path(raw).expanduser()
    if not root.exists():
        fail("DEMAND root missing", str(root))
        return False
    missing = []
    for cls in DEMAND_CLASSES:
        cls_dir = root / cls / cls
        if not cls_dir.exists() or not list(cls_dir.glob("ch*.wav")):
            missing.append(cls)
    if missing:
        fail("DEMAND class directories missing", ", ".join(missing))
        return False
    ok("DEMAND root", str(root))
    return True


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--manifest", default=str(DEFAULT_MANIFEST))
    parser.add_argument("--demand-root", default=None)
    parser.add_argument("--import-xtts", action="store_true")
    args = parser.parse_args()

    checks = [
        check_manifest(Path(args.manifest).expanduser()),
        check_xtts(args.import_xtts),
        check_demand(args.demand_root),
    ]
    return 0 if all(checks) else 1


if __name__ == "__main__":
    raise SystemExit(main())
