"""
MiniMax Realtime API client.
Supports real-time voice dialogue with MiniMax Speech models.

Note: MiniMax's Realtime API documentation is still incomplete; this
implementation is based on the best available information and may need
adjustment once the real API responses are observed.
"""
import asyncio
import json
import base64
import time
from typing import Optional, Dict, Any, List
import websockets
from websockets.client import WebSocketClientProtocol


class MiniMaxRealtimeClient:
    """MiniMax Realtime API client."""

    def __init__(
        self,
        api_key: str,
        model: str = "speech-2.6",
        voice: str = "female-tianmei",  # MiniMax prebuilt voice
        tool_executor=None,
        group_id: str = ""  # MiniMax requires a group_id
    ):
        """
        Initialize the MiniMax Realtime API client.

        Args:
            api_key: MiniMax API key.
            model: Model name.
            voice: Voice ID.
            tool_executor: Tool executor.
            group_id: MiniMax Group ID.
        """
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.tool_executor = tool_executor
        self.group_id = group_id

        # MiniMax Realtime API endpoint (may need updating).
        self.base_url = "wss://api.minimax.io/ws/v1/realtime"

        self.ws: Optional[WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        self.conversation_history: List[Dict[str, Any]] = []

        # Response collection.
        self.current_response: Optional[Dict[str, Any]] = None
        self.audio_buffer: List[bytes] = []
        self.transcript_buffer: List[str] = []

    async def connect(self):
        """Open the WebSocket connection."""
        url = f"{self.base_url}?model={self.model}"
        if self.group_id:
            url += f"&group_id={self.group_id}"

        headers = {
            "Authorization": f"Bearer {self.api_key}"
        }

        import ssl
        ssl_context = ssl.create_default_context()

        self.ws = await websockets.connect(
            url,
            additional_headers=headers,
            ssl=ssl_context
        )

        # Wait for connection confirmation.
        event = await self._receive_event()
        event_type = event.get("event") or event.get("type")

        if event_type in ["connected_success", "session.created"]:
            self.session_id = event.get("session", {}).get("id") or event.get("session_id")
            print(f"✓ MiniMax Session created: {self.session_id}")
            await self._configure_session()
        else:
            print(f"[DEBUG] First event: {event}")

    async def _configure_session(self):
        """Configure the session."""
        config = {
            "event": "session.update",
            "session": {
                "voice_id": self.voice,
                "model": self.model,
                "input_audio_format": "pcm",
                "output_audio_format": "pcm",
                "sample_rate": 16000
            }
        }

        # Add tool configuration.
        if self.tool_executor:
            tools_openai = self.tool_executor.get_tools_for_openai()
            tools = []
            for tool in tools_openai:
                if tool.get("type") == "function" and "function" in tool:
                    tools.append({
                        "type": "function",
                        "name": tool["function"]["name"],
                        "description": tool["function"]["description"],
                        "parameters": tool["function"]["parameters"]
                    })
            config["session"]["tools"] = tools
            print(f"[DEBUG] Configured {len(tools)} tools for MiniMax")

        await self._send_event(config)

        # Wait for confirmation.
        try:
            event = await asyncio.wait_for(self._receive_event(), timeout=5.0)
            event_type = event.get("event") or event.get("type")
            if event_type in ["session.updated", "task_started"]:
                print("✓ MiniMax session configured")
        except asyncio.TimeoutError:
            print("[DEBUG] No session.updated confirmation received")

    async def disconnect(self):
        """Close the connection."""
        if self.ws:
            # Send the close event.
            try:
                await self._send_event({"event": "task_finish"})
            except:
                pass
            await self.ws.close()
            self.ws = None

    async def _send_event(self, event: Dict[str, Any]):
        """Send an event."""
        if not self.ws:
            raise Exception("Not connected")
        await self.ws.send(json.dumps(event))

    async def _receive_event(self) -> Dict[str, Any]:
        """Receive an event."""
        if not self.ws:
            raise Exception("Not connected")
        message = await self.ws.recv()
        return json.loads(message)

    async def send_audio_chunk(self, audio_data: bytes):
        """Send an audio chunk."""
        # MiniMax may use hex encoding instead of base64.
        audio_hex = audio_data.hex()
        event = {
            "event": "input_audio_buffer.append",
            "audio": audio_hex
        }
        await self._send_event(event)

    async def commit_audio_buffer(self):
        """Commit the input audio buffer."""
        event = {"event": "input_audio_buffer.commit"}
        await self._send_event(event)

    async def create_response(self):
        """Trigger response generation."""
        event = {"event": "response.create"}
        await self._send_event(event)

    async def send_audio_and_wait_response(
        self,
        audio_data: bytes,
        chunk_size: int = 4800,
        max_tool_rounds: int = 5
    ) -> Dict[str, Any]:
        """Send audio and wait for the response."""
        start_time = time.time()

        # Reset.
        self.audio_buffer = []
        self.transcript_buffer = []
        self.current_response = {
            "llm_calls": [],
            "tool_executions": [],
            "audio_chunks": [],
            "transcript": "",
            "events": []
        }

        # Send audio in chunks.
        print(f"  Sending {len(audio_data)} bytes of audio...")
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            await self.send_audio_chunk(chunk)
            await asyncio.sleep(0.05)

        await asyncio.sleep(0.2)
        await self.commit_audio_buffer()
        print(f"  Creating response...")
        await self.create_response()

        # Tool-call loop.
        tool_round = 0
        timeout_seconds = 30

        while tool_round < max_tool_rounds:
            response_complete = False
            current_transcript = ""
            current_function_calls = []
            start_wait = time.time()

            while not response_complete:
                if time.time() - start_wait > timeout_seconds:
                    print(f"  WARNING: Response timeout")
                    break

                try:
                    event = await asyncio.wait_for(self._receive_event(), timeout=10.0)
                except asyncio.TimeoutError:
                    continue

                event_type = event.get("event") or event.get("type", "")
                self.current_response["events"].append(event)

                # Handle audio data.
                if event_type in ["response.audio.delta", "audio"]:
                    audio_data = event.get("delta") or event.get("data", {}).get("audio")
                    if audio_data:
                        # MiniMax may use hex encoding.
                        try:
                            audio_bytes = bytes.fromhex(audio_data)
                        except:
                            audio_bytes = base64.b64decode(audio_data)
                        self.audio_buffer.append(audio_bytes)

                # Handle transcripts.
                elif event_type in ["response.audio_transcript.delta", "transcript"]:
                    delta = event.get("delta") or event.get("text", "")
                    self.transcript_buffer.append(delta)
                    current_transcript += delta

                # Handle function calls.
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

                # Response finished.
                elif event_type in ["response.done", "is_final"]:
                    is_final = event.get("is_final", True)
                    if is_final:
                        response_complete = True

                        llm_call = {
                            "round": tool_round + 1,
                            "content": current_transcript,
                            "tool_calls": None
                        }

                        if current_function_calls and self.tool_executor:
                            llm_call["tool_calls"] = []
                            for fc in current_function_calls:
                                func_name = fc["name"]
                                try:
                                    func_args = json.loads(fc["arguments"])
                                except:
                                    func_args = {}

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

                            self.current_response["llm_calls"].append(llm_call)
                            tool_round += 1

                            if tool_round < max_tool_rounds:
                                await self.create_response()
                                break
                        else:
                            self.current_response["llm_calls"].append(llm_call)
                            self.current_response["transcript"] = current_transcript
                            tool_round = max_tool_rounds
                            break

                elif event_type == "error":
                    print(f"  Error: {event}")
                    raise Exception(f"MiniMax API Error: {event}")

            if not response_complete:
                break

        end_time = time.time()

        return {
            "assistant_response": self.current_response["transcript"],
            "llm_calls": self.current_response["llm_calls"],
            "tool_executions": self.current_response["tool_executions"],
            "audio_data": b"".join(self.audio_buffer),
            "total_latency_ms": (end_time - start_time) * 1000,
            "events": self.current_response["events"]
        }

    def reset(self):
        """Reset the conversation."""
        self.conversation_history = []
        self.audio_buffer = []
        self.transcript_buffer = []

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Return the conversation history."""
        return self.conversation_history.copy()
