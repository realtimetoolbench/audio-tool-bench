"""
xAI Grok Voice Agent API client.
Compatible with the OpenAI Realtime API format.
"""
import json
from typing import Optional, Dict, Any
from eval.models.openai_realtime_client import OpenAIRealtimeClient


class GrokRealtimeClient(OpenAIRealtimeClient):
    """xAI Grok Voice Agent API client (OpenAI Realtime API compatible)."""

    # Voices available on Grok: Ara, Rex, Sal, Eve, Leo.
    VOICES = ["Ara", "Rex", "Sal", "Eve", "Leo"]

    def __init__(
        self,
        api_key: str,
        model: str = "grok-3-fast",
        voice: str = "Ara",
        tool_executor=None,
        turn_detection_mode: str = "manual",
    ):
        """
        Initialize the Grok Voice Agent API client.

        Args:
            api_key: xAI API key.
            model: Model to use (grok-3-fast, grok-voice-think-fast-1.0, etc.).
            voice: Voice (Ara, Rex, Sal, Eve, Leo).
            tool_executor: Tool executor (optional).
            turn_detection_mode: "manual" or "server_vad" (Grok does not support semantic_vad).
        """
        # Validate the voice.
        if voice not in self.VOICES:
            voice = "Ara"

        super().__init__(
            api_key=api_key,
            model=model,
            voice=voice,
            tool_executor=tool_executor,
            base_url="wss://api.x.ai/v1/realtime",
            turn_detection_mode=turn_detection_mode,
        )
        # Grok's server_vad is insensitive to all-zero silence padding (in practice it
        # only emits pings); use 3s padding plus an explicit commit as a fallback to
        # trigger the server's auto-response.
        self.vad_silence_padding_bytes = 144000  # 3s @ 24kHz PCM16
        self.vad_force_commit = True

    async def _configure_session(self):
        """Override the parent _configure_session with Grok-friendly defaults.

        - silence_duration_ms uses Grok's default 200ms (shorter; paired with silence
          padding it triggers faster).
        - prefix_padding_ms uses Grok's default 300ms.
        - input_audio_transcription uses grok-voice-listen-fast-1.0 (replaces OpenAI whisper-1).
        """
        if self.turn_detection_mode == "server_vad":
            turn_detection: Optional[Dict[str, Any]] = {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 200,
            }
        elif self.turn_detection_mode == "semantic_vad":
            raise ValueError("Grok does not support semantic_vad; use server_vad or manual.")
        else:
            turn_detection = None

        config: Dict[str, Any] = {
            "type": "session.update",
            "session": {
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "turn_detection": turn_detection,
            }
        }

        if self.tool_executor:
            tools_chat_format = self.tool_executor.get_tools_for_openai()
            tools = []
            for tool in tools_chat_format:
                if tool.get("type") == "function" and "function" in tool:
                    tools.append({
                        "type": "function",
                        "name": tool["function"]["name"],
                        "description": tool["function"]["description"],
                        "parameters": tool["function"]["parameters"]
                    })
            config["session"]["tools"] = tools
            config["session"]["tool_choice"] = "auto"
            print(f"[DEBUG] Configured {len(tools)} tools for Grok")

        await self._send_event(config)

        while True:
            event = await self._receive_event()
            if event["type"] == "session.updated":
                print("✓ Grok session configured")
                break
            print(f"[DEBUG] Skipping event during Grok setup: {event['type']}")
