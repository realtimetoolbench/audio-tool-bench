"""
D3-new noise injection: 在 PCM 层把 DEMAND noise overlay 到现有 default audio cache。

策略
- 读 ablation_subsets/d3_new.json 中 60 task 的 path
- 对每个 task:
    随机选 1 个 DEMAND class + 1 个 channel（fixed seed, reproducible）
    把 16kHz noise polyphase resample 到 24kHz（与 TTS PCM 一致）
    对每个 chunk_*.pcm 用相同 (class, ch) 混音，SNR=15dB
    输出到项目级 outputs/audio/<task>/noisy/{chunk_*.pcm + metadata.json}

不在 codec 后混音（PCM 层混音 → 后续 transcode 由 audio_runner 各 model native format 处理）
"""

import argparse
import json
import os
import random
import sys
import wave
from pathlib import Path
from typing import List, Optional

import numpy as np
from scipy.signal import resample_poly

SEED = 42
SNR_DB = 15.0
TARGET_SR = 24000  # match TTS PCM
NOISE_SR = 16000  # DEMAND _16k

REPO = Path(__file__).resolve().parents[3]
PROJECT = REPO.parent.parent if REPO.parent.name == "code" else REPO
OUTPUTS = PROJECT / "outputs"
sys.path.insert(0, str(REPO))

from eval.audio.tts_cache import TTSCache

DEMAND_DIR = Path(os.getenv("AUDIO_TOOL_BENCH_DEMAND_ROOT", OUTPUTS / "archive" / "corpora" / "_corpora" / "DEMAND_16k")).expanduser()
NOISE_CLASSES = ["DKITCHEN", "OOFFICE", "PCAFETER", "PRESTO", "TMETRO", "NRIVER"]

DEFAULT_SUBSET_FILE = REPO / "scripts" / "ablation" / "subsets" / "d3_new.json"
AUDIO_ROOT = OUTPUTS / "audio"


def load_pcm16(path: Path) -> np.ndarray:
    """Load raw PCM16 mono → float32 in [-1, 1]"""
    raw = path.read_bytes()
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    return samples


def save_pcm16(samples: np.ndarray, path: Path) -> int:
    samples = np.clip(samples, -1.0, 1.0)
    int_samples = (samples * 32767).astype(np.int16)
    path.write_bytes(int_samples.tobytes())
    return len(int_samples) * 2


def load_demand_noise(class_name: str, channel: str) -> np.ndarray:
    """Load DEMAND noise wav (16kHz mono PCM16) as float32 normalized."""
    # DEMAND nested: <root>/CLASS/CLASS/chXX.wav
    wav_path = DEMAND_DIR / class_name / class_name / f"{channel}.wav"
    if not wav_path.exists():
        raise FileNotFoundError(wav_path)
    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getframerate() == NOISE_SR, f"expect 16kHz, got {wf.getframerate()}"
        assert wf.getsampwidth() == 2, f"expect 16-bit, got {wf.getsampwidth() * 8}-bit"
        n = wf.getnframes()
        raw = wf.readframes(n)
    samples = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
    if wf.getnchannels() > 1:
        samples = samples.reshape(-1, wf.getnchannels())[:, 0]
    return samples


def resample_16_to_24(noise: np.ndarray) -> np.ndarray:
    """16kHz → 24kHz polyphase resample (3/2 ratio)"""
    return resample_poly(noise, 3, 2).astype(np.float32)


def mix_at_snr(speech: np.ndarray, noise: np.ndarray, snr_db: float) -> np.ndarray:
    """Overlay noise on speech at specified SNR (in dB).

    Loops noise to match speech length. SNR uses RMS energy.
    """
    n_speech = len(speech)
    if len(noise) < n_speech:
        repeats = n_speech // len(noise) + 1
        noise = np.tile(noise, repeats)
    noise = noise[:n_speech]

    eps = 1e-9
    speech_rms = np.sqrt(np.mean(speech ** 2) + eps)
    noise_rms = np.sqrt(np.mean(noise ** 2) + eps)
    target_noise_rms = speech_rms / (10 ** (snr_db / 20))
    gain = target_noise_rms / noise_rms
    return speech + noise * gain


def collect_d3_task_paths(subset_file: Path) -> List[Path]:
    with open(subset_file, "r", encoding="utf-8") as f:
        d3 = json.load(f)
    paths = []
    for cat in ("reactive", "proactive", "interruption"):
        for entry in d3.get(cat, []):
            paths.append(Path(entry["path"]))
    return paths


def task_audio_dir(
    task_path: Path,
    tts_backend: str = "openai",
    clone_manifest: Optional[str] = None,
    clone_accent: Optional[str] = None,
    clone_policy: str = "task_hash",
) -> Path:
    """Mirror TTSCache._get_cache_path logic under outputs/audio."""
    cache = TTSCache(
        cache_dir=str(AUDIO_ROOT),
        tts_backend=tts_backend,
        clone_manifest=clone_manifest,
        clone_accent=clone_accent,
        clone_policy=clone_policy,
    )
    return cache._get_cache_path(str(task_path))


