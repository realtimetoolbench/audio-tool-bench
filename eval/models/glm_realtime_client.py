"""
Zhipu GLM Realtime API client.
Supports GLM-Realtime real-time voice dialogue.

Auth: direct API key (Bearer {api_key}); JWT is not used.
Protocol: similar to OpenAI Realtime, but requires beta_fields configuration.
Audio: WAV input, PCM output.
"""
import asyncio
import json
import base64
import io
import time
import wave
from typing import Optional, Dict, Any, List
import websockets
from websockets.client import WebSocketClientProtocol


class GLMRealtimeClient:
    """Zhipu GLM Realtime API client."""

    def __init__(
        self,
        api_key: str,
        model: str = "glm-realtime",
        voice: str = "male",
        tool_executor=None
    ):
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.tool_executor = tool_executor
        self.base_url = "wss://open.bigmodel.cn/api/paas/v4/realtime"

        self.ws: Optional[WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        self.conversation_history: List[Dict[str, Any]] = []

        # Response collection.
        self.current_response: Optional[Dict[str, Any]] = None
        self.audio_buffer: List[bytes] = []
        self.transcript_buffer: List[str] = []

    async def connect(self):
        """Open the WebSocket connection (direct API key auth)."""
        headers = {"Authorization": f"Bearer {self.api_key}"}

        self.ws = await websockets.connect(
            self.base_url, additional_headers=headers, open_timeout=15
        )

        # Wait for session.created (skip heartbeats).
        for _ in range(10):
            event = await self._receive_event()
            if event.get("type") == "session.created":
                self.session_id = event.get("session", {}).get("id")
                print(f"✓ GLM Session created: {self.session_id}")
                break
            if event.get("type") == "heartbeat":
                continue
        else:
            raise Exception("Never received session.created from GLM")

        await self._configure_session()

    async def _configure_session(self):
        """Configure the session — beta_fields is required."""
        tools = []
        if self.tool_executor:
            for tool in self.tool_executor.get_tools_for_openai():
                if tool.get("type") == "function" and "function" in tool:
                    tools.append({
                        "type": "function",
                        "name": tool["function"]["name"],
                        "description": tool["function"]["description"],
                        "parameters": tool["function"]["parameters"]
                    })
            print(f"[DEBUG] Configured {len(tools)} tools for GLM")

        config = {
            "type": "session.update",
            "session": {
                "input_audio_format": "wav",
                "output_audio_format": "pcm",
                "modalities": ["audio", "text"],
                "beta_fields": {
                    "chat_mode": "audio",
                    "tts_source": "e2e",
                    "auto_search": False
                },
                "tools": tools
            }
        }

        await self._send_event(config)

        # Wait for session.updated.
        for _ in range(10):
            event = await self._receive_event()
            if event.get("type") == "session.updated":
                print("✓ GLM session configured")
                break
            if event.get("type") == "heartbeat":
                continue
            if event.get("type") == "error":
                print(f"[DEBUG] GLM config error: {event}")
                break

    async def disconnect(self):
        """Close the connection."""
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def _send_event(self, event: Dict[str, Any]):
        if not self.ws:
            raise Exception("Not connected")
        await self.ws.send(json.dumps(event))

    async def _receive_event(self) -> Dict[str, Any]:
        if not self.ws:
            raise Exception("Not connected")
        message = await self.ws.recv()
        return json.loads(message)

    async def send_audio_and_wait_response(
        self,
        audio_data: bytes,
        chunk_size: int = 4800,
        max_tool_rounds: int = 5
    ) -> Dict[str, Any]:
        """Send audio and wait for the response."""
        start_time = time.time()

        self.audio_buffer = []
        self.transcript_buffer = []
        self.current_response = {
            "llm_calls": [],
            "tool_executions": [],
            "audio_chunks": [],
            "transcript": "",
            "events": []
        }

        # PCM → WAV (GLM input format is wav).
        wav_buf = io.BytesIO()
        with wave.open(wav_buf, 'wb') as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(24000)
            wf.writeframes(audio_data)
        wav_b64 = base64.b64encode(wav_buf.getvalue()).decode('utf-8')

        # Send the audio.
        ts = int(time.time() * 1000)
        print(f"  Sending {len(audio_data)} bytes of audio (WAV)...")
        await self._send_event({
            "type": "input_audio_buffer.append",
            "audio": wav_b64,
            "client_timestamp": ts
        })

        await asyncio.sleep(0.2)
        await self._send_event({
            "type": "input_audio_buffer.commit",
            "client_timestamp": ts + 100
        })

        print(f"  Creating response...")
        await self._send_event({"type": "response.create"})

        # Tool-call loop.
        tool_round = 0
        while tool_round < max_tool_rounds:
            response_complete = False
            current_transcript = ""
            current_function_calls = []

            while not response_complete:
                event = await self._receive_event()
                event_type = event.get("type", "")
                self.current_response["events"].append(event)

                if event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        self.audio_buffer.append(base64.b64decode(audio_b64))

                elif event_type == "response.audio_transcript.delta":
                    delta = event.get("delta", "")
                    self.transcript_buffer.append(delta)
                    current_transcript += delta

                elif event_type == "response.text.delta":
                    # audio_transcript.delta already captures the content; skip text.delta to avoid duplicates.
                    pass

                elif event_type == "response.output_item.done":
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        fc = {
                            "call_id": item.get("call_id"),
                            "name": item.get("name"),
                            "arguments": item.get("arguments", "")
                        }
                        current_function_calls.append(fc)
                        print(f"  Function call: {fc['name']}")

                elif event_type == "response.done":
                    response_complete = True

                    llm_call = {
                        "round": tool_round + 1,
                        "content": current_transcript,
                        "tool_calls": None
                    }

                    if current_function_calls and self.tool_executor:
                        print(f"  Detected {len(current_function_calls)} function call(s)")
                        llm_call["tool_calls"] = []

                        for fc in current_function_calls:
                            func_name = fc["name"]
                            try:
                                func_args = json.loads(fc["arguments"])
                            except Exception:
                                func_args = {}

                            print(f"    Executing: {func_name}({func_args})")
                            llm_call["tool_calls"].append({
                                "id": fc["call_id"],
                                "name": func_name,
                                "arguments": func_args
                            })

                            result = self.tool_executor.execute_tool(func_name, func_args)
                            self.current_response["tool_executions"].append({
                                "tool_call_id": fc["call_id"],
                                "tool_name": func_name,
                                "arguments": func_args,
                                "result": result
                            })

                            await self._send_function_call_output(
                                fc["call_id"], result.get("output", "")
                            )

                        self.current_response["llm_calls"].append(llm_call)
                        tool_round += 1

                        if tool_round < max_tool_rounds:
                            await self._send_event({"type": "response.create"})
                            break
                    else:
                        self.current_response["llm_calls"].append(llm_call)
                        self.current_response["transcript"] = current_transcript
                        tool_round = max_tool_rounds
                        break

                elif event_type == "heartbeat":
                    continue

                elif event_type == "error":
                    print(f"  Error: {event}")
                    raise Exception(f"GLM API Error: {event}")

        end_time = time.time()

        transcript = self.current_response.get("transcript", "")
        if transcript:
            print(f"  Transcript: {transcript[:200]}")

        return {
            "assistant_response": transcript,
            "llm_calls": self.current_response["llm_calls"],
            "tool_executions": self.current_response["tool_executions"],
            "audio_data": b"".join(self.audio_buffer),
            "total_latency_ms": (end_time - start_time) * 1000,
            "events": self.current_response["events"]
        }

    async def _send_function_call_output(self, call_id: str, output: str):
        """Send the function call result."""
        await self._send_event({
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output
            }
        })

    def reset(self):
        self.conversation_history = []
        self.audio_buffer = []
        self.transcript_buffer = []

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        return self.conversation_history.copy()
