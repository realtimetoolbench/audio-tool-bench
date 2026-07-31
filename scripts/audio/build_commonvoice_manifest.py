#!/usr/bin/env python3
"""Build a CommonVoice speaker manifest for VoiceCloningTTS."""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def normalize_accent(value: str | None) -> str:
    value = (value or "unknown").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return "_".join(part for part in value.split("_") if part) or "unknown"


def file_hash(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.name.encode("utf-8"))
        digest.update(path.read_bytes())
    return digest.hexdigest()[:12]


def build_manifest(args: argparse.Namespace) -> dict:
    root = Path(args.commonvoice_root).expanduser().resolve()
    tsv_path = Path(args.validated_tsv).expanduser()
    if not tsv_path.is_absolute():
        tsv_path = root / tsv_path
    tsv_path = tsv_path.resolve()
    clips_dir = Path(args.clips_dir).expanduser()
    if not clips_dir.is_absolute():
        clips_dir = root / clips_dir
    clips_dir = clips_dir.resolve()

    grouped: dict[str, list[dict]] = defaultdict(list)
    with open(tsv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            speaker_id = row.get("client_id") or row.get("speaker_id")
            rel_path = row.get("path")
            if not speaker_id or not rel_path:
                continue
            accent = normalize_accent(row.get("accent"))
            if args.accent != "any" and accent != normalize_accent(args.accent):
                continue
            clip_path = clips_dir / rel_path
            if args.verify_files and not clip_path.exists():
                continue
            grouped[speaker_id].append({"path": clip_path, "accent": accent, "row": row})

    speakers = []
    for speaker_id, rows in sorted(grouped.items()):
        rows = rows[: args.refs_per_speaker]
        if len(rows) < args.refs_per_speaker:
            continue
        refs = [r["path"] for r in rows]
        if args.verify_files and any(not p.exists() for p in refs):
            continue
        accent_counts = defaultdict(int)
        for r in rows:
            accent_counts[r["accent"]] += 1
        accent = sorted(accent_counts.items(), key=lambda item: (-item[1], item[0]))[0][0]
        speakers.append(
            {
                "speaker_id": speaker_id,
                "reference_wavs": [str(p) for p in refs],
                "language": args.language,
                "accent": accent,
                "reference_hash": file_hash(refs) if args.verify_files else None,
            }
        )
        if args.max_speakers and len(speakers) >= args.max_speakers:
            break

    return {
        "dataset": "commonvoice",
        "language": args.language,
        "created_at": datetime.now().isoformat(),
        "source_tsv": str(tsv_path),
        "clips_dir": str(clips_dir),
        "speakers": speakers,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--commonvoice-root", required=True, help="CommonVoice split root")
    parser.add_argument("--validated-tsv", default="validated.tsv")
    parser.add_argument("--clips-dir", default="clips")
    parser.add_argument("--output", default="data/voice_clones/commonvoice_manifest.json")
    parser.add_argument("--language", default="en")
    parser.add_argument("--accent", default="any")
    parser.add_argument("--refs-per-speaker", type=int, default=1)
    parser.add_argument("--max-speakers", type=int, default=0)
    parser.add_argument("--verify-files", action="store_true")
    args = parser.parse_args()

    manifest = build_manifest(args)
    out = Path(args.output).expanduser()
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Wrote {len(manifest['speakers'])} speakers to {out}")


if __name__ == "__main__":
    main()