def inject_for_task(
    task_path: Path,
    rng: random.Random,
    source_cache_dir: Optional[Path] = None,
    tts_backend: str = "openai",
    clone_manifest: Optional[str] = None,
    clone_accent: Optional[str] = None,
    clone_policy: str = "task_hash",
    snr_db: float = SNR_DB,
    noise_class: str = "any",
) -> dict:
    """Process one task: mix all chunks at SNR=15dB. Returns summary dict."""
    src_dir = source_cache_dir or task_audio_dir(
        task_path,
        tts_backend=tts_backend,
        clone_manifest=clone_manifest,
        clone_accent=clone_accent,
        clone_policy=clone_policy,
    )
    src_metadata = src_dir / "metadata.json"
    if not src_metadata.exists():
        return {"task": task_path.stem, "status": "skip_no_cache", "src": str(src_dir)}

    with open(src_metadata, "r", encoding="utf-8") as f:
        meta = json.load(f)

    # noise selection (deterministic per task via task name hash + global rng)
    if noise_class == "any":
        noise_class = rng.choice(NOISE_CLASSES)
    elif noise_class not in NOISE_CLASSES:
        raise ValueError(f"noise_class must be one of {NOISE_CLASSES} or 'any', got {noise_class!r}")
    channel = f"ch{rng.randint(1, 16):02d}"
    noise_24k = resample_16_to_24(load_demand_noise(noise_class, channel))

    out_dir = src_dir / "noisy"
    out_dir.mkdir(parents=True, exist_ok=True)

    new_chunks = []
    for chunk_meta in meta["chunks"]:
        src_pcm = src_dir / chunk_meta["file"]
        speech = load_pcm16(src_pcm)
        mixed = mix_at_snr(speech, noise_24k, snr_db)
        out_pcm = out_dir / chunk_meta["file"]
        size = save_pcm16(mixed, out_pcm)
        new_chunks.append({
            **chunk_meta,
            "size_bytes": size,
        })

    out_meta = {
        **meta,
        "variant": "noisy",
        "noise_class": noise_class,
        "noise_channel": channel,
        "snr_db": snr_db,
        "noise_source_cache_dir": str(src_dir),
        "chunks": new_chunks,
    }
    with open(out_dir / "metadata.json", "w", encoding="utf-8") as f:
        json.dump(out_meta, f, indent=2, ensure_ascii=False)

    return {
        "task": task_path.stem,
        "status": "ok",
        "noise_class": noise_class,
        "channel": channel,
        "snr_db": snr_db,
        "n_chunks": len(new_chunks),
        "out_dir": str(out_dir),
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--subset", default=str(DEFAULT_SUBSET_FILE),
                        help="path to subset JSON")
    parser.add_argument("--summary", default=None,
                        help="output summary path (default: <subset>_noise_injection.json)")
    parser.add_argument("--source-cache-dir", default=None,
                        help="explicit clean cache dir containing metadata.json; mainly for one-off injections")
    parser.add_argument("--tts-backend", default="openai", choices=["openai", "voice_cloning"])
    parser.add_argument("--clone-manifest", default=None)
    parser.add_argument("--clone-accent", default=None,
                        help="optional CommonVoice accent filter for ablation")
    parser.add_argument("--clone-policy", default="task_hash")
    parser.add_argument("--snr-db", type=float, default=SNR_DB)
    parser.add_argument("--noise-class", default="any",
                        help="DEMAND class or any")
    args = parser.parse_args()
    subset_file = Path(args.subset)
    summary_path = Path(args.summary) if args.summary else subset_file.with_name(subset_file.stem + "_noise_injection.json")

    rng = random.Random(SEED)
    paths = collect_d3_task_paths(subset_file)
    print(f"Loaded {len(paths)} task paths from {subset_file}")

    results = []
    by_class = {}
    for i, p in enumerate(paths, 1):
        try:
            r = inject_for_task(
                p,
                rng,
                source_cache_dir=Path(args.source_cache_dir).expanduser() if args.source_cache_dir else None,
                tts_backend=args.tts_backend,
                clone_manifest=args.clone_manifest,
                clone_accent=args.clone_accent,
                clone_policy=args.clone_policy,
                snr_db=args.snr_db,
                noise_class=args.noise_class,
            )
        except Exception as e:
            r = {"task": p.stem, "status": "fail", "error": f"{type(e).__name__}: {e}"}
        results.append(r)
        if r["status"] == "ok":
            by_class[r["noise_class"]] = by_class.get(r["noise_class"], 0) + 1
        msg = r.get("status")
        if msg == "ok":
            msg = f"ok (noise={r['noise_class']}/{r['channel']}, n={r['n_chunks']})"
        elif msg == "skip_no_cache":
            msg = "SKIP no default cache"
        elif msg == "fail":
            msg = f"FAIL {r.get('error', '')}"
        print(f"  [{i}/{len(paths)}] {p.stem}: {msg}")

    ok = sum(1 for r in results if r["status"] == "ok")
    print(f"\n=== Summary: {ok}/{len(paths)} success ===")
    print("Noise class distribution:")
    for c in NOISE_CLASSES:
        print(f"  {c}: {by_class.get(c, 0)}")

    summary_path.write_text(json.dumps(results, indent=2, ensure_ascii=False))
    print(f"\nSummary written to {summary_path}")


if __name__ == "__main__":
    main()
