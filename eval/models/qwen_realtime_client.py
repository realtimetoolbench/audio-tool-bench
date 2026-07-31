"""
Alibaba Cloud Bailian Qwen Realtime API client.

DashScope's Qwen3.x Omni Realtime protocol is compatible with OpenAI Realtime
(matching event names, turn_detection semantics, and native function calling).
By subclassing OpenAIRealtimeClient we reuse the entire event loop, tool-call,
and interruption paths, overriding only the endpoint and session-config differences.

Differences:
- WebSocket endpoint: dashscope.aliyuncs.com (cn) / dashscope-intl.aliyuncs.com (intl).
- Authorization header: the OpenAI-Beta header is not required.
- session.input_audio_transcription: DashScope does not support whisper-1; drop it.
- voice: Qwen uses Ethan / Cherry / Aiden etc. (not alloy).
- turn_detection: only server_vad is supported; semantic_vad is not.
"""
import asyncio
import json
from typing import Optional, Dict, Any
import websockets

from eval.models.openai_realtime_client import OpenAIRealtimeClient


class QwenRealtimeClient(OpenAIRealtimeClient):
    """Alibaba Cloud Qwen Realtime API client (built on the OpenAI Realtime protocol)."""

    def __init__(
        self,
        api_key: str,
        model: str = "qwen3-omni-flash-realtime",
        voice: str = "Ethan",
        tool_executor=None,
        region: str = "cn",
        turn_detection_mode: str = "manual",
    ):
        if turn_detection_mode == "vad":
            turn_detection_mode = "server_vad"
        if turn_detection_mode == "semantic_vad":
            raise ValueError(
                "Qwen DashScope realtime API does not support semantic_vad; use server_vad or manual."
            )

        if region == "intl":
            base_url = "wss://dashscope-intl.aliyuncs.com/api-ws/v1/realtime"
        else:
            base_url = "wss://dashscope.aliyuncs.com/api-ws/v1/realtime"

        super().__init__(
            api_key=api_key,
            model=model,
            voice=voice,
            tool_executor=tool_executor,
            base_url=base_url,
            turn_detection_mode=turn_detection_mode,
        )
        self.region = region

    async def connect(self):
        """Override the parent connect: drop the OpenAI-Beta header; DashScope needs only Authorization."""
        url = f"{self.base_url}?model={self.model}"
        headers = {"Authorization": f"Bearer {self.api_key}"}

        for attempt in range(3):
            try:
                self.ws = await websockets.connect(
                    url, additional_headers=headers, open_timeout=30,
                )
                break
            except (asyncio.TimeoutError, OSError) as e:
                if attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(f"  Qwen WebSocket connect failed ({e}), retry in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise

        # Handshake: DashScope sends session.created, same as OpenAI.
        for _ in range(10):
            event = await self._receive_event()
            if event["type"] == "session.created":
                self.session_id = event["session"]["id"]
                print(f"✓ Qwen Session created: {self.session_id}")
                break
            if event["type"] == "ping":
                continue
            print(f"[DEBUG] Skipping event during Qwen connect: {event['type']}")
        else:
            raise Exception("Never received session.created from DashScope")

        await self._configure_session()

    async def _configure_session(self):
        """Override the parent _configure_session: remove whisper-1 transcription (DashScope has built-in ASR)."""
        if self.turn_detection_mode == "server_vad":
            turn_detection: Optional[Dict[str, Any]] = {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 500,
                "silence_duration_ms": 800,
            }
        else:
            turn_detection = None

        config: Dict[str, Any] = {
            "type": "session.update",
            "session": {
                "voice": self.voice,
                "input_audio_format": "pcm16",
                "output_audio_format": "pcm16",
                "modalities": ["text", "audio"],
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
            print(f"[DEBUG] Configured {len(tools)} tools for Qwen")

        await self._send_event(config)

        while True:
            event = await self._receive_event()
            if event["type"] == "session.updated":
                print("✓ Qwen session configured")
                break
            print(f"[DEBUG] Skipping event during Qwen setup: {event['type']}")
