"""
TTS 音频缓存管理

将 TTS 生成与评测分离：
- 首次运行自动生成音频并缓存
- 后续运行直接加载缓存
- 通过 transcript_hash 检测 task 内容变更，自动失效旧缓存

v7: proactive task (strength=strong/ambiguous/negative) 自动用 gpt-4o-mini-tts
+ prosody instructions。其他 task 走旧路径 tts-1。
Cache invalidation 通过 metadata 里的 tts_model + prosody_instruction 检测。
"""
import hashlib
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple

from eval.audio.clone_registry import CloneSpeaker, CommonVoiceCloneRegistry, normalize_accent
from eval.audio.tts_generator import TTSGenerator, VoiceCloningTTS
from eval.data.task import Task, MessageRole
from eval.paths import audio_cache_root


# v7 Prosody control: per-strength TTS instructions
# 与 plan.md / scripts/spike_tts_prosody_v3.py 对齐
PROSODY_INSTRUCTIONS = {
    "strong": (
        "Speak confidently and steadily, with clear declarative tone. "
        "Decisive pacing, even rhythm, no filler words."
    ),
    "ambiguous": (
        "Speak with mild hesitation and neutral pacing. "
        "Slight uncertainty, occasional pauses between phrases."
    ),
    "negative": None,  # default ambient prosody (无 instruction)
}


# v8 Prosody control: per-band TTS instructions
# clarify / dilemma / passive 三档独立语调
BAND_PROSODY_INSTRUCTIONS = {
    "clarify": (
        "Speak with a tentative, inquisitive tone, as if working through a partial idea aloud. "
        "Slight upward inflection at the ends of phrases, suggesting open questions. "
        "Pace slightly slower than declarative speech, with brief pauses while gathering thought. "
        "The voice should feel like someone asking for help, not commanding."
    ),
    "dilemma": (
        "Speak in a conflicted, deliberative tone, as if weighing options out loud. "
        "Stretch the option names slightly, with subtle pitch contrast between alternatives. "
        "Pause briefly between mentions of each option, conveying back-and-forth indecision. "
        "The voice should feel torn, oscillating, never settling on a final lean."
    ),
    "passive": (
        "Speak softly, as if thinking aloud to oneself rather than addressing anyone. "
        "Slow pace, drifting cadence, occasional trailing-off at clause ends. "
        "Avoid directive intonation. The tone should feel introspective, distracted, "
        "almost wandering — like someone remembering, imagining, or recounting to "
        "themselves rather than asking a listener for help."
    ),
}


