"""
音频任务运行器 - 支持多个 Realtime API 提供商
"""
import asyncio
import os
import time
from datetime import datetime
from typing import Optional, Literal
from pathlib import Path

from eval.data.task import Task, MessageRole
from eval.data.trace import Trace, TraceStep
from eval.audio.tts_cache import TTSCache
from eval.models.openai_realtime_client import OpenAIRealtimeClient
from eval.models.gemini_live_client import GeminiLiveClient
from eval.models.grok_realtime_client import GrokRealtimeClient
from eval.models.qwen_realtime_client import QwenRealtimeClient
from eval.models.doubao_realtime_client import DoubaoRealtimeClient
from eval.models.glm_realtime_client import GLMRealtimeClient
from eval.models.minimax_realtime_client import MiniMaxRealtimeClient
from eval.paths import trace_root as default_trace_root, audio_cache_root


class AudioTaskRunner:
    """音频任务运行器 - Crawl 阶段（合成音频 + 多轮）"""

    # 支持的提供商列表
    PROVIDERS = ["openai", "gemini", "grok", "qwen", "doubao", "glm", "minimax"]

    def __init__(
        self,
        api_key: str,
        provider: str = "openai",
        model: Optional[str] = None,
        voice: str = "alloy",
        tool_executor=None,
        output_dir: Optional[str] = None,
        audio_cache_dir: Optional[str] = None,
        realtime_mode: bool = False,
        time_scale: float = 1.0,
        region: str = "cn",  # 用于 qwen
        quiet: bool = False,  # 静默模式
        save_audio: bool = False,  # 保存模型音频输出
        input_mode: str = "audio",  # "audio" 或 "text"
        turn_detection_mode: str = "manual",  # "manual" / "server_vad" / "semantic_vad"（"vad" 别名 → "server_vad"）
        audio_variant: str = "default",
        tts_backend: str = "openai",
        clone_manifest: Optional[str] = None,
        clone_accent: Optional[str] = None,
        clone_policy: str = "task_hash",
        clone_model: str = "tts_models/multilingual/multi-dataset/xtts_v2",
    ):
        """
        初始化音频任务运行器

        Args:
            api_key: API key
            provider: API 提供商
            model: 模型名称（如果为 None 则使用默认值）
            voice: 语音类型
            tool_executor: 工具执行器
            output_dir: trace 输出目录
            realtime_mode: 是否启用实时模式
            time_scale: 时间缩放因子
            region: 区域（用于 qwen: cn/intl）
            quiet: 静默模式（减少输出）
            save_audio: 保存模型音频输出到文件
        """
        if provider not in self.PROVIDERS:
            raise ValueError(f"Unsupported provider: {provider}. Supported: {self.PROVIDERS}")
        # "vad" 是 "server_vad" 的别名（backward compat）
        if turn_detection_mode == "vad":
            turn_detection_mode = "server_vad"
        if turn_detection_mode not in ("manual", "server_vad", "semantic_vad"):
            raise ValueError(
                f"turn_detection_mode must be 'manual', 'server_vad', or 'semantic_vad', got {turn_detection_mode!r}"
            )

        self.api_key = api_key
        self.provider = provider
        self.tool_executor = tool_executor
        self.region = region
        self.output_dir = Path(output_dir) if output_dir else default_trace_root()
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.realtime_mode = realtime_mode
        self.time_scale = time_scale
        self.quiet = quiet
        self.save_audio = save_audio
        self.input_mode = input_mode
        self.turn_detection_mode = turn_detection_mode
        self.audio_variant = audio_variant
        self.tts_backend = tts_backend
        self.clone_manifest = clone_manifest
        if clone_accent is None or str(clone_accent).strip().lower() in ("", "any"):
            self.clone_accent = None
        else:
            self.clone_accent = clone_accent
        self.clone_policy = clone_policy
        self.clone_model = clone_model

        # 设置默认模型和语音
        default_models = {
            "openai": "gpt-realtime-mini",
            "gemini": "gemini-2.5-flash-native-audio-latest",
            "grok": "grok-3-fast",
            "qwen": "qwen3-omni-flash-realtime",
            "doubao": "doubao-1.5-realtime-voice-pro",
            "glm": "glm-realtime",
            "minimax": "speech-2.6",
        }
        self.model = model if model else default_models.get(provider, "default")

        # 各提供商使用不同的语音系统
        voice_defaults = {
            "openai": "alloy",
            "gemini": "Puck",
            "grok": "Ara",
            "qwen": "Ethan",  # Cherry 在 qwen3.5-omni-plus-realtime 不被支持（DashScope 拒绝）；Ethan 已验证 (2026-05-03)
            "doubao": "zh_female_wanwanxiaohe_moon_bigtts",
            "glm": "male",
            "minimax": "female-tianmei",
        }
        self.voice = voice if voice != "alloy" else voice_defaults.get(provider, "alloy")

        # 初始化 TTS 缓存管理器（统一使用 alloy 语音）
        self.tts_cache = TTSCache(
            cache_dir=str(Path(audio_cache_dir) if audio_cache_dir else audio_cache_root()),
            tts_model="tts-1",
            tts_voice="alloy",
            variant=audio_variant,
            tts_backend=tts_backend,
            clone_manifest=clone_manifest,
            clone_accent=self.clone_accent,
            clone_policy=clone_policy,
            clone_model=clone_model,
        )

        # Realtime 客户端（延迟初始化）
        self.realtime_client = None

    async def run_task(
        self,
        task: Task,
        task_path: str,
        system_prompt: Optional[str] = None
    ) -> Trace:
        """
        运行音频任务并生成 trace

        Args:
            task: 要运行的任务
            task_path: task JSON 文件路径（用于音频缓存）
            system_prompt: 系统提示（可选）

        Returns:
            完整的 Trace
        """
        # 读取 task JSON 获取 info_complete_turn
        import json
        with open(task_path, 'r') as f:
            task_data = json.load(f)
        info_complete_turn = task_data.get('info_complete_turn')

        if not self.quiet:
            print(f"\n{'='*60}")
            print(f"开始运行音频任务: {task.name}")
            print(f"描述: {task.description}")
            print(f"提供商: {self.provider.upper()}")
            print(f"模型: {self.model}")
            print(f"总共 {len(task.chunks)} 个步骤")
            print(f"模式: {'实时模拟' if self.realtime_mode else '快速执行'}")
            if info_complete_turn:
                print(f"Info Complete Turn: {info_complete_turn}")
            print(f"{'='*60}\n")

        # 创建 Realtime 客户端并连接
        if not self.quiet:
            print("[DEBUG] 创建 Realtime 客户端...")
        client_classes = {
            "openai": OpenAIRealtimeClient,
            "gemini": GeminiLiveClient,
            "grok": GrokRealtimeClient,
            "doubao": DoubaoRealtimeClient,
            "glm": GLMRealtimeClient,
            "minimax": MiniMaxRealtimeClient,
        }

        if self.provider == "qwen":
            # DashScope 仅支持 server_vad，semantic_vad 在 audio_runner_v2 入口已校验过别名
            if self.turn_detection_mode == "semantic_vad":
                raise NotImplementedError(
                    "Qwen DashScope realtime API 不支持 semantic_vad，请用 server_vad 或 manual"
                )
            self.realtime_client = QwenRealtimeClient(
                api_key=self.api_key,
                model=self.model,
                voice=self.voice,
                tool_executor=self.tool_executor,
                region=self.region,
                turn_detection_mode=self.turn_detection_mode,
            )
        elif self.provider in client_classes:
            ClientCls = client_classes[self.provider]
            if self.provider == "openai":
                # Allow project-level regional routing to override the default endpoint.
                # Some OpenAI projects require us.api.openai.com even for GA Realtime models.
                base_url = os.getenv("OPENAI_REALTIME_BASE_URL")
                if not base_url:
                    if self.model == "gpt-realtime-2" or "preview" in self.model:
                        base_url = "wss://api.openai.com/v1/realtime"
                    else:
                        base_url = "wss://us.api.openai.com/v1/realtime"
                self.realtime_client = ClientCls(
                    api_key=self.api_key,
                    model=self.model,
                    voice=self.voice,
                    tool_executor=self.tool_executor,
                    base_url=base_url,
                    turn_detection_mode=self.turn_detection_mode,
                )
            elif self.provider == "grok":
                # Grok 兼容 OpenAI 格式，同样支持 turn_detection_mode
                self.realtime_client = ClientCls(
                    api_key=self.api_key,
                    model=self.model,
                    voice=self.voice,
                    tool_executor=self.tool_executor,
                    turn_detection_mode=self.turn_detection_mode,
                )
            elif self.provider == "gemini":
                # Gemini Live API 支持 manual / server_vad / semantic_vad
                self.realtime_client = ClientCls(
                    api_key=self.api_key,
                    model=self.model,
                    voice=self.voice,
                    tool_executor=self.tool_executor,
                    turn_detection_mode=self.turn_detection_mode,
                )
            else:
                if self.turn_detection_mode != "manual":
                    raise NotImplementedError(
                        f"turn_detection_mode={self.turn_detection_mode!r} not yet supported for provider {self.provider}"
                    )
                self.realtime_client = ClientCls(
                    api_key=self.api_key,
                    model=self.model,
                    voice=self.voice,
                    tool_executor=self.tool_executor
                )
        else:
            raise ValueError(f"Unsupported provider: {self.provider}")

        try:
            if not self.quiet:
                print("[DEBUG] 连接到 Realtime API...")
            await self.realtime_client.connect()
            if not self.quiet:
                print("[DEBUG] 连接成功！")

            # 创建 trace
            trace = Trace(
                task_name=task.name,
                start_time=datetime.now().isoformat(),
                metadata={
                    **task.metadata,
                    "mode": "audio_crawl",
                    "provider": self.provider,
                    "tts_voice": self.voice,
                    "realtime_model": self.model,
                    "input_mode": self.input_mode,
                    "turn_detection_mode": self.turn_detection_mode,
                    "tts_backend": self.tts_backend,
                    "audio_variant": self.audio_variant,
                    "clone_filter_accent": self.clone_accent if self.tts_backend == "voice_cloning" else None,
                }
            )

            # 第一步：获取音频（text 模式跳过 TTS）
            if self.input_mode == "text":
                if not self.quiet:
                    print("\n[阶段 1] 准备文本输入（跳过 TTS）...")
                # 从 transcript 构建 text-only chunks
                audio_chunks = []
                for chunk in task.chunks:
                    if chunk.role == MessageRole.USER:
                        audio_chunks.append({
                            'audio': b'',
                            'text': chunk.content,
                            'timestamp': chunk.timestamp,
                            'metadata': chunk.metadata or {}
                        })
                if not self.quiet:
                    print(f"✓ 准备了 {len(audio_chunks)} 个文本块\n")
            else:
                if not self.quiet:
                    print("\n[阶段 1] 准备音频...")
                audio_chunks = self.tts_cache.get_or_generate(task_path, task)
                # cache 的 metadata 可能是旧 task JSON 时写入的（hash 只校验 transcript 文本，
                # 不校验 metadata 字段如 interrupt_trigger.dangling_return）。这里用 task JSON
                # 的最新 metadata 覆盖，确保 dangling_return / contains_params 等字段是最新的。
                user_turns = [t for t in task_data.get("transcript", []) if t.get("speaker") == "user"]
                for i, ch in enumerate(audio_chunks):
                    if i < len(user_turns):
                        ch['metadata'] = user_turns[i].get("metadata", {})
                if not self.quiet:
                    print(f"✓ 准备了 {len(audio_chunks)} 个音频块\n")

            # 注入 context_turns（proactive 任务的前置对话背景）
            context_turns = task_data.get("context_turns", [])
            if context_turns:
                if hasattr(self.realtime_client, 'send_text_message'):
                    if not self.quiet:
                        print(f"\n[阶段 1.5] 注入 context_turns ({len(context_turns)} 轮)...")
                    for turn in context_turns:
                        role = turn.get("role", "user")
                        content = turn.get("content", "")
                        await self.realtime_client.send_text_message(content, role=role)
                        if not self.quiet:
                            print(f"  {role}: {content[:50]}...")
                    if not self.quiet:
                        print(f"  context_turns 注入完成")
                else:
                    if not self.quiet:
                        print(f"\n[WARNING] {self.provider} 不支持 send_text_message，跳过 context_turns 注入")

            # 第二步：逐步发送音频并收集响应
            if not self.quiet:
                print("[阶段 2] 执行对话...")
            step_count = 0
            last_timestamp = 0.0

            # Latency 收集（只在 info_complete_turn 对应的步骤记录）
            task_latency = {}

            # VAD 打断专用：上一步如果触发了 VAD 打断，下一 turn 音频已经发送过
            audio_already_sent_for_next = False

            for chunk_idx, audio_chunk in enumerate(audio_chunks):
                step_count += 1

                # 实时模式：模拟真实时间流逝
                if self.realtime_mode and step_count > 1:
                    time_delay = (audio_chunk['timestamp'] - last_timestamp) * self.time_scale
                    if time_delay > 0:
                        if not self.quiet:
                            print(f"\n⏱️  等待 {time_delay:.1f} 秒（模拟语音输入间隔）...")
                        await asyncio.sleep(time_delay)

                last_timestamp = audio_chunk['timestamp']

                # 检查下一个 chunk 是否是 interruption
                next_chunk = audio_chunks[chunk_idx + 1] if chunk_idx + 1 < len(audio_chunks) else None
                next_is_interrupt = (
                    next_chunk is not None
                    and next_chunk.get('metadata', {}).get('is_interruption')
                )
                interrupt_trigger = (
                    next_chunk['metadata'].get('interrupt_trigger')
                    if next_is_interrupt else None
                )

                # 发送输入并等待响应
                if not self.quiet:
                    print(f"\n[步骤 {step_count} @ {audio_chunk['timestamp']:.1f}s]")
                    print(f"用户（文本）: {audio_chunk['text']}")
                    if next_is_interrupt:
                        print(f"⚡ 下一步是打断 (keyword={interrupt_trigger.get('keyword', '?')})")
                    if self.input_mode == "text":
                        print(f"输入模式: text")
                    else:
                        print(f"用户（音频）: {len(audio_chunk['audio'])} bytes")

                if next_is_interrupt and self.input_mode == "text":
                    # text-mode interrupt: 拦截 tool-phase dangling tool；speech-phase 自然按 turn 处理
                    dangling_tool = None
                    if interrupt_trigger and interrupt_trigger.get("type") == "tool_phase":
                        dangling_tool = interrupt_trigger.get("dangling_tool")
                    response = await self.realtime_client.send_text_and_wait_response(
                        text=audio_chunk['text'],
                        dangling_tool=dangling_tool,
                    )
                    # 未命中 dangling 时仍标记 interrupted（evaluator 看此 flag），trigger_type 透传
                    if not response.get("interrupted"):
                        response["interrupted"] = True
                        response["interrupt_trigger_type"] = (
                            interrupt_trigger.get("type") if interrupt_trigger else "unknown"
                        )
                        response["partial_transcript"] = response.get("assistant_response", "")
                elif next_is_interrupt and hasattr(self.realtime_client, 'send_audio_with_interrupt'):
                    # 打断模式：keyword (v3.0) 或 tool_phase (v3.1, 仅全局 VAD)
                    # interrupt_audio 始终传 next_chunk 音频；client 按 trigger_type + mode 处理
                    response = await self.realtime_client.send_audio_with_interrupt(
                        audio_data=audio_chunk['audio'],
                        interrupt_trigger=interrupt_trigger,
                        interrupt_audio=next_chunk['audio'],
                    )
                    # VAD 模式（含 vad_tool_phase 与 keyword）下一 turn 音频已由 client 发送
                    if response.get("next_audio_sent"):
                        audio_already_sent_for_next = True
                elif self.input_mode == "text":
                    response = await self.realtime_client.send_text_and_wait_response(
                        text=audio_chunk['text']
                    )
                elif audio_already_sent_for_next:
                    # VAD 打断后的下一轮：音频已发送，仅等响应
                    response = await self.realtime_client.send_audio_and_wait_response(
                        audio_data=audio_chunk['audio'],
                        audio_already_sent=True,
                    )
                    audio_already_sent_for_next = False
                else:
                    response = await self.realtime_client.send_audio_and_wait_response(
                        audio_data=audio_chunk['audio']
                    )

                # 记录这一步
                step_latency = response.get('latency', {}) or {}
                step_metadata = {
                    "usage": response.get("usage", {}),
                    "audio_output_size_bytes": len(response.get("audio_data", b"")),
                    "event_count": len(response.get("events", [])),
                }
                # speech_ms/tool_call_ms：commit/speech_stopped 后到首响应/首工具调用的延迟
                if step_latency:
                    step_metadata["latency"] = step_latency
                # 打断标记
                if response.get("interrupted"):
                    step_metadata["interrupted"] = True
                    step_metadata["interrupt_trigger_type"] = response.get("interrupt_trigger_type")
                    step_metadata["partial_transcript"] = response.get("partial_transcript", "")

                step = TraceStep(
                    step_id=step_count,
                    timestamp=audio_chunk['timestamp'],
                    input_chunk={
                        "role": "user",
                        "content": audio_chunk['text'],
                        "timestamp": audio_chunk['timestamp'],
                        "metadata": audio_chunk['metadata'],
                        "audio_size_bytes": len(audio_chunk['audio'])
                    },
                    assistant_response=response.get("assistant_response"),
                    llm_calls=response.get("llm_calls", []),
                    tool_executions=response.get("tool_executions", []),
                    total_latency_ms=response.get("total_latency_ms"),
                    metadata=step_metadata,
                )

                if not self.quiet:
                    print(f"助手（转录）: {response.get('assistant_response', 'N/A')}")
                    print(f"助手（音频）: {len(response.get('audio_data', b''))} bytes")
                    print(f"工具调用: {len(response.get('tool_executions', []))} 个")
                    print(f"延迟: {response.get('total_latency_ms', 0):.1f}ms")

                # 保存完整对话音频（如果启用）
                if self.save_audio:
                    audio_dir = self.output_dir / "conversation_audio" / task.name
                    audio_dir.mkdir(parents=True, exist_ok=True)

                    # 保存用户音频（输入）
                    user_audio_file = audio_dir / f"step_{step_count:02d}_user.wav"
                    import wave
                    with wave.open(str(user_audio_file), 'wb') as wf:
                        wf.setnchannels(1)  # mono
                        wf.setsampwidth(2)  # 16-bit
                        wf.setframerate(24000)  # 24kHz
                        wf.writeframes(audio_chunk['audio'])

                    # 保存模型音频（输出）
                    if response.get('audio_data'):
                        assistant_audio_file = audio_dir / f"step_{step_count:02d}_assistant.wav"
                        with wave.open(str(assistant_audio_file), 'wb') as wf:
                            wf.setnchannels(1)  # mono
                            wf.setsampwidth(2)  # 16-bit
                            wf.setframerate(24000)  # 24kHz
                            wf.writeframes(response.get('audio_data'))

                        if not self.quiet:
                            print(f"💾 对话音频已保存: {audio_dir}/step_{step_count:02d}_*.wav")

                # 记录 latency
                if step_latency and (step_latency.get('speech_ms') or step_latency.get('tool_call_ms')):
                    if not self.quiet:
                        speech_ms = step_latency.get('speech_ms')
                        tool_call_ms = step_latency.get('tool_call_ms')
                        speech_str = f"{speech_ms:.1f}" if speech_ms else "N/A"
                        tool_call_str = f"{tool_call_ms:.1f}" if tool_call_ms else "N/A"
                        print(f"Latency: speech={speech_str}ms, tool_call={tool_call_str}ms")

                # task 级别 latency：info_complete_turn 是 {tool_name: turn_number}（新 schema），
                # 在每个 tool 的 info_complete_turn 那一步保存对应 latency；
                # 兼容旧 int 格式（整个 task 一个 latency）。
                if info_complete_turn:
                    if isinstance(info_complete_turn, dict):
                        for tool_name, target_turn in info_complete_turn.items():
                            if step_count == target_turn and step_latency:
                                task_latency[tool_name] = step_latency
                                if not self.quiet:
                                    print(f"📊 Info complete for {tool_name} at turn {step_count}")
                    elif step_count == info_complete_turn:
                        task_latency = step_latency
                        if not self.quiet:
                            print(f"📊 Info complete at turn {step_count}, latency recorded")

                trace.add_step(step)

            # 完成 trace
            trace.conversation_history = self.realtime_client.get_conversation_history()
            trace.finalize()

            # 添加 latency 到 trace metadata
            if task_latency:
                trace.metadata['latency'] = task_latency
                trace.metadata['info_complete_turn'] = info_complete_turn

            if not self.quiet:
                print(f"\n{'='*60}")
                print(f"任务执行完成！")
                print(f"总步骤: {trace.summary['total_steps']}")
                print(f"LLM 调用: {trace.summary['total_llm_calls']}")
                print(f"工具调用: {trace.summary['total_tool_calls']}")
                if task_latency:
                    # task_latency 可能是 dict[tool]→latency（新格式）或 直接 latency 字典（旧格式）
                    if isinstance(info_complete_turn, dict):
                        for tool_name, lat in task_latency.items():
                            speech_ms = lat.get('speech_ms')
                            tool_call_ms = lat.get('tool_call_ms')
                            speech_str = f"{speech_ms:.1f}" if speech_ms else "N/A"
                            tool_call_str = f"{tool_call_ms:.1f}" if tool_call_ms else "N/A"
                            print(f"Latency [{tool_name}]: speech={speech_str}ms, tool_call={tool_call_str}ms")
                    else:
                        speech_ms = task_latency.get('speech_ms')
                        tool_call_ms = task_latency.get('tool_call_ms')
                        speech_str = f"{speech_ms:.1f}" if speech_ms else "N/A"
                        tool_call_str = f"{tool_call_ms:.1f}" if tool_call_ms else "N/A"
                        print(f"Latency: speech={speech_str}ms, tool_call={tool_call_str}ms")
                print(f"{'='*60}\n")

            return trace

        finally:
            # 断开连接
            if self.realtime_client:
                await self.realtime_client.disconnect()

    def run_task_sync(
        self,
        task: Task,
        task_path: str,
        system_prompt: Optional[str] = None
    ) -> Trace:
        """
        同步版本的 run_task（用于兼容现有代码）

        Args:
            task: 要运行的任务
            task_path: task JSON 文件路径
            system_prompt: 系统提示

        Returns:
            完整的 Trace
        """
        if not self.quiet:
            print("[DEBUG audio_runner] run_task_sync called")
        result = asyncio.run(self.run_task(task, task_path, system_prompt))
        if not self.quiet:
            print("[DEBUG audio_runner] run_task_sync completed")
        return result
