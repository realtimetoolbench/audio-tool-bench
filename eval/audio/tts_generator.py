"""
TTS audio generators.

The OpenAI generator is the legacy default. VoiceCloningTTS is an optional local
XTTS backend used when the pipeline is configured with CommonVoice references.
Both generators return raw 24kHz mono PCM16 bytes for the realtime runners.
"""
import math
import os
import tempfile
import wave
from pathlib import Path
from openai import OpenAI
from typing import Optional, Sequence


class TTSGenerator:
    """OpenAI TTS 音频生成器"""

    def __init__(
        self,
        api_key: Optional[str] = None,
        model: str = "tts-1",
        voice: str = "alloy"
    ):
        """
        初始化 TTS 生成器

        Args:
            api_key: OpenAI API key，如果为 None 则从环境变量读取
            model: TTS 模型（tts-1 / tts-1-hd / gpt-4o-mini-tts）
            voice: 语音类型（alloy, echo, fable, onyx, nova, shimmer）
        """
        # Use US OpenAI endpoint
        self.client = OpenAI(
            api_key=api_key,
            base_url="https://us.api.openai.com/v1"
        )
        self.model = model
        self.voice = voice

    def text_to_audio(
        self,
        text: str,
        output_format: str = "pcm16",
        instructions: Optional[str] = None,
    ) -> bytes:
        """
        将文本转换为音频。

        Args:
            text: 要转换的文本
            output_format: 输出格式（pcm16 用于 Realtime API）
            instructions: prosody 控制（仅 gpt-4o-mini-tts 支持）。
                          tts-1 不支持，会被忽略。

        Returns:
            音频数据（bytes）
        """
        kwargs = {
            "model": self.model,
            "voice": self.voice,
            "input": text,
            "response_format": "pcm",  # 24kHz mono PCM16 (匹配 Realtime API)
        }
        # 仅 gpt-4o 系列 TTS 支持 instructions 参数
        if instructions and "gpt-4o" in self.model:
            kwargs["instructions"] = instructions

        response = self.client.audio.speech.create(**kwargs)
        return response.content

    def batch_text_to_audio(
        self,
        texts: list[str],
        output_format: str = "pcm16",
        instructions: Optional[str] = None,
    ) -> list[bytes]:
        """
        批量将文本转换为音频。

        Args:
            texts: 文本列表
            output_format: 输出格式
            instructions: prosody 控制（仅 gpt-4o-mini-tts 支持）

        Returns:
            音频数据列表
        """
        audio_list = []
        for text in texts:
            audio = self.text_to_audio(text, output_format, instructions=instructions)
            audio_list.append(audio)
        return audio_list


class VoiceCloningTTS:
    """Local XTTS v2 voice-cloning generator.

    Coqui TTS is intentionally imported lazily so the default OpenAI TTS path
    does not require local voice-cloning dependencies.
    """

    def __init__(
        self,
        model_name: str = "tts_models/multilingual/multi-dataset/xtts_v2",
        device: Optional[str] = None,
    ):
        self.model_name = model_name
        self.device = device or os.getenv("VOICE_CLONING_DEVICE") or self._default_device()
        try:
            from TTS.api import TTS as CoquiTTS
        except ImportError as exc:
            raise ImportError(
                "VoiceCloningTTS requires the Coqui TTS package. Install it with "
                "`pip install TTS` before using --tts-backend voice_cloning."
            ) from exc

        local_model_path = os.getenv("VOICE_CLONING_MODEL_PATH")
        if local_model_path:
            model_dir = Path(local_model_path).expanduser()
            config_path = model_dir / "config.json"
            if not model_dir.exists():
                raise FileNotFoundError(f"VOICE_CLONING_MODEL_PATH does not exist: {model_dir}")
            if not config_path.exists():
                raise FileNotFoundError(f"XTTS config.json not found under VOICE_CLONING_MODEL_PATH: {config_path}")
            self.tts = CoquiTTS(
                model_path=str(model_dir),
                config_path=str(config_path),
                progress_bar=False,
            )
        else:
            self.tts = CoquiTTS(model_name)
        if hasattr(self.tts, "to"):
            self.tts = self.tts.to(self.device)

    @staticmethod
    def _default_device() -> str:
        try:
            import torch

            if torch.cuda.is_available():
                return "cuda"
            return "cpu"
        except ImportError:
            return "cpu"

    def text_to_audio(
        self,
        text: str,
        output_format: str = "pcm16",
        instructions: Optional[str] = None,
        speaker_wav: Optional[str | Sequence[str]] = None,
        language: str = "en",
    ) -> bytes:
        if output_format != "pcm16":
            raise ValueError(f"VoiceCloningTTS only supports pcm16 output, got {output_format!r}")
        if not speaker_wav:
            raise ValueError("speaker_wav is required for VoiceCloningTTS")

        # XTTS does not accept OpenAI-style prosody instructions. The argument
        # stays in the signature so TTSCache can call both generators uniformly.
        _ = instructions

        tmp_path = None
        try:
            with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
                tmp_path = Path(tmp.name)

            self.tts.tts_to_file(
                text=text,
                speaker_wav=list(speaker_wav) if isinstance(speaker_wav, tuple) else speaker_wav,
                language=language,
                file_path=str(tmp_path),
                split_sentences=True,
            )
            return self._wav_to_pcm16(tmp_path)
        finally:
            if tmp_path and tmp_path.exists():
                tmp_path.unlink()

    def batch_text_to_audio(
        self,
        texts: list[str],
        output_format: str = "pcm16",
        instructions: Optional[str] = None,
        speaker_wav: Optional[str | Sequence[str]] = None,
        language: str = "en",
    ) -> list[bytes]:
        return [
            self.text_to_audio(
                text,
                output_format=output_format,
                instructions=instructions,
                speaker_wav=speaker_wav,
                language=language,
            )
            for text in texts
        ]

    @classmethod
    def _wav_to_pcm16(cls, wav_path: Path, target_sr: int = 24000) -> bytes:
        with wave.open(str(wav_path), "rb") as wf:
            sample_rate = wf.getframerate()
            channels = wf.getnchannels()
            sample_width = wf.getsampwidth()
            frames = wf.readframes(wf.getnframes())

        import numpy as np

        if sample_width == 2:
            samples = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
        elif sample_width == 4:
            samples = np.frombuffer(frames, dtype=np.int32).astype(np.float32) / 2147483648.0
        elif sample_width == 1:
            samples = (np.frombuffer(frames, dtype=np.uint8).astype(np.float32) - 128.0) / 128.0
        else:
            raise ValueError(f"Unsupported WAV sample width: {sample_width * 8}-bit")

        if channels > 1:
            samples = samples.reshape(-1, channels).mean(axis=1)

        if sample_rate != target_sr:
            samples = cls._resample(samples, sample_rate, target_sr)

        samples = np.clip(samples, -1.0, 1.0)
        return (samples * 32767).astype(np.int16).tobytes()

    @staticmethod
    def _resample(samples, sample_rate: int, target_sr: int):
        try:
            from scipy.signal import resample_poly
        except ImportError as exc:
            raise ImportError(
                "Resampling voice-cloned audio requires scipy when XTTS output "
                f"sample rate is {sample_rate}Hz instead of {target_sr}Hz."
            ) from exc

        gcd = math.gcd(sample_rate, target_sr)
        return resample_poly(samples, target_sr // gcd, sample_rate // gcd)