def _resolve_tts_config(task_path: str, default_model: str) -> Tuple[str, Optional[str]]:
    """根据 task 字段选 TTS model + prosody instruction.

    优先级：v8 band > v7 strength > default。

    Returns:
        (tts_model, prosody_instruction)
        - v8 proactive task (has "band")  → ("gpt-4o-mini-tts", BAND prosody)
        - v7 proactive task (has "strength" only) → ("gpt-4o-mini-tts", STRENGTH prosody)
        - 旧 task / reactive               → (default_model, None)
    """
    try:
        with open(task_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        band = data.get("band")
        if band in BAND_PROSODY_INSTRUCTIONS:
            return ("gpt-4o-mini-tts", BAND_PROSODY_INSTRUCTIONS[band])
        # v2 schema: intent.strength 嵌套字段（strong/medium/weak）
        # v7 schema: 顶层 strength 字段（strong/ambiguous/negative）
        strength = data.get("intent", {}).get("strength") or data.get("strength")
        # v2 weak 映射到 v8 passive prosody（recounting/remembering 过去叙述）
        # v7 negative=None 丢了 weak 的 prosody 信号，v2 weak ≈ v8 passive 语义一致
        if strength == "weak":
            return ("gpt-4o-mini-tts", BAND_PROSODY_INSTRUCTIONS["passive"])
        v2_to_v7 = {"strong": "strong", "medium": "ambiguous"}
        strength = v2_to_v7.get(strength, strength)
        if strength in PROSODY_INSTRUCTIONS and PROSODY_INSTRUCTIONS[strength] is not None:
            return ("gpt-4o-mini-tts", PROSODY_INSTRUCTIONS[strength])
    except Exception:
        pass
    return (default_model, None)


def _compute_transcript_hash(task_path: str) -> Optional[str]:
    """从 task JSON 读取或计算 transcript_hash"""
    try:
        with open(task_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        # 优先用 task 里预计算的 hash
        if data.get("transcript_hash"):
            return data["transcript_hash"]
        # 否则现场计算
        transcript = data.get("transcript", [])
        user_texts = [t.get("text", "") for t in transcript if t.get("speaker") == "user"]
        content = json.dumps(user_texts, ensure_ascii=False)
        return hashlib.sha256(content.encode()).hexdigest()[:12]
    except Exception:
        return None


class TTSCache:
    """TTS 音频缓存管理器"""

    def __init__(
        self,
        cache_dir: Optional[str] = None,
        tts_model: str = "tts-1",
        tts_voice: str = "alloy",
        variant: str = "default",
        tts_backend: str = "openai",
        clone_manifest: Optional[str] = None,
        clone_accent: Optional[str] = None,
        clone_policy: str = "task_hash",
        clone_model: str = "tts_models/multilingual/multi-dataset/xtts_v2",
    ):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存根目录
            tts_model: TTS 模型
            tts_voice: TTS 语音
        """
        if variant not in ("default", "no_prosody", "noisy"):
            raise ValueError(f"variant must be default/no_prosody/noisy, got {variant!r}")
        if tts_backend not in ("openai", "voice_cloning"):
            raise ValueError(f"tts_backend must be openai/voice_cloning, got {tts_backend!r}")
        self.cache_dir = Path(cache_dir) if cache_dir else audio_cache_root()
        self.tts_model = tts_model  # default model (used when task lacks strength)
        self.tts_voice = tts_voice
        self.variant = variant
        self.tts_backend = tts_backend
        self.clone_manifest = clone_manifest
        self.clone_accent = self._normalize_clone_filter(clone_accent)
        self.clone_policy = clone_policy
        self.clone_model = clone_model
        # v7: 按 model 缓存 generators（不同 task 可能用不同 TTS model）
        self._generators: Dict[str, TTSGenerator] = {}
        self._clone_generator: Optional[VoiceCloningTTS] = None
        self._clone_registry: Optional[CommonVoiceCloneRegistry] = None

    def _get_cache_path(self, task_path: str) -> Path:
        """
        获取 task 对应的缓存目录路径

        Args:
            task_path: task JSON 文件路径

        Returns:
            缓存目录路径，如 outputs/audio/reactive/gen_000000/
        """
        # resolve symlinks so sampled task dirs reuse original TTS cache
        task_path = Path(task_path).resolve()
        if self.tts_backend == "voice_cloning":
            existing_cache_path = self._find_existing_voice_clone_cache_path(task_path)
            if existing_cache_path is not None:
                return existing_cache_path

        # 从 task 路径提取相对路径
        # data/tasks/seeds/003_ride_direct.json -> seeds/003_ride_direct
        if "tasks" in task_path.parts:
            idx = task_path.parts.index("tasks")
            relative_parts = task_path.parts[idx + 1:]
        else:
            relative_parts = (task_path.stem,)

        # 构建缓存路径
        cache_path = self.cache_dir
        for part in relative_parts[:-1]:  # 不包括文件名
            cache_path = cache_path / part
        cache_path = cache_path / task_path.stem  # 用 task 名作为目录名
        if self.tts_backend == "voice_cloning":
            speaker = self._select_clone_speaker(str(task_path))
            cache_path = cache_path / "voice_clone"
            if self.clone_accent:
                cache_path = cache_path / f"accent_{self.clone_accent}"
            cache_path = cache_path / speaker.speaker_id
        if self.variant != "default":
            cache_path = cache_path / self.variant

        return cache_path

    def _base_task_cache_path(self, task_path: str | Path) -> Path:
        """Return the task-level cache directory before backend-specific suffixes."""
        task_path = Path(task_path).resolve()
        if "tasks" in task_path.parts:
            idx = task_path.parts.index("tasks")
            relative_parts = task_path.parts[idx + 1:]
        else:
            relative_parts = (task_path.stem,)

        cache_path = self.cache_dir
        for part in relative_parts[:-1]:
            cache_path = cache_path / part
        return cache_path / task_path.stem

    def _find_existing_voice_clone_cache_path(self, task_path: str | Path) -> Optional[Path]:
        """Find a valid existing clone cache, including path-dependent legacy caches."""
        base_path = self._base_task_cache_path(task_path) / "voice_clone"
        if self.clone_accent:
            base_path = base_path / f"accent_{self.clone_accent}"
        if not base_path.exists():
            return None

        task_hash = _compute_transcript_hash(str(task_path))
        registry = self._get_clone_registry()
        pattern = "*/metadata.json" if self.variant == "default" else f"*/{self.variant}/metadata.json"
        for metadata_file in sorted(base_path.glob(pattern)):
            try:
                with open(metadata_file, "r", encoding="utf-8") as f:
                    metadata = json.load(f)
            except json.JSONDecodeError:
                continue

            if metadata.get("tts_backend") != "voice_cloning":
                continue
            if metadata.get("tts_model") != self.clone_model:
                continue
            if metadata.get("clone_policy") != self.clone_policy:
                continue
            if metadata.get("clone_filter_accent") != self.clone_accent:
                continue
            if task_hash and metadata.get("transcript_hash") != task_hash:
                continue

            speaker = registry.get_speaker(str(metadata.get("clone_speaker_id") or ""))
            if speaker is None:
                continue
            if metadata.get("clone_speaker_accent") != speaker.accent:
                continue
            if metadata.get("clone_reference_hash") != speaker.reference_hash:
                continue
            if metadata.get("language") != speaker.language:
                continue

            cache_path = metadata_file.parent
            if all((cache_path / chunk.get("file", "")).exists() for chunk in metadata.get("chunks", [])):
                return cache_path
        return None

    def _voice_clone_metadata_is_valid(self, metadata: Dict[str, Any], task_path: str | Path) -> bool:
        if metadata.get("tts_backend") != "voice_cloning":
            print(f"  ⚠️  Cache stale: tts_backend mismatch ({metadata.get('tts_backend')} != voice_cloning)")
            return False
        if metadata.get("tts_model") != self.clone_model:
            print(f"  ⚠️  Cache stale: tts_model mismatch ({metadata.get('tts_model')} != {self.clone_model})")
            return False
        if metadata.get("clone_policy") != self.clone_policy:
            print(f"  ⚠️  Cache stale: clone_policy mismatch ({metadata.get('clone_policy')} != {self.clone_policy})")
            return False
        if metadata.get("clone_filter_accent") != self.clone_accent:
            print(
                f"  ⚠️  Cache stale: clone_filter_accent mismatch "
                f"({metadata.get('clone_filter_accent')} != {self.clone_accent})"
            )
            return False

        speaker = self._get_clone_registry().get_speaker(str(metadata.get("clone_speaker_id") or ""))
        if speaker is None:
            print(f"  ⚠️  Cache stale: unknown clone_speaker_id ({metadata.get('clone_speaker_id')})")
            return False
        if self.clone_accent and normalize_accent(speaker.accent) != self.clone_accent:
            print(f"  ⚠️  Cache stale: speaker accent not in clone filter ({speaker.accent} != {self.clone_accent})")
            return False

        expected = {
            "clone_dataset": "commonvoice",
            "clone_speaker_accent": speaker.accent,
            "clone_reference_hash": speaker.reference_hash,
            "language": speaker.language,
        }
        for key, expected_value in expected.items():
            if metadata.get(key) != expected_value:
                print(
                    f"  ⚠️  Cache stale: {key} mismatch "
                    f"({metadata.get(key)} != {expected_value})"
                )
                return False
        return True

    @staticmethod
    def _normalize_clone_filter(accent: Optional[str]) -> Optional[str]:
        if accent is None:
            return None
        value = str(accent).strip()
        if not value or value.lower() == "any":
            return None
        return normalize_accent(value)

    def _get_clone_registry(self) -> CommonVoiceCloneRegistry:
        if not self.clone_manifest:
            raise ValueError("--clone-manifest is required when --tts-backend voice_cloning")
        if self._clone_registry is None:
            self._clone_registry = CommonVoiceCloneRegistry(
                self.clone_manifest,
                accent=self.clone_accent,
                policy=self.clone_policy,
            )
        return self._clone_registry

    def _select_clone_speaker(self, task_path: str) -> CloneSpeaker:
        registry = self._get_clone_registry()
        return registry.select_speaker(task_path, _compute_transcript_hash(task_path))

    def _expected_clone_metadata(self, task_path: str) -> Dict[str, Any]:
        speaker = self._select_clone_speaker(task_path)
        return {
            "tts_backend": "voice_cloning",
            "tts_model": self.clone_model,
            "clone_dataset": "commonvoice",
            "clone_speaker_id": speaker.speaker_id,
            "clone_filter_accent": self.clone_accent,
            "clone_speaker_accent": speaker.accent,
            "clone_reference_hash": speaker.reference_hash,
            "clone_policy": self.clone_policy,
            "language": speaker.language,
        }

    def has_cache(self, task_path: str) -> bool:
        """
        检查 task 是否有缓存

        Args:
            task_path: task JSON 文件路径

        Returns:
            是否存在有效缓存（内容匹配 + TTS 配置匹配 + 文件完整）
        """
        cache_path = self._get_cache_path(task_path)
        metadata_file = cache_path / "metadata.json"

        if not metadata_file.exists():
            return False

        try:
            with open(metadata_file, 'r', encoding='utf-8') as f:
                metadata = json.load(f)

            # 检查 transcript_hash 是否匹配（防止 task 重新生成后用旧音频）
            task_hash = _compute_transcript_hash(task_path)
            cached_hash = metadata.get("transcript_hash")
            if task_hash and cached_hash and task_hash != cached_hash:
                print(f"  ⚠️  Cache stale: transcript_hash mismatch ({cached_hash} != {task_hash})")
                return False

            if self.tts_backend == "voice_cloning":
                if not self._voice_clone_metadata_is_valid(metadata, task_path):
                    return False
            else:
                if metadata.get("tts_backend", "openai") != "openai":
                    print(f"  ⚠️  Cache stale: tts_backend mismatch ({metadata.get('tts_backend')} != openai)")
                    return False
                # v7: 检查 TTS 配置匹配（model + prosody instruction）
                # 如果 task 现在用 prosody 但 cache 是旧 tts-1，invalidate
                expected_model, expected_instruction = _resolve_tts_config(task_path, self.tts_model)
                if self.variant == "no_prosody":
                    expected_instruction = None
                    if "gpt-4o" not in expected_model:
                        expected_model = "gpt-4o-mini-tts"
                elif self.variant == "noisy":
                    expected_instruction = metadata.get("prosody_instruction")
                    expected_model = metadata.get("tts_model", expected_model)
                if metadata.get("tts_model") != expected_model:
                    print(f"  ⚠️  Cache stale: tts_model mismatch ({metadata.get('tts_model')} != {expected_model})")
                    return False
                if metadata.get("prosody_instruction") != expected_instruction:
                    print(f"  ⚠️  Cache stale: prosody_instruction mismatch")
                    return False

            # 检查所有 chunk 文件是否存在
            for chunk in metadata.get("chunks", []):
                chunk_file = cache_path / chunk["file"]
                if not chunk_file.exists():
                    return False

            return True
        except (json.JSONDecodeError, KeyError):
            return False

    def load_cache(self, task_path: str) -> List[Dict[str, Any]]:
        """
        加载缓存的音频数据

        Args:
            task_path: task JSON 文件路径

        Returns:
            音频数据列表，每项包含 audio, text, timestamp, metadata
        """
        cache_path = self._get_cache_path(task_path)
        metadata_file = cache_path / "metadata.json"

        with open(metadata_file, 'r', encoding='utf-8') as f:
            metadata = json.load(f)

        audio_chunks = []
        for chunk in metadata["chunks"]:
            chunk_file = cache_path / chunk["file"]
            with open(chunk_file, 'rb') as f:
                audio_data = f.read()

            audio_chunks.append({
                'audio': audio_data,
                'text': chunk["text"],
                'timestamp': chunk.get("timestamp", 0.0),
                'metadata': chunk.get("metadata", {})
            })

        return audio_chunks

    def generate_cache(self, task_path: str, task: Optional[Task] = None) -> List[Dict[str, Any]]:
        """
        为 task 生成音频并缓存

        v7: 根据 task strength 字段自动选 TTS model + prosody instruction:
          - proactive (strong/ambiguous/negative) → gpt-4o-mini-tts + prosody
          - reactive / 旧 task                     → tts-1 (默认)

        Args:
            task_path: task JSON 文件路径
            task: Task 对象（可选，如果不传则从文件加载）

        Returns:
            音频数据列表
        """
        # 加载 task
        if task is None:
            with open(task_path, 'r', encoding='utf-8') as f:
                task_data = json.load(f)
            task = Task.from_dict(task_data)

        # v7: 决定本次 TTS 用什么 model + instruction
        if self.tts_backend == "voice_cloning":
            tts_model = self.clone_model
            prosody_instruction = None
            clone_speaker = self._select_clone_speaker(task_path)
        else:
            tts_model, prosody_instruction = _resolve_tts_config(task_path, self.tts_model)
            clone_speaker = None

        if self.variant == "noisy":
            raise RuntimeError(
                "variant='noisy' 不支持在线生成；请先用 scripts/ablation/audio_mix/inject_noise.py "
                f"预生成 noisy chunks。 task: {task_path}"
            )

        if self.variant == "no_prosody" and self.tts_backend == "openai":
            prosody_instruction = None
            if "gpt-4o" not in tts_model:
                tts_model = "gpt-4o-mini-tts"

        # 初始化 TTS 生成器（按 model 缓存，避免每个 task 都新建 client）
        if self.tts_backend == "voice_cloning":
            if self._clone_generator is None:
                self._clone_generator = VoiceCloningTTS(model_name=tts_model)
            generator = self._clone_generator
        else:
            if not hasattr(self, "_generators"):
                self._generators: Dict[str, TTSGenerator] = {}
            if tts_model not in self._generators:
                api_key = os.getenv("OPENAI_API_KEY")
                if not api_key:
                    raise ValueError("OPENAI_API_KEY is required for TTS generation")
                self._generators[tts_model] = TTSGenerator(
                    api_key=api_key,
                    model=tts_model,
                    voice=self.tts_voice,
                )
            generator = self._generators[tts_model]

        if clone_speaker:
            print(
                f"  TTS: backend=voice_cloning, model={tts_model}, "
                f"speaker={clone_speaker.speaker_id}"
                + (f", accent_filter={self.clone_accent}" if self.clone_accent else "")
            )
        elif prosody_instruction:
            print(f"  TTS: model={tts_model}, prosody=enabled")
        elif tts_model != self.tts_model:
            print(f"  TTS: model={tts_model} (no instruction)")

        # 创建缓存目录
        cache_path = self._get_cache_path(task_path)
        cache_path.mkdir(parents=True, exist_ok=True)

        # 生成音频
        audio_chunks = []
        metadata_chunks = []

        chunk_index = 0
        for chunk in task.chunks:
            if chunk.role != MessageRole.USER:
                continue

            chunk_index += 1
            print(f"  Generating audio {chunk_index}: \"{chunk.content[:50]}...\"" if len(chunk.content) > 50 else f"  Generating audio {chunk_index}: \"{chunk.content}\"")

            # 生成音频（带 prosody if applicable）
            if clone_speaker:
                audio_data = generator.text_to_audio(
                    chunk.content,
                    output_format="pcm16",
                    instructions=prosody_instruction,
                    speaker_wav=[str(p) for p in clone_speaker.reference_wavs],
                    language=clone_speaker.language,
                )
            else:
                audio_data = generator.text_to_audio(
                    chunk.content,
                    output_format="pcm16",
                    instructions=prosody_instruction,
                )

            # 保存音频文件
            chunk_filename = f"chunk_{chunk_index:03d}.pcm"
            chunk_file = cache_path / chunk_filename
            with open(chunk_file, 'wb') as f:
                f.write(audio_data)

            # 记录数据
            audio_chunks.append({
                'audio': audio_data,
                'text': chunk.content,
                'timestamp': chunk.timestamp,
                'metadata': chunk.metadata
            })

            metadata_chunks.append({
                'index': chunk_index,
                'text': chunk.content,
                'timestamp': chunk.timestamp,
                'metadata': chunk.metadata,
                'file': chunk_filename,
                'size_bytes': len(audio_data)
            })

        # 保存 metadata
        metadata = {
            'task_name': task.name,
            'transcript_hash': _compute_transcript_hash(task_path),
            'tts_backend': self.tts_backend,
            'tts_model': tts_model,                      # v7: 实际使用的 model
            'tts_voice': self.tts_voice,
            'prosody_instruction': prosody_instruction,  # v7: cache invalidation key
            'sample_rate': 24000,
            'format': 'pcm16',
            'generated_at': datetime.now().isoformat(),
            'chunks': metadata_chunks
        }
        if clone_speaker:
            metadata.update({
                "clone_dataset": "commonvoice",
                "clone_speaker_id": clone_speaker.speaker_id,
                "clone_filter_accent": self.clone_accent,
                "clone_speaker_accent": clone_speaker.accent,
                "clone_reference_hash": clone_speaker.reference_hash,
                "clone_policy": self.clone_policy,
                "language": clone_speaker.language,
                "clone_reference_wavs": [str(p) for p in clone_speaker.reference_wavs],
            })

        metadata_file = cache_path / "metadata.json"
        with open(metadata_file, 'w', encoding='utf-8') as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

        print(f"  Cached {len(audio_chunks)} audio chunks to {cache_path}")

        return audio_chunks

    def get_or_generate(self, task_path: str, task: Optional[Task] = None) -> List[Dict[str, Any]]:
        """
        获取音频数据：有缓存则加载，无缓存则生成

        Args:
            task_path: task JSON 文件路径
            task: Task 对象（可选）

        Returns:
            音频数据列表
        """
        if self.has_cache(task_path):
            print(f"  Loading cached audio from {self._get_cache_path(task_path)}")
            return self.load_cache(task_path)
        else:
            print(f"  No cache found, generating audio...")
            return self.generate_cache(task_path, task)


def generate_all_caches(
    tasks_dir: str,
    cache_dir: Optional[str] = None,
    variant: str = "default",
    tts_backend: str = "openai",
    clone_manifest: Optional[str] = None,
    clone_accent: Optional[str] = None,
    clone_policy: str = "task_hash",
    clone_model: str = "tts_models/multilingual/multi-dataset/xtts_v2",
):
    """
    批量生成所有 task 的音频缓存

    Args:
        tasks_dir: tasks 目录路径
        cache_dir: 缓存目录路径
    """
    tasks_path = Path(tasks_dir)
    cache = TTSCache(
        cache_dir=cache_dir,
        variant=variant,
        tts_backend=tts_backend,
        clone_manifest=clone_manifest,
        clone_accent=clone_accent,
        clone_policy=clone_policy,
        clone_model=clone_model,
    )

    task_files = list(tasks_path.glob("**/*.json"))
    print(f"Found {len(task_files)} task files")

    for i, task_file in enumerate(task_files, 1):
        print(f"\n[{i}/{len(task_files)}] {task_file}")

        if cache.has_cache(str(task_file)):
            print("  Cache already exists, skipping")
            continue

        try:
            cache.generate_cache(str(task_file))
        except Exception as e:
            print(f"  Error: {e}")
