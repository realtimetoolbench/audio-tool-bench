"""
OpenAI Realtime API client.
"""
import asyncio
import json
import base64
import time
import os
from typing import Optional, Dict, Any, List, Callable
import websockets
from websockets.client import WebSocketClientProtocol


class OpenAIRealtimeClient:
    """OpenAI Realtime API client."""

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-realtime-mini",
        voice: str = "alloy",
        tool_executor=None,
        base_url: str = "wss://us.api.openai.com/v1/realtime",
        turn_detection_mode: str = "manual",
    ):
        """
        Initialize the Realtime API client.

        Args:
            api_key: OpenAI API key.
            model: Model to use.
            voice: Voice (alloy, echo, fable, onyx, nova, shimmer).
            tool_executor: Tool executor (optional).
            base_url: WebSocket endpoint.
            turn_detection_mode: Turn-detection mode.
                - "manual": manual commit + create_response (the runner drives pacing).
                - "vad" / "server_vad": server VAD endpoints on audio silence (threshold + silence_duration_ms).
                - "semantic_vad": server semantic VAD endpoints based on semantics (eagerness=low, up to 8s decision window).
        """
        # "vad" is an alias for "server_vad" (backward compat).
        if turn_detection_mode == "vad":
            turn_detection_mode = "server_vad"
        if turn_detection_mode not in ("manual", "server_vad", "semantic_vad"):
            raise ValueError(
                f"turn_detection_mode must be 'manual', 'server_vad', or 'semantic_vad', got {turn_detection_mode!r}"
            )
        self.api_key = api_key
        self.model = model
        self.voice = voice
        self.tool_executor = tool_executor
        self.base_url = base_url
        self.turn_detection_mode = turn_detection_mode

        self.ws: Optional[WebSocketClientProtocol] = None
        self.session_id: Optional[str] = None
        self.conversation_history: List[Dict[str, Any]] = []

        # Event handlers.
        self.event_handlers: Dict[str, List[Callable]] = {}

        # Response collection.
        self.current_response: Optional[Dict[str, Any]] = None
        self.audio_buffer: List[bytes] = []
        self.transcript_buffer: List[str] = []

    def _uses_ga_api(self) -> bool:
        return self.model.startswith("gpt-realtime")

    async def connect(self):
        """Open the WebSocket connection."""
        url = f"{self.base_url}?model={self.model}"
        print(f"[DEBUG] OpenAI Realtime URL: {url}")
        headers = {
            "Authorization": f"Bearer {self.api_key}",
        }
        if not self._uses_ga_api():
            headers["OpenAI-Beta"] = "realtime=v1"

        # Retry the handshake (API can queue during peaks).
        for attempt in range(3):
            try:
                self.ws = await websockets.connect(
                    url,
                    additional_headers=headers,
                    open_timeout=30,
                    proxy=os.getenv("OPENAI_REALTIME_PROXY", True),
                    ping_timeout=None,
                )
                break
            except (asyncio.TimeoutError, OSError) as e:
                if attempt < 2:
                    wait = 5 * (attempt + 1)
                    print(f"  WebSocket connect failed ({e}), retry in {wait}s...")
                    await asyncio.sleep(wait)
                else:
                    raise

        # Wait for the handshake to complete (OpenAI: session.created, Grok: conversation.created).
        for _ in range(10):
            event = await self._receive_event()
            if event["type"] == "session.created":
                self.session_id = event["session"]["id"]
                print(f"✓ Session created: {self.session_id}")
                break
            if event["type"] == "conversation.created":
                # Grok emits conversation.created instead of session.created.
                self.session_id = event.get("conversation", {}).get("id", "grok-session")
                print(f"✓ Conversation created (Grok): {self.session_id}")
                break
            if event["type"] == "ping":
                continue
            print(f"[DEBUG] Skipping event during connect: {event['type']} — {event.get('error', '')}")
        else:
            raise Exception("Never received session/conversation.created")

        # Configure the session.
        await self._configure_session()

    async def _configure_session(self):
        """Configure session parameters (native tools rather than instructions)."""
        if self.turn_detection_mode == "server_vad":
            # silence_duration_ms = 800ms: covers measured P99 mid-sentence TTS pauses
            # (660ms) plus a buffer. Avoids splitting long utterances into multiple turns
            # at natural pauses (reactive/gen_000001 was measured with a 1340ms pause).
            turn_detection = {
                "type": "server_vad",
                "threshold": 0.5,
                "prefix_padding_ms": 300,
                "silence_duration_ms": 800,
            }
        elif self.turn_detection_mode == "semantic_vad":
            # eagerness: low (max 8s) > medium (4s) > high (2s).
            # create_response / interrupt_response explicitly enabled so the server auto-responds.
            turn_detection = {
                "type": "semantic_vad",
                "eagerness": "low",
                "create_response": True,
                "interrupt_response": True,
            }
        else:
            turn_detection = None  # manual: disable VAD; the runner handles commit + create_response.

        if self._uses_ga_api():
            config = {
                "type": "session.update",
                "session": {
                    "type": "realtime",
                    "output_modalities": ["audio"],
                    "audio": {
                        "input": {
                            "format": {"type": "audio/pcm", "rate": 24000},
                            "turn_detection": turn_detection,
                        },
                        "output": {
                            "format": {"type": "audio/pcm", "rate": 24000},
                            "voice": self.voice,
                        },
                    },
                }
            }
        else:
            config = {
                "type": "session.update",
                "session": {
                    "voice": self.voice,
                    "input_audio_format": "pcm16",
                    "output_audio_format": "pcm16",
                    "input_audio_transcription": {
                        "model": "whisper-1"
                    },
                    "turn_detection": turn_detection,
                }
            }

        # Use the native tools configuration.
        if self.tool_executor:
            tools_chat_format = self.tool_executor.get_tools_for_openai()

            # Convert to Realtime API format (flattened structure).
            tools = []
            for tool in tools_chat_format:
                if tool.get("type") == "function" and "function" in tool:
                    # Realtime API needs the flattened format.
                    tools.append({
                        "type": "function",
                        "name": tool["function"]["name"],
                        "description": tool["function"]["description"],
                        "parameters": tool["function"]["parameters"]
                    })

            config["session"]["tools"] = tools
            config["session"]["tool_choice"] = "auto"
            print(f"[DEBUG] Configured {len(tools)} native tools")
            print(f"[DEBUG] Tools: {json.dumps(tools, indent=2, ensure_ascii=False)}")

        print(f"[DEBUG] Sending session config: {json.dumps(config, indent=2)}")
        await self._send_event(config)

        # Wait for the session.updated ack (skip intermediate non-critical events like conversation.created).
        while True:
            event = await self._receive_event()
            if event["type"] == "session.updated":
                print("✓ Session configured with native function calling")
                break
            if event["type"] == "error":
                raise Exception(f"session.update failed: {event.get('error', event)}")
            # Skip extra handshake events from providers such as Grok.
            print(f"[DEBUG] Skipping event during setup: {event['type']}")

    async def disconnect(self):
        """Close the connection."""
        if self.ws:
            await self.ws.close()
            self.ws = None

    async def _send_event(self, event: Dict[str, Any]):
        """Send an event to the server."""
        if not self.ws:
            raise Exception("Not connected")
        await self.ws.send(json.dumps(event))

    async def _receive_event(self) -> Dict[str, Any]:
        """Receive a server event."""
        if not self.ws:
            raise Exception("Not connected")
        message = await self.ws.recv()
        event = json.loads(message)
        event_type_aliases = {
            "response.output_audio.delta": "response.audio.delta",
            "response.output_audio.done": "response.audio.done",
            "response.output_audio_transcript.delta": "response.audio_transcript.delta",
            "response.output_audio_transcript.done": "response.audio_transcript.done",
            "response.output_text.delta": "response.text.delta",
            "response.output_text.done": "response.text.done",
        }
        event["type"] = event_type_aliases.get(event.get("type"), event.get("type"))
        return event

    async def send_audio_chunk(self, audio_data: bytes):
        """
        Send an audio chunk to the input buffer.

        Args:
            audio_data: PCM16-formatted audio bytes.
        """
        if len(audio_data) % 2:
            audio_data += b"\x00"
        audio_base64 = base64.b64encode(audio_data).decode('utf-8')
        event = {
            "type": "input_audio_buffer.append",
            "audio": audio_base64
        }
        await self._send_event(event)

    async def commit_audio_buffer(self):
        """Commit the audio buffer to create a user message."""
        event = {"type": "input_audio_buffer.commit"}
        await self._send_event(event)

    async def create_response(self, modalities: Optional[List[str]] = None):
        """Manually trigger response generation.

        modalities defaults to None → the server uses the session default (audio + text);
        the model replies with audio and streams the transcript via response.audio_transcript.delta.
        For the text baseline pass ["text"] to force text-only responses.
        """
        event = {"type": "response.create"}
        if modalities is not None:
            if self._uses_ga_api():
                event["response"] = {"output_modalities": modalities}
            else:
                event["response"] = {"modalities": modalities}
        await self._send_event(event)

    async def send_text_message(self, text: str, role: str = "user"):
        """Send a text message (used to inject conversation history or return tool results)."""
        # The content type is "text" for assistant messages and "input_text" for user messages.
        if role == "assistant":
            content_type = "text"
        else:
            content_type = "input_text"

        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": role,
                "content": [
                    {
                        "type": content_type,
                        "text": text
                    }
                ]
            }
        }
        await self._send_event(event)

    async def send_audio_and_wait_response(
        self,
        audio_data: bytes,
        chunk_size: int = 4800,
        max_tool_rounds: int = 5,
        audio_already_sent: bool = False,
    ) -> Dict[str, Any]:
        """
        Send audio and wait for the full response (supports multiple tool-call rounds).

        Args:
            audio_data: Full audio bytes.
            chunk_size: Send chunk size in bytes.
            max_tool_rounds: Maximum number of tool-call rounds.
            audio_already_sent: VAD post-interrupt only — the audio was already sent in
                                send_audio_with_interrupt; skip send + commit / create_response
                                and just wait for the response.

        Returns:
            A dict with the response and metadata.
        """
        start_time = time.time()

        # Reset the response collector.
        self.audio_buffer = []
        self.transcript_buffer = []
        self.current_response = {
            "llm_calls": [],
            "tool_executions": [],
            "audio_chunks": [],
            "transcript": "",
            "events": []
        }

        # Latency timestamps (ms).
        audio_commit_ts = None  # time audio send finished
        first_speech_ts = None  # time of the first audio response
        first_tool_call_ts = None  # time of the first tool call

        # Send the audio in chunks.
        if audio_already_sent:
            # VAD post-interrupt only: audio already sent in send_audio_with_interrupt; just wait.
            print(f"  Audio already sent (VAD post-interrupt mode) — waiting for response...")
            audio_commit_ts = None
        else:
            print(f"  Sending {len(audio_data)} bytes of audio... (mode={self.turn_detection_mode})")
            for i in range(0, len(audio_data), chunk_size):
                chunk = audio_data[i:i + chunk_size]
                await self.send_audio_chunk(chunk)
                await asyncio.sleep(0.05)

            if self.turn_detection_mode != "manual":
                # server_vad / semantic_vad: silence padding lets server VAD detect speech_stopped.
                # Subclasses can override vad_silence_padding_bytes (PCM16 24kHz: 48000=1s, 144000=3s).
                # Some models (e.g. Grok) are insensitive to pure-zero silence and need longer padding.
                silence_bytes = getattr(self, "vad_silence_padding_bytes", 48000)
                silence_padding = b'\x00' * silence_bytes
                for i in range(0, len(silence_padding), chunk_size):
                    await self.send_audio_chunk(silence_padding[i:i + chunk_size])
                    await asyncio.sleep(0.05)
                # Subclasses (e.g. Grok) can set vad_force_commit=True to explicitly commit after silence.
                if getattr(self, "vad_force_commit", False):
                    await self.commit_audio_buffer()
                    print(f"  Sent silence padding + manual commit (mode={self.turn_detection_mode})")
                else:
                    print(f"  Sent silence padding, waiting for VAD speech_stopped... (mode={self.turn_detection_mode})")
                audio_commit_ts = time.time() * 1000
            else:
                await asyncio.sleep(0.2)
                await self.commit_audio_buffer()
                audio_commit_ts = time.time() * 1000
                print(f"  Creating response...")
                await self.create_response()

        # Tool-call loop.
        tool_round = 0
        while tool_round < max_tool_rounds:
            response_complete = False
            current_transcript = ""
            current_function_calls = []
            current_function_call = None

            # Wait for the response to complete.
            while not response_complete:
                event = await self._receive_event()
                event_type = event["type"]
                self.current_response["events"].append(event)

                if event_type == "response.created":
                    print(f"  Response created (round {tool_round + 1})")

                elif event_type == "input_audio_buffer.speech_started":
                    # VAD mode: server detected the user starting to speak (logged only; no flow change).
                    pass

                elif event_type == "input_audio_buffer.speech_stopped":
                    # VAD mode: server detected the user stopping → it will auto-commit.
                    if audio_commit_ts is None:
                        audio_commit_ts = time.time() * 1000
                    print(f"  VAD speech_stopped — server will auto-commit + respond")
                    # late_return: send the pending dangling result back before the server auto-creates a response.
                    pending = getattr(self, "_pending_dangling_result", None)
                    if pending:
                        await self._send_function_call_output(pending["call_id"], pending["output"])
                        print(f"  [Late return] sent pending dangling result")
                        self._pending_dangling_result = None

                elif event_type == "input_audio_buffer.committed":
                    # VAD mode: server's auto-commit is done.
                    pass

                elif event_type == "response.audio.delta":
                    # Record the time of the first audio response.
                    if first_speech_ts is None:
                        first_speech_ts = time.time() * 1000
                    audio_base64 = event.get("delta", "")
                    if audio_base64:
                        audio_bytes = base64.b64decode(audio_base64)
                        self.audio_buffer.append(audio_bytes)
                        self.current_response["audio_chunks"].append(audio_bytes)

                elif event_type == "response.audio_transcript.delta":
                    delta = event.get("delta", "")
                    self.transcript_buffer.append(delta)
                    current_transcript += delta

                elif event_type == "response.audio_transcript.done":
                    current_transcript = event.get("transcript", "")
                    if current_transcript:
                        print(f"  Transcript: {current_transcript}")

                elif event_type == "response.function_call_arguments.delta":
                    # Native function calling: collect function-call arguments (for debugging).
                    if not current_function_call:
                        current_function_call = {
                            "call_id": event.get("call_id"),
                            "name": event.get("name"),
                            "arguments": ""
                        }
                    current_function_call["arguments"] += event.get("delta", "")

                elif event_type == "response.function_call_arguments.done":
                    # Function-call arguments are complete (logged only, for debugging).
                    if current_function_call and current_function_call.get("name"):
                        print(f"  Function call complete: {current_function_call['name']}")
                    current_function_call = None  # reset; do not add to the list

                elif event_type == "response.output_item.done":
                    # An output item is done; it may contain a function_call.
                    # This is the canonical source of complete function-call info.
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        # Record the time of the first tool call.
                        if first_tool_call_ts is None:
                            first_tool_call_ts = time.time() * 1000
                        fc = {
                            "call_id": item.get("call_id"),
                            "name": item.get("name"),
                            "arguments": item.get("arguments", "")
                        }
                        # Append only from output_item to avoid duplicates.
                        current_function_calls.append(fc)
                        print(f"  Function call from output_item: {fc['name']}")

                elif event_type == "response.done":
                    response_complete = True
                    response_data = event["response"]

                    # Debug: log response status.
                    status = response_data.get("status")
                    if status == "failed":
                        print(f"  [DEBUG] Response failed: {response_data.get('status_details', {})}")

                    # Accumulate this round's transcript into the session transcript (even if this round called tools).
                    if current_transcript:
                        if self.current_response["transcript"]:
                            self.current_response["transcript"] += " " + current_transcript
                        else:
                            self.current_response["transcript"] = current_transcript

                    # Record the LLM call.
                    llm_call = {
                        "round": tool_round + 1,
                        "finish_reason": response_data.get("status"),
                        "content": current_transcript,
                        "tool_calls": None
                    }

                    # Check whether any tool calls happened.
                    if current_function_calls:
                        print(f"  Detected {len(current_function_calls)} native function call(s)")
                        llm_call["tool_calls"] = []

                        # Execute the tools.
                        for fc in current_function_calls:
                            func_name = fc["name"]
                            try:
                                func_args = json.loads(fc["arguments"])
                            except:
                                func_args = {}

                            print(f"    Executing: {func_name}({func_args})")

                            tool_call_record = {
                                "id": fc["call_id"],
                                "name": func_name,
                                "arguments": func_args
                            }
                            llm_call["tool_calls"].append(tool_call_record)

                            # Execute the tool.
                            if self.tool_executor:
                                result = self.tool_executor.execute_tool(func_name, func_args)

                                # Record the tool execution.
                                self.current_response["tool_executions"].append({
                                    "tool_call_id": fc["call_id"],
                                    "tool_name": func_name,
                                    "arguments": func_args,
                                    "result": result,
                                    "latency_ms": result.get("latency_ms", 0)
                                })

                                # Send the tool result back to the model.
                                await self._send_function_call_output(
                                    fc["call_id"],
                                    result.get("output", "")
                                )

                        self.current_response["llm_calls"].append(llm_call)

                        tool_round += 1

                        # If we still have rounds left, create a new response.
                        # In VAD mode the server may have auto-responded already →
                        # conversation_already_has_active_response; the error handler ignores it.
                        if tool_round < max_tool_rounds:
                            print(f"  Creating next response...")
                            await self.create_response()
                            break  # advance to the next round
                        else:
                            print(f"  Reached max tool rounds ({max_tool_rounds})")
                            tool_round = max_tool_rounds
                            break

                    else:
                        # No tool calls; done (transcript was already accumulated on response.done entry).
                        self.current_response["llm_calls"].append(llm_call)
                        tool_round = max_tool_rounds  # exit the loop
                        break

                elif event_type == "error":
                    err = event.get("error", {})
                    code = err.get("code", "")
                    msg = err.get("message", "") or ""
                    # In VAD mode, conversation_already_has_active_response is a race:
                    # the server's auto-response already fired; no further action needed.
                    # DashScope / Grok may omit the code field — judge by message instead.
                    is_active_response_race = (
                        code == "conversation_already_has_active_response"
                        or "already has an active response" in msg.lower()
                    )
                    if is_active_response_race:
                        print(f"  VAD auto-response race (ignored): {msg or code}")
                    else:
                        print(f"  Error: {err}")
                        raise Exception(f"API Error: {err}")

        end_time = time.time()

        # Compute latency (relative to audio_commit_ts).
        latency = {}
        if audio_commit_ts:
            if first_speech_ts:
                latency["speech_ms"] = first_speech_ts - audio_commit_ts
            if first_tool_call_ts:
                latency["tool_call_ms"] = first_tool_call_ts - audio_commit_ts

        # Build the return value.
        result = {
            "assistant_response": self.current_response["transcript"],
            "llm_calls": self.current_response["llm_calls"],
            "tool_executions": self.current_response["tool_executions"],
            "audio_data": b"".join(self.audio_buffer),
            "total_latency_ms": (end_time - start_time) * 1000,
            "events": self.current_response["events"],
            "latency": latency
        }

        return result

    async def send_audio_with_interrupt(
        self,
        audio_data: bytes,
        interrupt_trigger: Dict[str, Any],
        interrupt_audio: bytes,
        chunk_size: int = 4800,
        max_tool_rounds: int = 5,
    ) -> Dict[str, Any]:
        """
        Send audio and wait for the response, interrupting under the configured condition.

        Two trigger types:
        1. keyword (v3.0): watch the transcript and interrupt when the keyword is hit.
        2. tool_phase (v3.1): interrupt when a dangling_tool is detected — global VAD only.

        VAD mode (server_vad / semantic_vad): send interrupt_audio + silence padding;
                 the server VAD auto-cancels the old response (keyword) or starts a new one
                 (tool_phase). Returns next_audio_sent=True so the runner skips audio send
                 on the next round.
        Manual mode (keyword only): on keyword hit → response.cancel → return (the runner
                  sends the interrupt-turn audio naturally on the next round).

        Args:
            audio_data: Audio bytes of the previous turn.
            interrupt_trigger: {"type": "keyword"|"tool_phase", ...}
            interrupt_audio: Audio for the interrupting turn (PCM16 24kHz mono); required in
                             VAD mode, ignored in manual mode.

        Returns:
            A partial response with the interrupted flag (and any tool calls that ran).
            Additionally returns next_audio_sent=True in VAD mode.
        """
        trigger_type = interrupt_trigger.get("type", "keyword")

        # tool_phase trigger only supports global VAD (v3.1 design: session is VAD from the start).
        if trigger_type == "tool_phase" and self.turn_detection_mode == "manual":
            raise NotImplementedError(
                "tool_phase interrupt requires --turn-detection server_vad (or semantic_vad). "
                "Manual mode is no longer supported for v3.1 tool-phase tasks."
            )

        start_time = time.time()

        self.audio_buffer = []
        self.transcript_buffer = []
        self.current_response = {
            "llm_calls": [],
            "tool_executions": [],
            "audio_chunks": [],
            "transcript": "",
            "events": [],
        }

        # Send the audio.
        print(f"  Sending {len(audio_data)} bytes of audio (with interrupt monitoring, mode={self.turn_detection_mode})...")
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            await self.send_audio_chunk(chunk)
            await asyncio.sleep(0.05)

        if self.turn_detection_mode != "manual":
            # VAD mode: silence padding lets the server VAD detect speech_stopped.
            # Subclasses can override vad_silence_padding_bytes (Grok uses 144000=3s).
            silence_bytes = getattr(self, "vad_silence_padding_bytes", 48000)
            silence_padding = b'\x00' * silence_bytes
            for i in range(0, len(silence_padding), chunk_size):
                await self.send_audio_chunk(silence_padding[i:i + chunk_size])
                await asyncio.sleep(0.05)
            # Subclasses such as Grok can set vad_force_commit=True to explicitly commit
            # as a fallback (server VAD does not respond to pure silence).
            if getattr(self, "vad_force_commit", False):
                await self.commit_audio_buffer()
                print(f"  Sent silence padding + manual commit (mode={self.turn_detection_mode})")
            else:
                print(f"  Sent silence padding, waiting for VAD speech_stopped... (mode={self.turn_detection_mode})")
        else:
            await asyncio.sleep(0.2)
            await self.commit_audio_buffer()
            await self.create_response()

        keyword = interrupt_trigger.get("keyword", "").lower()
        timeout_s = interrupt_trigger.get("timeout_s", 5.0)
        # Forced fallback: interrupt unconditionally after receiving 2 seconds of audio.
        # 24kHz 16-bit mono = 48000 bytes/s → 2s = 96000 bytes.
        force_interrupt_audio_bytes = 2.0 * 24000 * 2

        # Reset the timeout origin: start the clock only once the model begins speaking.
        speech_started = False
        speech_start_time = None
        accumulated_transcript = ""
        accumulated_audio_bytes = 0
        triggered_by = None
        tool_round = 0

        # Tool-call + keyword-detection loop.
        while tool_round < max_tool_rounds:
            response_complete = False
            current_transcript = ""
            current_function_calls = []
            current_function_call = None

            while not response_complete:
                # Forced interrupt after enough audio has been received.
                # Disabled in v3.1 (tool_phase) mode to avoid interrupting during the
                # "speech intro" phase so the model has a chance to emit the
                # function_call that hits the dangling intercept. v3.0 (keyword) keeps the original behavior.
                if (
                    trigger_type == "keyword"
                    and speech_started
                    and accumulated_audio_bytes >= force_interrupt_audio_bytes
                ):
                    audio_secs = accumulated_audio_bytes / (24000 * 2)
                    print(f"  Forced interrupt ({audio_secs:.1f}s of audio received)")
                    triggered_by = "forced"
                    break

                # Timeout fallback: measured against wall-clock time once the model starts speaking.
                # Speech-based timeout is also disabled in tool_phase mode (same reason); use a long recv timeout instead.
                if trigger_type == "keyword" and speech_started:
                    elapsed = time.time() - speech_start_time
                    recv_timeout = max(0.1, timeout_s - elapsed)
                    if elapsed > timeout_s:
                        print(f"  Interrupt timeout ({timeout_s}s after speech start)")
                        triggered_by = "timeout"
                        break
                else:
                    recv_timeout = 30.0  # use a long timeout during tool execution and throughout tool_phase

                try:
                    event = await asyncio.wait_for(
                        self._receive_event(), timeout=recv_timeout
                    )
                except asyncio.TimeoutError:
                    if speech_started:
                        print(f"  Interrupt timeout ({timeout_s}s after speech start)")
                        triggered_by = "timeout"
                    else:
                        print(f"  Timeout waiting for response (no speech yet)")
                    break

                event_type = event["type"]
                self.current_response["events"].append(event)

                if event_type == "response.created":
                    print(f"  Response created (round {tool_round + 1}, interrupt mode)")

                elif event_type == "input_audio_buffer.speech_started":
                    # VAD mode: server detected the user starting to speak (logged only).
                    pass

                elif event_type == "input_audio_buffer.speech_stopped":
                    # VAD mode: server detected the user stopping → it will auto-commit and trigger a response.
                    print(f"  VAD speech_stopped — server will auto-respond")

                elif event_type == "input_audio_buffer.committed":
                    pass

                elif event_type == "response.audio.delta":
                    if not speech_started:
                        speech_started = True
                        speech_start_time = time.time()
                        print(f"  Speech started — interrupt monitoring active")
                    audio_base64 = event.get("delta", "")
                    if audio_base64:
                        audio_bytes = base64.b64decode(audio_base64)
                        self.audio_buffer.append(audio_bytes)
                        accumulated_audio_bytes += len(audio_bytes)

                elif event_type == "response.audio_transcript.delta":
                    if not speech_started:
                        speech_started = True
                        speech_start_time = time.time()
                        print(f"  Speech started — interrupt monitoring active")
                    delta = event.get("delta", "")
                    accumulated_transcript += delta
                    current_transcript += delta
                    # Keyword detection.
                    if keyword and keyword in accumulated_transcript.lower():
                        print(f"  Interrupt keyword '{keyword}' detected in: ...{accumulated_transcript[-60:]}")
                        triggered_by = "keyword"
                        break

                elif event_type == "response.audio_transcript.done":
                    current_transcript = event.get("transcript", current_transcript)

                elif event_type == "response.function_call_arguments.delta":
                    if not current_function_call:
                        current_function_call = {
                            "call_id": event.get("call_id"),
                            "name": event.get("name"),
                            "arguments": "",
                        }
                    current_function_call["arguments"] += event.get("delta", "")

                elif event_type == "response.function_call_arguments.done":
                    if current_function_call and current_function_call.get("name"):
                        print(f"  Function call complete: {current_function_call['name']}")
                    current_function_call = None

                elif event_type == "response.output_item.done":
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        fc = {
                            "call_id": item.get("call_id"),
                            "name": item.get("name"),
                            "arguments": item.get("arguments", ""),
                        }
                        current_function_calls.append(fc)
                        print(f"  Function call from output_item: {fc['name']}")

                elif event_type == "response.done":
                    response_complete = True
                    response_data = event["response"]
                    status = response_data.get("status")

                    if status == "failed":
                        print(f"  [DEBUG] Response failed: {response_data.get('status_details', {})}")

                    llm_call = {
                        "round": tool_round + 1,
                        "finish_reason": status,
                        "content": current_transcript,
                        "tool_calls": None,
                    }

                    if current_function_calls:
                        # tool_phase interrupt: when a dangling_tool is detected → open VAD → send interrupt audio.
                        # The model perceives the user's speech autonomously and responds.
                        dangling_tool = interrupt_trigger.get("dangling_tool") if trigger_type == "tool_phase" else None
                        # dangling_return: "never" (no_return) | "during_inserted" (late) | "before_resume" (early)
                        dangling_return = interrupt_trigger.get("dangling_return", "never")
                        if dangling_tool:
                            dangling_match = [fc for fc in current_function_calls if fc["name"] == dangling_tool]
                            if dangling_match:
                                print(f"  Dangling tool detected: {dangling_tool} — VAD interrupt mode (return={dangling_return})")
                                llm_call["tool_calls"] = []

                                # Run any tools before the dangling_tool (return their results normally).
                                for fc in current_function_calls:
                                    func_name = fc["name"]
                                    try:
                                        func_args = json.loads(fc["arguments"])
                                    except Exception:
                                        func_args = {}

                                    is_dangling = fc["name"] == dangling_tool
                                    llm_call["tool_calls"].append({
                                        "id": fc["call_id"],
                                        "name": func_name,
                                        "arguments": func_args,
                                        "dangling": is_dangling,
                                        "dangling_return": dangling_return if is_dangling else None,
                                    })

                                    if is_dangling:
                                        if dangling_return == "never":
                                            # no_return: do not execute, do not return.
                                            print(f"    Dangling (not executed): {func_name}({func_args})")
                                        elif dangling_return == "before_resume":
                                            # early_return: execute and return immediately; the model enters VAD with the result.
                                            if self.tool_executor:
                                                result = self.tool_executor.execute_tool(func_name, func_args)
                                                self.current_response["tool_executions"].append({
                                                    "tool_call_id": fc["call_id"],
                                                    "tool_name": func_name,
                                                    "arguments": func_args,
                                                    "result": result,
                                                    "latency_ms": result.get("latency_ms", 0),
                                                    "dangling_return": "before_resume",
                                                })
                                                await self._send_function_call_output(
                                                    fc["call_id"], result.get("output", "")
                                                )
                                                print(f"    Dangling (early_return): {func_name}({func_args}) — result sent immediately")
                                        elif dangling_return == "during_inserted":
                                            # late_return: execute but do not return yet; store it as pending.
                                            if self.tool_executor:
                                                result = self.tool_executor.execute_tool(func_name, func_args)
                                                self.current_response["tool_executions"].append({
                                                    "tool_call_id": fc["call_id"],
                                                    "tool_name": func_name,
                                                    "arguments": func_args,
                                                    "result": result,
                                                    "latency_ms": result.get("latency_ms", 0),
                                                    "dangling_return": "during_inserted",
                                                })
                                                self._pending_dangling_result = {
                                                    "call_id": fc["call_id"],
                                                    "output": result.get("output", ""),
                                                }
                                                print(f"    Dangling (late_return): {func_name}({func_args}) — result pending")
                                        break

                                    # Non-dangling: execute and return normally.
                                    if self.tool_executor:
                                        result = self.tool_executor.execute_tool(func_name, func_args)
                                        self.current_response["tool_executions"].append({
                                            "tool_call_id": fc["call_id"],
                                            "tool_name": func_name,
                                            "arguments": func_args,
                                            "result": result,
                                            "latency_ms": result.get("latency_ms", 0),
                                        })
                                        await self._send_function_call_output(
                                            fc["call_id"], result.get("output", "")
                                        )
                                        print(f"    Executed (normal): {func_name}({func_args})")

                                self.current_response["llm_calls"].append(llm_call)
                                triggered_by = "vad_tool_phase"
                                break

                        # Normal tool call: execute, then continue to the next round.
                        print(f"  Detected {len(current_function_calls)} function call(s) (executing before interrupt)")
                        llm_call["tool_calls"] = []

                        for fc in current_function_calls:
                            func_name = fc["name"]
                            try:
                                func_args = json.loads(fc["arguments"])
                            except Exception:
                                func_args = {}

                            print(f"    Executing: {func_name}({func_args})")
                            tool_call_record = {
                                "id": fc["call_id"],
                                "name": func_name,
                                "arguments": func_args,
                            }
                            llm_call["tool_calls"].append(tool_call_record)

                            if self.tool_executor:
                                result = self.tool_executor.execute_tool(func_name, func_args)
                                self.current_response["tool_executions"].append({
                                    "tool_call_id": fc["call_id"],
                                    "tool_name": func_name,
                                    "arguments": func_args,
                                    "result": result,
                                    "latency_ms": result.get("latency_ms", 0),
                                })
                                await self._send_function_call_output(
                                    fc["call_id"], result.get("output", "")
                                )

                        self.current_response["llm_calls"].append(llm_call)
                        tool_round += 1

                        if tool_round < max_tool_rounds:
                            print(f"  Creating next response (tools done, waiting for speech)...")
                            await self.create_response()
                            break  # advance to the next round
                        else:
                            print(f"  Reached max tool rounds")
                            break
                    else:
                        # No tool calls → the speech response is complete and was not interrupted.
                        self.current_response["llm_calls"].append(llm_call)
                        self.current_response["transcript"] = current_transcript
                        accumulated_transcript = current_transcript

                        end_time = time.time()
                        print(f"  Response completed before interrupt trigger")
                        return {
                            "assistant_response": accumulated_transcript,
                            "llm_calls": self.current_response["llm_calls"],
                            "tool_executions": self.current_response["tool_executions"],
                            "audio_data": b"".join(self.audio_buffer),
                            "total_latency_ms": (end_time - start_time) * 1000,
                            "events": self.current_response["events"],
                            "latency": {},
                            "interrupted": False,
                        }

                elif event_type == "error":
                    err = event.get("error", {})
                    code = err.get("code", "")
                    if code in ("response_cancel_not_active", "conversation_already_has_active_response"):
                        print(f"  VAD race condition (ignored): {code}")
                    else:
                        print(f"  Error: {err}")
                        raise Exception(f"API Error: {err}")

            # Check whether an interrupt fired.
            if triggered_by:
                break

        # Post-interrupt handling.
        next_audio_sent = False
        if triggered_by == "vad_tool_phase":
            # Global VAD mode only: send the interrupt audio; on the next round the runner uses
            # send_audio_and_wait_response (audio_already_sent=True) to handle the VAD's autonomous
            # response (including delivering the late_return pending result).
            # Simulate tool-execution delay (let the model finish emitting the dangling function_call before pausing).
            await asyncio.sleep(1.0)

            # Send interrupt audio + 1s silence padding so the VAD detects speech_stopped.
            print(f"  Sending interrupt audio ({len(interrupt_audio)} bytes) via global VAD...")
            await self._send_audio_chunks(interrupt_audio, chunk_size, append_silence=True)
            next_audio_sent = True

        elif triggered_by:
            # v3.0 keyword / forced / timeout interrupt.
            if self.turn_detection_mode != "manual":
                # VAD mode (server_vad / semantic_vad): send the interrupt-turn audio directly;
                # the server VAD auto-cancels the current response.
                print(f"  Sending interrupt audio ({len(interrupt_audio)} bytes) to trigger VAD interrupt... (mode={self.turn_detection_mode})")
                # Stream the send concurrently with draining old response events.
                send_task = asyncio.create_task(self._send_audio_chunks(interrupt_audio, chunk_size))

                # Drain the old response events until response.done(cancelled).
                old_response_done = False
                for _ in range(500):
                    try:
                        event = await asyncio.wait_for(self._receive_event(), timeout=15.0)
                    except asyncio.TimeoutError:
                        print(f"  Timeout draining old response after VAD interrupt")
                        break
                    self.current_response["events"].append(event)
                    et = event["type"]
                    if et == "response.audio_transcript.delta":
                        accumulated_transcript += event.get("delta", "")
                    elif et == "response.done":
                        status = event["response"].get("status")
                        print(f"  Old response done (status={status})")
                        old_response_done = True
                        break
                    elif et == "error":
                        err = event.get("error", {})
                        code = err.get("code", "")
                        if code in ("response_cancel_not_active", "response_already_done"):
                            print(f"  VAD interrupt race (ignored): {code}")
                        else:
                            print(f"  Error during VAD interrupt: {err}")

                # Wait for the audio send to finish.
                await send_task
                next_audio_sent = True
                if not old_response_done:
                    print(f"  Warning: old response not drained cleanly, may affect next response")
            else:
                # Manual mode: send response.cancel.
                print(f"  Sending response.cancel...")
                await self._send_event({"type": "response.cancel"})

                # Drain remaining events until response.done (plus any trailing error).
                for _ in range(200):
                    try:
                        event = await asyncio.wait_for(self._receive_event(), timeout=10.0)
                    except asyncio.TimeoutError:
                        print(f"  Timeout waiting for response.done after cancel")
                        break
                    self.current_response["events"].append(event)
                    if event["type"] == "response.audio_transcript.delta":
                        accumulated_transcript += event.get("delta", "")
                    elif event["type"] == "response.done":
                        status = event["response"].get("status")
                        print(f"  Response cancelled (status={status})")
                        # response.done may be followed by an error event (cancel race condition).
                        try:
                            extra = await asyncio.wait_for(self._receive_event(), timeout=0.5)
                            self.current_response["events"].append(extra)
                            if extra["type"] == "error":
                                print(f"  Post-cancel error (drained): {extra.get('error', {}).get('code', '?')}")
                        except asyncio.TimeoutError:
                            pass
                        break
                    elif event["type"] == "error":
                        err = event.get("error", {})
                        print(f"  Cancel error (ignored): {err.get('code', err)}")
                        break

        end_time = time.time()

        self.current_response["transcript"] = accumulated_transcript
        self.current_response["llm_calls"].append({
            "round": tool_round + 1,
            "finish_reason": "cancelled" if triggered_by else "completed",
            "content": accumulated_transcript,
            "tool_calls": None,
        })

        return {
            "assistant_response": accumulated_transcript,
            "llm_calls": self.current_response["llm_calls"],
            "tool_executions": self.current_response["tool_executions"],
            "audio_data": b"".join(self.audio_buffer),
            "total_latency_ms": (end_time - start_time) * 1000,
            "events": self.current_response["events"],
            "latency": {},
            "interrupted": triggered_by is not None,
            "interrupt_trigger_type": triggered_by,
            "partial_transcript": accumulated_transcript,
            "next_audio_sent": next_audio_sent,
        }

    async def _send_audio_chunks(self, audio_data: bytes, chunk_size: int = 4800, append_silence: bool = True):
        """Stream audio chunks (used to run concurrently with event draining during a VAD interrupt).

        append_silence: append silence padding so the server VAD detects speech_stopped.
        Subclasses can override vad_silence_padding_bytes to control padding length (Grok uses 144000=3s);
        subclasses can set vad_force_commit=True to explicitly commit as a fallback (Grok's server VAD does not respond to pure silence).
        """
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            await self.send_audio_chunk(chunk)
            await asyncio.sleep(0.05)
        if append_silence:
            silence_bytes = getattr(self, "vad_silence_padding_bytes", 48000)
            silence_padding = b'\x00' * silence_bytes
            for i in range(0, len(silence_padding), chunk_size):
                await self.send_audio_chunk(silence_padding[i:i + chunk_size])
                await asyncio.sleep(0.05)
            if getattr(self, "vad_force_commit", False):
                await self.commit_audio_buffer()

    async def send_audio_with_vad_interrupt(
        self,
        audio_data: bytes,
        interrupt_audio: bytes,
        chunk_size: int = 4800,
        speech_grace_s: float = 0.4,
        max_tool_rounds: int = 5,
    ) -> Dict[str, Any]:
        """Server-VAD interrupt path (replaces v3.0 keyword + response.cancel).

        Flow:
          1. Stream pre-interrupt audio + manual commit + create_response
          2. Wait for model to start speaking (response.audio.delta) and let it
             commit to its decision for `speech_grace_s` seconds
          3. Enable server_vad turn_detection
          4. Stream interrupt_audio + 1 s silence — server VAD detects speech
             and auto-truncates the in-flight assistant response
          5. After silence, server VAD triggers a new autonomous response;
             handle its tool calls / transcript / audio
          6. Disable server_vad; restore manual control

        Returns the same dict schema as send_audio_with_interrupt.
        """
        start_time = time.time()
        self.audio_buffer = []
        self.transcript_buffer = []
        self.current_response = {
            "llm_calls": [],
            "tool_executions": [],
            "audio_chunks": [],
            "transcript": "",
            "events": [],
        }

        # 1) send pre-interrupt audio + commit + create_response
        print(f"  Sending {len(audio_data)} bytes of pre-interrupt audio (VAD interrupt mode)...")
        for i in range(0, len(audio_data), chunk_size):
            chunk = audio_data[i:i + chunk_size]
            await self.send_audio_chunk(chunk)
            await asyncio.sleep(0.05)
        await asyncio.sleep(0.2)
        await self.commit_audio_buffer()
        await self.create_response()

        # 2) wait for model speech start, then a brief grace period
        speech_started = False
        speech_start_time = None
        pre_transcript = ""
        model_finished_early = False
        for _ in range(800):
            try:
                event = await asyncio.wait_for(self._receive_event(), timeout=15.0)
            except asyncio.TimeoutError:
                print(f"  Timeout waiting for model speech")
                break
            event_type = event["type"]
            self.current_response["events"].append(event)

            if event_type == "response.audio.delta":
                audio_b64 = event.get("delta", "")
                if audio_b64:
                    self.audio_buffer.append(base64.b64decode(audio_b64))
                if not speech_started:
                    speech_started = True
                    speech_start_time = time.time()
                    print(f"  Speech started — {speech_grace_s}s grace then enable VAD")
            elif event_type == "response.audio_transcript.delta":
                pre_transcript += event.get("delta", "")
            elif event_type == "response.done":
                model_finished_early = True
                print(f"  [warn] Model finished before VAD interrupt could fire")
                break

            if speech_started and (time.time() - speech_start_time) >= speech_grace_s:
                break

        # 3) enable server_vad
        print(f"  Enabling server_vad turn_detection...")
        await self._send_event({
            "type": "session.update",
            "session": {
                "turn_detection": {
                    "type": "server_vad",
                    "threshold": 0.5,
                    "prefix_padding_ms": 300,
                    "silence_duration_ms": 500,
                }
            }
        })
        # consume session.updated
        for _ in range(20):
            try:
                ev = await asyncio.wait_for(self._receive_event(), timeout=5.0)
            except asyncio.TimeoutError:
                break
            self.current_response["events"].append(ev)
            if ev["type"] == "session.updated":
                break

        # 4) stream interrupt audio + 1 s silence
        print(f"  Sending interrupt audio ({len(interrupt_audio)} bytes) — server VAD will auto-truncate model")
        for i in range(0, len(interrupt_audio), chunk_size):
            chunk = interrupt_audio[i:i + chunk_size]
            await self.send_audio_chunk(chunk)
            await asyncio.sleep(0.05)
        silence = b'\x00' * (24000 * 2)  # 1 s, 24 kHz 16-bit mono
        for i in range(0, len(silence), chunk_size):
            chunk = silence[i:i + chunk_size]
            await self.send_audio_chunk(chunk)
            await asyncio.sleep(0.05)

        # 5) consume events: cancel + new autonomous response (with tool rounds)
        accumulated_transcript = ""
        truncated = False
        vad_tool_round = 0
        max_vad_tool_rounds = max_tool_rounds

        while vad_tool_round <= max_vad_tool_rounds:
            per_round_calls = []
            per_round_done = False
            while not per_round_done:
                try:
                    event = await asyncio.wait_for(self._receive_event(), timeout=20.0)
                except asyncio.TimeoutError:
                    print(f"  [VAD] Timeout — no autonomous response")
                    per_round_done = True
                    break
                event_type = event["type"]
                self.current_response["events"].append(event)

                if event_type == "input_audio_buffer.speech_started":
                    print(f"  [VAD] User speech detected (server-side)")
                elif event_type == "input_audio_buffer.speech_stopped":
                    print(f"  [VAD] User speech ended")
                elif event_type == "response.created":
                    print(f"  [VAD] New autonomous response started (round {vad_tool_round + 1})")
                elif event_type == "response.audio.delta":
                    audio_b64 = event.get("delta", "")
                    if audio_b64:
                        self.audio_buffer.append(base64.b64decode(audio_b64))
                elif event_type == "response.audio_transcript.delta":
                    accumulated_transcript += event.get("delta", "")
                elif event_type == "response.output_item.done":
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        fc = {
                            "call_id": item.get("call_id"),
                            "name": item.get("name"),
                            "arguments": item.get("arguments", ""),
                        }
                        per_round_calls.append(fc)
                        print(f"  [VAD] Function call: {fc['name']}")
                elif event_type == "response.done":
                    status = event.get("response", {}).get("status")
                    print(f"  [VAD] Response done (status={status})")
                    if status == "cancelled":
                        truncated = True
                        # the cancelled response is the pre-interrupt one — wait for the next one
                        continue
                    per_round_done = True
                elif event_type == "error":
                    err = event.get("error", {})
                    code = err.get("code", err)
                    if "cancel" in str(code).lower():
                        print(f"  [VAD] Cancel race (ignored): {code}")
                    else:
                        print(f"  [VAD] Error: {err}")
                        per_round_done = True

            # execute any function calls and continue the dialogue
            if per_round_calls:
                vad_tool_round += 1
                for fc in per_round_calls:
                    try:
                        func_args = json.loads(fc["arguments"])
                    except Exception:
                        func_args = {}
                    print(f"  [VAD] Executing: {fc['name']}({func_args})")
                    if self.tool_executor:
                        result = self.tool_executor.execute_tool(fc["name"], func_args)
                        self.current_response["tool_executions"].append({
                            "tool_call_id": fc["call_id"],
                            "tool_name": fc["name"],
                            "arguments": func_args,
                            "result": result,
                            "latency_ms": result.get("latency_ms", 0),
                        })
                        await self._send_function_call_output(
                            fc["call_id"], result.get("output", "")
                        )
                # ask for next response
                await self.create_response()
                continue
            break

        # 6) disable server_vad
        print(f"  Disabling server_vad (restoring manual control)...")
        await self._send_event({
            "type": "session.update",
            "session": {"turn_detection": None}
        })
        try:
            for _ in range(20):
                ev = await asyncio.wait_for(self._receive_event(), timeout=2.0)
                self.current_response["events"].append(ev)
                if ev["type"] == "session.updated":
                    break
        except asyncio.TimeoutError:
            pass

        end_time = time.time()
        self.current_response["transcript"] = accumulated_transcript
        self.current_response["llm_calls"].append({
            "round": 1,
            "finish_reason": "vad_interrupted" if truncated else ("model_finished_early" if model_finished_early else "completed"),
            "content": accumulated_transcript,
            "tool_calls": None,
        })

        return {
            "assistant_response": accumulated_transcript,
            "llm_calls": self.current_response["llm_calls"],
            "tool_executions": self.current_response["tool_executions"],
            "audio_data": b"".join(self.audio_buffer),
            "total_latency_ms": (end_time - start_time) * 1000,
            "events": self.current_response["events"],
            "latency": {},
            "interrupted": truncated,
            "interrupt_trigger_type": "vad",
            "partial_transcript": pre_transcript,
        }

    async def send_text_and_wait_response(
        self,
        text: str,
        max_tool_rounds: int = 5,
        dangling_tool: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Send a text message and wait for the full response (for the text baseline).

        Logic is identical to send_audio_and_wait_response; only the input changes from
        audio to conversation.item.create + input_text.

        dangling_tool: if not None and a round's function_call matches this tool name,
        skip execution and result return, and immediately return a trace marked
        interrupted=True (text-mode equivalent of the tool-phase interrupt).
        """
        start_time = time.time()

        # Reset the response collector.
        self.audio_buffer = []
        self.transcript_buffer = []
        self.current_response = {
            "llm_calls": [],
            "tool_executions": [],
            "audio_chunks": [],
            "transcript": "",
            "events": []
        }

        # Latency timestamps.
        text_submit_ts = None
        first_speech_ts = None
        first_tool_call_ts = None

        # Send the text message (in place of audio).
        print(f"  Sending text: {text[:80]}...")
        await self.send_text_message(text, role="user")
        text_submit_ts = time.time() * 1000
        print(f"  Creating response...")
        await self.create_response(modalities=["text"])  # text baseline: force text-only

        # The tool-call loop below is identical to send_audio_and_wait_response.
        tool_round = 0
        while tool_round < max_tool_rounds:
            response_complete = False
            current_transcript = ""
            current_function_calls = []
            current_function_call = None

            while not response_complete:
                event = await self._receive_event()
                event_type = event["type"]
                self.current_response["events"].append(event)

                if event_type == "response.created":
                    print(f"  Response created (round {tool_round + 1})")

                elif event_type == "response.audio.delta":
                    if first_speech_ts is None:
                        first_speech_ts = time.time() * 1000
                    audio_base64 = event.get("delta", "")
                    if audio_base64:
                        audio_bytes = base64.b64decode(audio_base64)
                        self.audio_buffer.append(audio_bytes)
                        self.current_response["audio_chunks"].append(audio_bytes)

                elif event_type == "response.audio_transcript.delta":
                    delta = event.get("delta", "")
                    self.transcript_buffer.append(delta)
                    current_transcript += delta

                elif event_type == "response.audio_transcript.done":
                    current_transcript = event.get("transcript", "")
                    if current_transcript:
                        print(f"  Transcript: {current_transcript}")

                elif event_type == "response.text.delta":
                    delta = event.get("delta", "")
                    self.transcript_buffer.append(delta)
                    current_transcript += delta

                elif event_type == "response.text.done":
                    current_transcript = event.get("text", current_transcript)
                    if current_transcript:
                        print(f"  Transcript: {current_transcript}")

                elif event_type == "response.function_call_arguments.delta":
                    if not current_function_call:
                        current_function_call = {
                            "call_id": event.get("call_id"),
                            "name": event.get("name"),
                            "arguments": ""
                        }
                    current_function_call["arguments"] += event.get("delta", "")

                elif event_type == "response.function_call_arguments.done":
                    if current_function_call and current_function_call.get("name"):
                        print(f"  Function call complete: {current_function_call['name']}")
                    current_function_call = None

                elif event_type == "response.output_item.done":
                    item = event.get("item", {})
                    if item.get("type") == "function_call":
                        if first_tool_call_ts is None:
                            first_tool_call_ts = time.time() * 1000
                        fc = {
                            "call_id": item.get("call_id"),
                            "name": item.get("name"),
                            "arguments": item.get("arguments", "")
                        }
                        current_function_calls.append(fc)
                        print(f"  Function call from output_item: {fc['name']}")

                elif event_type == "response.done":
                    response_complete = True
                    response_data = event["response"]

                    status = response_data.get("status")
                    if status == "failed":
                        print(f"  [DEBUG] Response failed: {response_data.get('status_details', {})}")

                    llm_call = {
                        "round": tool_round + 1,
                        "finish_reason": response_data.get("status"),
                        "content": current_transcript,
                        "tool_calls": None
                    }

                    if current_function_calls:
                        print(f"  Detected {len(current_function_calls)} native function call(s)")
                        llm_call["tool_calls"] = []
                        dangling_hit = False

                        for fc in current_function_calls:
                            func_name = fc["name"]
                            try:
                                func_args = json.loads(fc["arguments"])
                            except:
                                func_args = {}

                            is_dangling = (dangling_tool is not None and func_name == dangling_tool)
                            tool_call_record = {
                                "id": fc["call_id"],
                                "name": func_name,
                                "arguments": func_args
                            }
                            if is_dangling:
                                tool_call_record["dangling"] = True
                                tool_call_record["dangling_return"] = "never"
                                llm_call["tool_calls"].append(tool_call_record)
                                print(f"    Dangling intercepted (not executed): {func_name}({func_args})")
                                dangling_hit = True
                                continue

                            print(f"    Executing: {func_name}({func_args})")
                            llm_call["tool_calls"].append(tool_call_record)

                            if self.tool_executor:
                                result = self.tool_executor.execute_tool(func_name, func_args)
                                self.current_response["tool_executions"].append({
                                    "tool_call_id": fc["call_id"],
                                    "tool_name": func_name,
                                    "arguments": func_args,
                                    "result": result,
                                    "latency_ms": result.get("latency_ms", 0)
                                })
                                await self._send_function_call_output(
                                    fc["call_id"],
                                    result.get("output", "")
                                )

                        self.current_response["llm_calls"].append(llm_call)

                        if dangling_hit:
                            # text-mode tool-phase interrupt: return immediately with interrupted flag
                            end_time = time.time()
                            self.current_response["transcript"] = current_transcript
                            return {
                                "assistant_response": current_transcript,
                                "llm_calls": self.current_response["llm_calls"],
                                "tool_executions": self.current_response["tool_executions"],
                                "audio_data": b"",
                                "total_latency_ms": (end_time - start_time) * 1000,
                                "events": self.current_response["events"],
                                "latency": {},
                                "interrupted": True,
                                "interrupt_trigger_type": "tool_phase",
                                "partial_transcript": current_transcript,
                            }

                        tool_round += 1

                        if tool_round < max_tool_rounds:
                            print(f"  Creating next response...")
                            await self.create_response(modalities=["text"])  # text baseline
                            break
                        else:
                            print(f"  Reached max tool rounds ({max_tool_rounds})")
                            tool_round = max_tool_rounds
                            break
                    else:
                        self.current_response["llm_calls"].append(llm_call)
                        self.current_response["transcript"] = current_transcript
                        tool_round = max_tool_rounds
                        break

                elif event_type == "error":
                    print(f"  Error: {event.get('error', {})}")
                    raise Exception(f"API Error: {event.get('error')}")

        end_time = time.time()

        latency = {}
        if text_submit_ts:
            if first_speech_ts:
                latency["speech_ms"] = first_speech_ts - text_submit_ts
            if first_tool_call_ts:
                latency["tool_call_ms"] = first_tool_call_ts - text_submit_ts

        result = {
            "assistant_response": self.current_response["transcript"],
            "llm_calls": self.current_response["llm_calls"],
            "tool_executions": self.current_response["tool_executions"],
            "audio_data": b"".join(self.audio_buffer),
            "total_latency_ms": (end_time - start_time) * 1000,
            "events": self.current_response["events"],
            "latency": latency
        }

        return result

    async def _send_function_call_output(self, call_id: str, output: str):
        """Send the function-call result."""
        event = {
            "type": "conversation.item.create",
            "item": {
                "type": "function_call_output",
                "call_id": call_id,
                "output": output
            }
        }
        await self._send_event(event)

    def reset(self):
        """Reset the conversation history."""
        self.conversation_history = []
        self.audio_buffer = []
        self.transcript_buffer = []

    def get_conversation_history(self) -> List[Dict[str, Any]]:
        """Return the full conversation history."""
        return self.conversation_history.copy()
