#!/usr/bin/env python3
"""Build an accent-labeled CommonVoice clone manifest from a HF dataset.

The default source is `WillHeld/accented_common_voice`, a small CommonVoice
derivative with an `accents` field. Audio files are written as local WAV refs;
the repository stores only the resulting manifest and the selected references.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any

import numpy as np
import soundfile as sf
from datasets import load_dataset


def normalize_accent(value: str | None) -> str:
    value = (value or "unknown").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return "_".join(part for part in value.split("_") if part) or "unknown"


def reference_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.name.encode("utf-8"))
    digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def parse_targets(raw: str) -> set[str] | None:
    raw = raw.strip()
    if not raw or raw.lower() == "auto":
        return None
    return {normalize_accent(item) for item in raw.split(",") if item.strip()}


def get_audio(row: dict[str, Any]) -> tuple[np.ndarray, int]:
    audio = row.get("audio")
    if not isinstance(audio, dict) or audio.get("array") is None:
        raise ValueError("row has no decoded audio")
    arr = np.asarray(audio["array"], dtype=np.float32)
    if arr.ndim > 1:
        arr = arr[:, 0]
    sr = int(audio.get("sampling_rate") or 16000)
    return arr, sr


def duration_seconds(arr: np.ndarray, sr: int) -> float:
    return float(len(arr)) / float(sr)


def build_manifest(args: argparse.Namespace) -> dict[str, Any]:
    refs_dir = Path(args.refs_dir).expanduser()
    refs_dir.mkdir(parents=True, exist_ok=True)

    targets = parse_targets(args.target_accents)
    selected_by_accent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    seen_paths: set[str] = set()

    ds = load_dataset(args.dataset, split=args.split, streaming=True)

    for row_idx, row in enumerate(ds):
        if args.max_rows and row_idx >= args.max_rows:
            break

        raw_accent = row.get(args.accent_field) or row.get("accent") or row.get("accents")
        accent = normalize_accent(raw_accent)
        if targets is not None and accent not in targets:
            continue
        if len(selected_by_accent) >= args.max_accents and accent not in selected_by_accent:
            continue
        if len(selected_by_accent[accent]) >= args.speakers_per_accent:
            continue

        source_path = str(row.get("path") or f"row_{row_idx:06d}")
        if source_path in seen_paths:
            continue
        seen_paths.add(source_path)

        try:
            arr, sr = get_audio(row)
        except Exception:
            continue
        dur = duration_seconds(arr, sr)
        if dur < args.min_duration or dur > args.max_duration:
            continue

        speaker_key = hashlib.sha256(f"{accent}:{source_path}:{row_idx}".encode("utf-8")).hexdigest()[:12]
        wav_path = refs_dir / f"{accent}_{speaker_key}.wav"
        sf.write(wav_path, arr, sr, subtype="PCM_16")

        selected_by_accent[accent].append(
            {
                "speaker_id": f"{accent}_{speaker_key}",
                "reference_wavs": [str(wav_path)],
                "language": args.language,
                "accent": accent,
                "reference_hash": reference_hash(wav_path),
                "source_dataset": args.dataset,
                "source_split": args.split,
                "source_path": source_path,
                "source_sentence": row.get("sentence"),
                "source_accent_label": raw_accent,
                "duration": round(dur, 3),
                "sample_rate": sr,
            }
        )

        if len(selected_by_accent) >= args.max_accents and all(
            len(items) >= args.speakers_per_accent for items in selected_by_accent.values()
        ):
            break

    speakers = []
    for accent in sorted(selected_by_accent):
        speakers.extend(selected_by_accent[accent])

    return {
        "dataset": "commonvoice",
        "source": args.dataset,
        "source_split": args.split,
        "language": args.language,
        "created_at": datetime.now().isoformat(),
        "target_accents": sorted(selected_by_accent),
        "speakers_per_accent": args.speakers_per_accent,
        "speakers": speakers,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", default="WillHeld/accented_common_voice")
    parser.add_argument("--split", default="train")
    parser.add_argument("--accent-field", default="accents")
    parser.add_argument("--language", default="en")
    parser.add_argument("--target-accents", default="auto", help="comma-separated normalized labels or auto")
    parser.add_argument("--max-accents", type=int, default=3)
    parser.add_argument("--speakers-per-accent", type=int, default=2)
    parser.add_argument("--max-rows", type=int, default=2000)
    parser.add_argument("--min-duration", type=float, default=2.0)
    parser.add_argument("--max-duration", type=float, default=12.0)
    parser.add_argument("--refs-dir", default="data/voice_clones/commonvoice_accent_refs")
    parser.add_argument("--output", default="data/voice_clones/commonvoice_accent_manifest.json")
    args = parser.parse_args()

    manifest = build_manifest(args)
    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")

    by_accent: dict[str, int] = defaultdict(int)
    for speaker in manifest["speakers"]:
        by_accent[speaker["accent"]] += 1
    print(f"Wrote {len(manifest['speakers'])} speakers to {out}")
    for accent, count in sorted(by_accent.items()):
        print(f"  {accent}: {count}")


if __name__ == "__main__":
    main()
