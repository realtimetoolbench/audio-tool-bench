"""CommonVoice speaker registry for voice-cloning TTS."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional


def normalize_accent(accent: Optional[str]) -> str:
    value = (accent or "unknown").strip().lower()
    value = re.sub(r"[^a-z0-9]+", "_", value)
    return "_".join(part for part in value.split("_") if part) or "unknown"


@dataclass(frozen=True)
class CloneSpeaker:
    speaker_id: str
    reference_wavs: tuple[Path, ...]
    language: str
    accent: str
    reference_hash: str
    metadata: dict[str, Any]


class CommonVoiceCloneRegistry:
    """Loads a CommonVoice manifest and selects deterministic clone speakers.

    Accent is an optional ablation filter. When omitted, the main benchmark
    samples from the whole speaker pool without treating accent as a condition.
    """

    def __init__(self, manifest_path: str | Path, accent: Optional[str] = None, policy: str = "task_hash"):
        self.manifest_path = Path(manifest_path).expanduser()
        self.accent_filter = self._normalize_filter(accent)
        self.policy = policy
        if self.policy != "task_hash":
            raise ValueError(f"Unsupported clone_policy {policy!r}; only 'task_hash' is implemented")
        self.speakers = self._load_manifest()
        self._candidates = self._filter_speakers()

    def select_speaker(self, task_path: str | Path, transcript_hash: Optional[str]) -> CloneSpeaker:
        if not self._candidates:
            raise ValueError(
                f"No CommonVoice speakers match accent_filter={self.accent_filter!r} in {self.manifest_path}"
            )
        accent_key = self.accent_filter or "unfiltered"
        # The benchmark may generate TTS on a remote GPU and evaluate locally.
        # Speaker assignment must therefore be independent of absolute paths.
        task_key = transcript_hash or Path(task_path).stem
        key = f"{task_key}:{accent_key}:{self.policy}"
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        idx = int(digest[:16], 16) % len(self._candidates)
        return self._candidates[idx]

    def get_speaker(self, speaker_id: str) -> Optional[CloneSpeaker]:
        return next((speaker for speaker in self.speakers if speaker.speaker_id == speaker_id), None)

    @staticmethod
    def _normalize_filter(accent: Optional[str]) -> Optional[str]:
        if accent is None:
            return None
        value = str(accent).strip()
        if not value or value.lower() == "any":
            return None
        return normalize_accent(value)

    def _filter_speakers(self) -> list[CloneSpeaker]:
        speakers = sorted(self.speakers, key=lambda s: s.speaker_id)
        if self.accent_filter is None:
            return speakers
        return [s for s in speakers if normalize_accent(s.accent) == self.accent_filter]

    def _load_manifest(self) -> list[CloneSpeaker]:
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"CommonVoice clone manifest not found: {self.manifest_path}")
        with open(self.manifest_path, "r", encoding="utf-8") as f:
            raw = json.load(f)

        entries = raw.get("speakers", raw) if isinstance(raw, dict) else raw
        if not isinstance(entries, list):
            raise ValueError("CommonVoice clone manifest must be a list or contain a 'speakers' list")

        speakers = [self._parse_entry(entry) for entry in entries]
        if not speakers:
            raise ValueError(f"CommonVoice clone manifest has no speakers: {self.manifest_path}")
        return speakers

    def _parse_entry(self, entry: dict[str, Any]) -> CloneSpeaker:
        if not isinstance(entry, dict):
            raise ValueError("Each CommonVoice manifest speaker must be an object")
        speaker_id = str(entry.get("speaker_id") or "").strip()
        if not speaker_id:
            raise ValueError("CommonVoice manifest speaker is missing speaker_id")

        refs = entry.get("reference_wavs") or entry.get("reference_wav")
        if isinstance(refs, str):
            refs = [refs]
        if not refs:
            raise ValueError(f"Speaker {speaker_id} has no reference_wavs")

        resolved_refs = tuple(self._resolve_reference_path(p) for p in refs)
        for ref in resolved_refs:
            if not ref.exists():
                raise FileNotFoundError(f"Speaker {speaker_id} reference audio not found: {ref}")

        reference_hash = str(entry.get("reference_hash") or self._hash_files(resolved_refs))
        return CloneSpeaker(
            speaker_id=speaker_id,
            reference_wavs=resolved_refs,
            language=str(entry.get("language") or "en"),
            accent=normalize_accent(entry.get("accent")),
            reference_hash=reference_hash,
            metadata={k: v for k, v in entry.items() if k not in {"reference_wavs", "reference_wav"}},
        )

    def _resolve_reference_path(self, value: str | Path) -> Path:
        path = Path(value).expanduser()
        if path.is_absolute():
            return path
        manifest_relative = self.manifest_path.parent / path
        if manifest_relative.exists():
            return manifest_relative
        return Path.cwd() / path

    @staticmethod
    def _hash_files(paths: Iterable[Path]) -> str:
        digest = hashlib.sha256()
        for path in paths:
            digest.update(path.name.encode("utf-8"))
            digest.update(path.read_bytes())
        return digest.hexdigest()[:12]
