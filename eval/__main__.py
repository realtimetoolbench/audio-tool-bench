"""
CLI 入口
"""
import os
import sys
from pathlib import Path
import typer
from typing import Optional
from eval.paths import trace_root as default_trace_root, audio_cache_root

# 自动从项目根目录的 .env 加载所有 API key（OPENAI / DASHSCOPE / XAI / 等）
# 这样 generate / batch 命令不再依赖外层 wrapper 手动 export
try:
    from dotenv import load_dotenv
    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path, override=False)
except ImportError:
    pass  # python-dotenv 未装时退化到只读已有环境变量

from eval.tools import (
    ToolExecutor, WebSearchTool, FetchURLTool, ExtractInfoTool,
    # Travel Booking
    RestaurantSearchTool, MakeReservationTool,
    FlightSearchTool, BookFlightTool,
    HotelSearchTool, BookHotelTool,
    CarRentalTool, BookCarTool,
    TrainSearchTool, BookTrainTool,
    AttractionSearchTool, BookAttractionTicketTool,
    # Healthcare
    DoctorSearchTool, BookAppointmentTool, MedicineSearchTool,
    # Financial
    TransferMoneyTool, CheckBalanceTool, GetTransactionHistoryTool,
    ListBillsTool, PayBillTool,
    # Education
    CourseSearchTool, EnrollCourseTool,
    BookSearchTool, ReserveBookTool, RenewBookTool,
    # Transportation
    RequestRideTool, CheckRideStatusTool, CancelRideTool,
    SearchParkingTool, ReserveParkingSpotTool,
    # Entertainment
    MovieSearchTool, BookMovieTicketTool,
    ShowSearchTool, BookShowTicketTool,
    SportsEventSearchTool, BookSportsTicketTool,
    # Life Services
    DeliveryRestaurantSearchTool, PlaceFoodOrderTool,
    TrackPackageTool,
    HomeServiceSearchTool, BookCleaningServiceTool,
    # Expanded domains
    ProductSearchTool, ProductDetailsTool, PlaceRetailOrderTool,
    TrackRetailOrderTool, CheckReturnPolicyTool,
    CheckCalendarTool, CreateEventTool, ContactSearchTool,
    DraftMessageTool, SendMessageTool,
    RentalListingSearchTool, RentalListingDetailsTool, BookViewingTool,
    RentalAgentSearchTool, DraftAgentMessageTool,
    JobSearchTool, JobDetailsTool, SaveJobTool,
    DraftApplicationTool, TrackApplicationStatusTool,
    ServiceCenterSearchTool, BookServiceAppointmentTool,
    CheckCivicApplicationStatusTool, RequiredDocumentsTool,
    CheckMobilePlanTool, PhonePlanSearchTool, ChangePhonePlanTool,
    CheckDataUsageTool, PayPhoneBillTool,
    CreateReminderTool, ListRemindersTool, CreateNoteTool, SearchNotesTool
)
from openai import OpenAI

# 工具名称到类的映射，支持跨领域场景动态注册
TOOL_MAP = {
    # Travel Booking
    "search_restaurants": RestaurantSearchTool,
    "make_reservation": MakeReservationTool,
    "book_restaurant": MakeReservationTool,  # alias
    "search_flights": FlightSearchTool,
    "book_flight": BookFlightTool,
    "search_hotels": HotelSearchTool,
    "book_hotel": BookHotelTool,
    "search_car_rentals": CarRentalTool,
    "search_cars": CarRentalTool,  # alias
    "book_car": BookCarTool,
    "search_trains": TrainSearchTool,
    "book_train": BookTrainTool,
    "search_attractions": AttractionSearchTool,
    "book_attraction_ticket": BookAttractionTicketTool,
    # Healthcare
    "search_doctors": DoctorSearchTool,
    "book_appointment": BookAppointmentTool,
    "search_medicine": MedicineSearchTool,
    # Financial
    "transfer_money": TransferMoneyTool,
    "check_balance": CheckBalanceTool,
    "get_transaction_history": GetTransactionHistoryTool,
    "list_bills": ListBillsTool,
    "pay_bill": PayBillTool,
    # Education
    "search_courses": CourseSearchTool,
    "enroll_course": EnrollCourseTool,
    "search_books": BookSearchTool,
    "reserve_book": ReserveBookTool,
    "renew_book": RenewBookTool,
    # Transportation
    "request_ride": RequestRideTool,
    "check_ride_status": CheckRideStatusTool,
    "cancel_ride": CancelRideTool,
    "search_parking": SearchParkingTool,
    "reserve_parking": ReserveParkingSpotTool,
    "reserve_parking_spot": ReserveParkingSpotTool,
    # Entertainment
    "search_movies": MovieSearchTool,
    "book_movie_ticket": BookMovieTicketTool,
    "search_shows": ShowSearchTool,
    "book_show_ticket": BookShowTicketTool,
    "search_sports_events": SportsEventSearchTool,
    "book_sports_ticket": BookSportsTicketTool,
    # Life Services
    "search_restaurants_delivery": DeliveryRestaurantSearchTool,
    "place_food_order": PlaceFoodOrderTool,
    "track_package": TrackPackageTool,
    "search_home_services": HomeServiceSearchTool,
    "book_cleaning_service": BookCleaningServiceTool,
    "book_home_service": BookCleaningServiceTool,  # alias
    # Shopping / Retail
    "search_products": ProductSearchTool,
    "get_product_details": ProductDetailsTool,
    "place_order": PlaceRetailOrderTool,
    "track_order": TrackRetailOrderTool,
    "check_return_policy": CheckReturnPolicyTool,
    # Calendar / Communication
    "check_calendar": CheckCalendarTool,
    "create_event": CreateEventTool,
    "search_contacts": ContactSearchTool,
    "draft_message": DraftMessageTool,
    "send_message": SendMessageTool,
    # Housing Rental
    "search_rental_listings": RentalListingSearchTool,
    "get_listing_details": RentalListingDetailsTool,
    "book_viewing": BookViewingTool,
    "search_agents": RentalAgentSearchTool,
    "draft_agent_message": DraftAgentMessageTool,
    # Jobs / Career
    "search_jobs": JobSearchTool,
    "get_job_details": JobDetailsTool,
    "save_job": SaveJobTool,
    "draft_application": DraftApplicationTool,
    "track_application_status": TrackApplicationStatusTool,
    # Civic Services
    "search_service_centers": ServiceCenterSearchTool,
    "book_service_appointment": BookServiceAppointmentTool,
    "check_application_status": CheckCivicApplicationStatusTool,
    "get_required_documents": RequiredDocumentsTool,
    # Telecom Services
    "check_mobile_plan": CheckMobilePlanTool,
    "search_phone_plans": PhonePlanSearchTool,
    "change_phone_plan": ChangePhonePlanTool,
    "check_data_usage": CheckDataUsageTool,
    "pay_phone_bill": PayPhoneBillTool,
    # Personal Productivity
    "create_reminder": CreateReminderTool,
    "list_reminders": ListRemindersTool,
    "create_note": CreateNoteTool,
    "search_notes": SearchNotesTool,
}

def _register_all_tools(tool_executor: ToolExecutor):
    """注册 TOOL_MAP 中所有工具（去重 alias），用于 --all-tools 模式"""
    registered = set(tool_executor.tools.keys())
    for name, cls in TOOL_MAP.items():
        if name not in registered:
            tool_executor.register_tool(cls())
            registered.add(name)


app = typer.Typer(
    help="Audio Tool Bench - Agent Evaluation Framework",
    no_args_is_help=True
)


@app.command()
def generate(
    task: str = typer.Argument(..., help="任务文件路径（如 data/tasks/example_search.json）"),
    model: str = typer.Option("gpt-4o", help="使用的模型"),
    output: Optional[str] = typer.Option(None, help="输出文件名（可选）"),
    system_prompt: Optional[str] = typer.Option(None, help="系统提示（可选）"),
    realtime: bool = typer.Option(False, "--realtime", "-r", help="启用实时模式（模拟真实时间流逝）"),
    time_scale: float = typer.Option(1.0, "--time-scale", "-t", help="时间缩放因子（1.0=真实速度，0.5=2倍速）"),
    provider: str = typer.Option("openai", "--provider", "-p", help="API 提供商（openai, gemini, grok, qwen, doubao, glm, minimax）"),
    voice: str = typer.Option("alloy", help="语音类型"),
    region: str = typer.Option("cn", "--region", help="区域（用于 qwen: cn/intl）"),
    run_id: Optional[str] = typer.Option(None, "--run-id", help="运行 ID（用于批量测试时将 traces 放入同一目录）"),
    save_audio: bool = typer.Option(False, "--save-audio", help="保存模型音频输出到文件"),
    input_mode: str = typer.Option("audio", "--input-mode", help="输入模式: audio（TTS音频）或 text（纯文本）"),
    all_tools: bool = typer.Option(False, "--all-tools", help="注册所有工具（含干扰工具），提高 Tool F1 区分度"),
    turn_detection: str = typer.Option("manual", "--turn-detection", help="对话轮次控制: manual / server_vad（音频静音）/ semantic_vad（语义判断, eagerness=low）"),
    trace_root: Optional[str] = typer.Option(None, "--trace-root", help="trace 输出根目录（默认项目级 outputs/traces）"),
    audio_cache_dir: Optional[str] = typer.Option(None, "--audio-cache-dir", help="TTS 缓存目录（默认项目级 outputs/audio）"),
    audio_variant: str = typer.Option("default", "--audio-variant", help="audio 变体: default / no_prosody / noisy"),
    tts_backend: str = typer.Option("openai", "--tts-backend", help="TTS backend: openai / voice_cloning"),
    clone_manifest: Optional[str] = typer.Option(None, "--clone-manifest", help="CommonVoice clone manifest path"),
    clone_accent: Optional[str] = typer.Option(None, "--clone-accent", help="Optional CommonVoice accent filter for ablation"),
    clone_policy: str = typer.Option("task_hash", "--clone-policy", help="Voice clone speaker policy"),
    clone_model: str = typer.Option("tts_models/multilingual/multi-dataset/xtts_v2", "--clone-model", help="Local Coqui TTS voice-cloning model"),
    doc_mode: str = typer.Option("default", "--doc-mode", help="工具 schema 详度: default / minimal / verbose"),
):
    """
    生成 trace：运行场景并记录 agent 行为

    使用 Realtime API 进行端到端语音对话评测。

    支持的提供商：openai, gemini, grok, qwen, doubao, glm, minimax

    实时模式说明：
    - 默认：立即执行所有步骤（快速测试）
    - --realtime：按照 timestamp 模拟真实时间流逝

    输入模式：
    - audio：TTS 生成音频后发送（默认，测试完整语音流）
    - text：直接发送文本（跳过 TTS/ASR，用于 text baseline 对比）
    """
    # 检查 API key
    api_key_env_map = {
        "openai": "OPENAI_API_KEY",
        "openai-chat": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "grok": "XAI_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "doubao": "VOLCENGINE_API_KEY",
        "glm": "ZHIPU_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }

    if provider not in api_key_env_map:
        typer.echo(f"错误: 不支持的提供商: {provider}（支持: {', '.join(api_key_env_map.keys())}）", err=True)
        raise typer.Exit(1)

    env_var = api_key_env_map[provider]
    api_key = os.getenv(env_var)
    if not api_key:
        typer.echo(f"错误: 请设置 {env_var} 环境变量", err=True)
        raise typer.Exit(1)

    # 检查任务文件
    if not Path(task).exists():
        typer.echo(f"错误: 任务文件不存在: {task}", err=True)
        raise typer.Exit(1)

    typer.echo(f"🚀 开始生成 trace...")
    typer.echo(f"任务: {task}")
    typer.echo(f"提供商: {provider.upper()}")
    typer.echo(f"模型: {model}")
    typer.echo(f"语音: {voice}")
    if realtime:
        typer.echo(f"⏱️  实时模式: 启用（时间缩放: {time_scale}x）")
    if input_mode == "text":
        typer.echo(f"📝 输入模式: text（跳过 TTS/ASR）")
    typer.echo("")

    # 创建工具执行器
    typer.echo("[DEBUG] 创建工具执行器...")

    # 读取任务 JSON
    try:
        import json as _json
        with open(task, encoding='utf-8') as _f:
            _data = _json.load(_f)
    except Exception:
        _data = {}

    # Multi-step 任务：使用 Failing_Tools adapter
    _scenario_type = _data.get("scenario_type", "")
    if _scenario_type == "multi_step" and _data.get("server"):
        from eval.tools.failing_tools.adapter import create_executor_for_server
        _task_tools = _data.get("tools", [])
        _, tool_executor = create_executor_for_server(
            _data["server"], tool_names=_task_tools or None
        )
        tool_executor.doc_mode = doc_mode
        typer.echo(f"[DEBUG] Multi-step: 已注册 {len(tool_executor.tools)} 个 Failing_Tools 工具")
        category = None
        task_tools = _task_tools
        tools_registered_from_json = True
    else:
        tool_executor = ToolExecutor(doc_mode=doc_mode)

        # 检测任务类别（从文件路径中提取，或从 JSON 的 tool_category 字段读取）
        task_path = Path(task)
        category = None
        for part in task_path.parts:
            if part in ['healthcare', 'financial', 'education', 'transportation',
                        'travel_booking', 'entertainment', 'life_services',
                        'shopping_retail', 'calendar_communication',
                        'housing_rental', 'jobs_career', 'civic_services',
                        'telecom_services', 'personal_productivity']:
                category = part
                break

        category = category or _data.get('tool_category')
        task_tools = _data.get('tools', [])

        typer.echo(f"[DEBUG] 检测到任务类别: {category}")
        typer.echo(f"[DEBUG] 任务指定工具: {task_tools}")

        # 根据任务类别注册相应的工具
        typer.echo("[DEBUG] 注册任务特定工具...")

        # 优先使用 task JSON 中的 tools 字段（支持跨领域任务）
        tools_registered_from_json = False
        if task_tools:
            for tool_name in task_tools:
                if tool_name in TOOL_MAP:
                    tool_executor.register_tool(TOOL_MAP[tool_name]())
                    tools_registered_from_json = True
                else:
                    typer.echo(f"[WARNING] 未知工具: {tool_name}")

    # 如果从 JSON 注册了工具，跳过基于类别的注册
    if tools_registered_from_json:
        typer.echo(f"[DEBUG] 已注册 {len(tool_executor.tools)} 个工具")
    elif category == 'healthcare':
        # 医疗健康类工具
        tool_executor.register_tool(DoctorSearchTool())
        tool_executor.register_tool(BookAppointmentTool())
        tool_executor.register_tool(MedicineSearchTool())
    elif category == 'financial':
        # 金融服务类工具
        tool_executor.register_tool(TransferMoneyTool())
        tool_executor.register_tool(CheckBalanceTool())
        tool_executor.register_tool(GetTransactionHistoryTool())
        tool_executor.register_tool(ListBillsTool())
        tool_executor.register_tool(PayBillTool())

    elif category == 'education':
        # 教育学习类工具
        tool_executor.register_tool(CourseSearchTool())
        tool_executor.register_tool(EnrollCourseTool())
        tool_executor.register_tool(BookSearchTool())
        tool_executor.register_tool(ReserveBookTool())
        tool_executor.register_tool(RenewBookTool())

    elif category == 'transportation':
        # 出行服务类工具
        tool_executor.register_tool(RequestRideTool())
        tool_executor.register_tool(CheckRideStatusTool())
        tool_executor.register_tool(CancelRideTool())
        tool_executor.register_tool(SearchParkingTool())
        tool_executor.register_tool(ReserveParkingSpotTool())

    elif category == 'travel_booking':
        # 旅行预订类工具
        tool_executor.register_tool(RestaurantSearchTool())
        tool_executor.register_tool(MakeReservationTool())
        tool_executor.register_tool(FlightSearchTool())
        tool_executor.register_tool(BookFlightTool())
        tool_executor.register_tool(HotelSearchTool())
        tool_executor.register_tool(BookHotelTool())
        tool_executor.register_tool(CarRentalTool())
        tool_executor.register_tool(BookCarTool())
        tool_executor.register_tool(TrainSearchTool())
        tool_executor.register_tool(BookTrainTool())
        tool_executor.register_tool(AttractionSearchTool())
        tool_executor.register_tool(BookAttractionTicketTool())

    elif category == 'entertainment':
        # 娱乐活动类工具
        tool_executor.register_tool(MovieSearchTool())
        tool_executor.register_tool(BookMovieTicketTool())
        tool_executor.register_tool(ShowSearchTool())
        tool_executor.register_tool(BookShowTicketTool())
        tool_executor.register_tool(SportsEventSearchTool())
        tool_executor.register_tool(BookSportsTicketTool())

    elif category == 'life_services':
        # 生活服务类工具
        tool_executor.register_tool(DeliveryRestaurantSearchTool())
        tool_executor.register_tool(PlaceFoodOrderTool())
        tool_executor.register_tool(TrackPackageTool())
        tool_executor.register_tool(HomeServiceSearchTool())
        tool_executor.register_tool(BookCleaningServiceTool())

    elif category == 'shopping_retail':
        tool_executor.register_tool(ProductSearchTool())
        tool_executor.register_tool(ProductDetailsTool())
        tool_executor.register_tool(PlaceRetailOrderTool())
        tool_executor.register_tool(TrackRetailOrderTool())
        tool_executor.register_tool(CheckReturnPolicyTool())

    elif category == 'calendar_communication':
        tool_executor.register_tool(CheckCalendarTool())
        tool_executor.register_tool(CreateEventTool())
        tool_executor.register_tool(ContactSearchTool())
        tool_executor.register_tool(DraftMessageTool())
        tool_executor.register_tool(SendMessageTool())

    elif category == 'housing_rental':
        tool_executor.register_tool(RentalListingSearchTool())
        tool_executor.register_tool(RentalListingDetailsTool())
        tool_executor.register_tool(BookViewingTool())
        tool_executor.register_tool(RentalAgentSearchTool())
        tool_executor.register_tool(DraftAgentMessageTool())

    elif category == 'jobs_career':
        tool_executor.register_tool(JobSearchTool())
        tool_executor.register_tool(JobDetailsTool())
        tool_executor.register_tool(SaveJobTool())
        tool_executor.register_tool(DraftApplicationTool())
        tool_executor.register_tool(TrackApplicationStatusTool())

    elif category == 'civic_services':
        tool_executor.register_tool(ServiceCenterSearchTool())
        tool_executor.register_tool(BookServiceAppointmentTool())
        tool_executor.register_tool(CheckCivicApplicationStatusTool())
        tool_executor.register_tool(RequiredDocumentsTool())

    elif category == 'telecom_services':
        tool_executor.register_tool(CheckMobilePlanTool())
        tool_executor.register_tool(PhonePlanSearchTool())
        tool_executor.register_tool(ChangePhonePlanTool())
        tool_executor.register_tool(CheckDataUsageTool())
        tool_executor.register_tool(PayPhoneBillTool())

    elif category == 'personal_productivity':
        tool_executor.register_tool(CreateReminderTool())
        tool_executor.register_tool(ListRemindersTool())
        tool_executor.register_tool(CreateNoteTool())
        tool_executor.register_tool(SearchNotesTool())

    elif category == 'multi':
        # 多领域场景：娱乐 + 餐饮
        # Entertainment tools
        tool_executor.register_tool(MovieSearchTool())
        tool_executor.register_tool(BookMovieTicketTool())
        tool_executor.register_tool(ShowSearchTool())
        tool_executor.register_tool(BookShowTicketTool())
        tool_executor.register_tool(SportsEventSearchTool())
        tool_executor.register_tool(BookSportsTicketTool())
        # Restaurant tools
        tool_executor.register_tool(RestaurantSearchTool())
        tool_executor.register_tool(MakeReservationTool())

    else:
        # 未识别类别，注册通用工具
        typer.echo("[WARNING] 未识别任务类别，注册通用工具")
        tool_executor.register_tool(WebSearchTool())
        tool_executor.register_tool(FetchURLTool())

    # --all-tools: 注册所有剩余工具作为干扰项
    if all_tools:
        _register_all_tools(tool_executor)
        typer.echo(f"[DEBUG] --all-tools: 已注册 {len(tool_executor.tools)} 个工具（含干扰工具）")
    else:
        typer.echo(f"[DEBUG] 已注册 {len(tool_executor.tools)} 个工具")

    # ExtractInfoTool belongs to the web-search tool family; do not expose it
    # to business-domain benchmarks because it adds an unrelated failing action.
    if provider in ("openai", "openai-chat") and any(
        name in tool_executor.tools for name in ("web_search", "fetch_url")
    ):
        llm_client = OpenAI(api_key=api_key)
        tool_executor.register_tool(ExtractInfoTool(llm_client))

    # 默认系统提示
    if system_prompt is None:
        system_prompt = """你是一个智能助手，可以帮助用户搜索和获取网页信息。

你有以下工具可用：
- web_search: 搜索网页
- fetch_url: 获取网页内容
- extract_info: 从文本中提取结构化信息

请根据用户的需求，合理使用这些工具来完成任务。
"""

    # 注入当前日期（参考 BFCL 做法，动态注入以支持相对时间解析）
    import datetime
    _today = datetime.date.today()
    _weekday_cn = ["周一", "周二", "周三", "周四", "周五", "周六", "周日"][_today.weekday()]
    _date_context = f"今天是 {_today.strftime('%Y年%m月%d日')}（{_weekday_cn}）。\n\n"
    system_prompt = _date_context + system_prompt

    # 生成并保存 trace
    try:
        from eval.audio.audio_runner_v2 import AudioTaskRunner
        import json

        # 加载任务
        typer.echo("[DEBUG] 加载任务...")
        with open(task, 'r', encoding='utf-8') as f:
            task_data = json.load(f)
        from eval.data.task import Task
        task_obj = Task.from_dict(task_data)
        typer.echo(f"[DEBUG] 任务加载完成: {task_obj.name}")

        # 根据 provider 选择 runner
        if provider == "openai-chat":
            # Chat Completions API baseline（纯文本 chat 模型，如 gpt-5.4-mini）
            typer.echo("[DEBUG] 创建 Chat Completions runner...")
            from eval.models.chat_completions_runner import ChatCompletionsRunner
            runner = ChatCompletionsRunner(
                api_key=api_key, model=model,
                tool_executor=tool_executor,
            )
            typer.echo("[DEBUG] 开始运行任务...")
            trace = runner.run_task(task_obj, task, system_prompt=system_prompt)
        else:
            # Realtime API（音频/文本模式）
            typer.echo("[DEBUG] 创建音频运行器...")
            runner = AudioTaskRunner(
                api_key=api_key,
                provider=provider,
                model=model if model != "gpt-4o" else None,  # 使用默认模型
                voice=voice,
                tool_executor=tool_executor,
                output_dir=str(Path(trace_root).expanduser()) if trace_root else str(default_trace_root()),
                audio_cache_dir=audio_cache_dir,
                realtime_mode=realtime,
                time_scale=time_scale,
                region=region,
                save_audio=save_audio,
                input_mode=input_mode,
                turn_detection_mode=turn_detection,
                audio_variant=audio_variant,
                tts_backend=tts_backend,
                clone_manifest=clone_manifest,
                clone_accent=clone_accent,
                clone_policy=clone_policy,
                clone_model=clone_model,
            )
            typer.echo("[DEBUG] 音频运行器创建完成")
            typer.echo("[DEBUG] 开始运行任务...")
            trace = runner.run_task_sync(task_obj, task, system_prompt)

        # 保存 trace
        from datetime import datetime

        # 确定输出目录
        trace_root_path = Path(trace_root).expanduser() if trace_root else default_trace_root()
        if run_id:
            # 使用指定的 run_id（可以是路径如 openai_gpt-realtime-mini/reactive）
            run_dir = trace_root_path / run_id
        else:
            # 自动: <trace_root>/{provider}_{model}/single/
            actual_model = runner.model.replace("/", "-")
            run_dir = trace_root_path / f"{provider}_{actual_model}" / "single"

        run_dir.mkdir(parents=True, exist_ok=True)

        # 确定输出文件名
        if output is None:
            output = f"{task_obj.name}.json"

        output_path = run_dir / output
        trace.save_to_file(str(output_path))
        trace_path = str(output_path)

        typer.echo(f"\n✅ 完成！Trace 保存在: {trace_path}")
    except Exception as e:
        typer.echo(f"\n❌ 错误: {str(e)}", err=True)
        import traceback
        traceback.print_exc()
        raise typer.Exit(1)


@app.command()
def list_tasks():
    """
    列出所有可用的任务
    """
    tasks_dir = Path("data")
    if not tasks_dir.exists():
        typer.echo("没有找到任务目录")
        return

    tasks = [f for f in tasks_dir.glob("**/*.json")
             if "traces" not in f.parts and "possible_answer" not in f.parts]
    if not tasks:
        typer.echo("没有找到任务文件")
        return

    typer.echo("可用的任务:\n")
    for t in sorted(tasks):
        typer.echo(f"  - {t}")


@app.command()
def list_traces():
    """
    列出所有生成的 trace
    """
    traces_dir = default_trace_root()
    if not traces_dir.exists():
        typer.echo("没有找到 trace 目录")
        return

    traces = list(traces_dir.glob("**/*.json"))
    if not traces:
        typer.echo("没有找到 trace 文件")
        return

    typer.echo("生成的 trace:\n")
    for trace in sorted(traces, reverse=True):
        typer.echo(f"  - {trace}")


@app.command()
def batch(
    provider: str = typer.Option("openai", "--provider", "-p", help="API 提供商"),
    model: str = typer.Option("gpt-realtime-mini", "--model", "-m", help="使用的模型"),
    voice: str = typer.Option("alloy", help="语音类型"),
    region: str = typer.Option("cn", "--region", help="区域（用于 qwen: cn/intl）"),
    tasks_dir: str = typer.Option("data/tasks/seeds", "--tasks", "-s", help="任务目录"),
    delay: float = typer.Option(2.0, "--delay", "-d", help="每个任务之间的延迟（秒）"),
    input_mode: str = typer.Option("audio", "--input-mode", help="输入模式: audio 或 text"),
    task_set_name: str = typer.Option("", "--task-set-name", help="task set 名称（如 reactive/strong/medium/weak）"),
    all_tools: bool = typer.Option(False, "--all-tools", help="注册所有工具（含干扰工具）"),
    skip_existing: bool = typer.Option(False, "--skip-existing", help="跳过 run_dir 里已存在同名 trace 的任务"),
    turn_detection: str = typer.Option("manual", "--turn-detection", help="对话轮次控制: manual / server_vad / semantic_vad"),
    trace_root: Optional[str] = typer.Option(None, "--trace-root", help="trace 输出根目录（默认项目级 outputs/traces）"),
    audio_cache_dir: Optional[str] = typer.Option(None, "--audio-cache-dir", help="TTS 缓存目录（默认项目级 outputs/audio）"),
    audio_variant: str = typer.Option("default", "--audio-variant", help="audio 变体: default / no_prosody / noisy"),
    tts_backend: str = typer.Option("openai", "--tts-backend", help="TTS backend: openai / voice_cloning"),
    clone_manifest: Optional[str] = typer.Option(None, "--clone-manifest", help="CommonVoice clone manifest path"),
    clone_accent: Optional[str] = typer.Option(None, "--clone-accent", help="Optional CommonVoice accent filter for ablation"),
    clone_policy: str = typer.Option("task_hash", "--clone-policy", help="Voice clone speaker policy"),
    clone_model: str = typer.Option("tts_models/multilingual/multi-dataset/xtts_v2", "--clone-model", help="Local Coqui TTS voice-cloning model"),
    doc_mode: str = typer.Option("default", "--doc-mode", help="工具 schema 详度: default / minimal / verbose"),
    exclude_tools: str = typer.Option("", "--exclude-tools", help="逗号分隔的工具名，含这些工具的任务整体跳过（如 gemini 跳过 priority_late_return）"),
):
    """
    批量运行所有任务，生成 traces 到同一目录

    示例:
        python -m eval batch --provider openai --model gpt-realtime-mini
        python -m eval batch --provider openai --model gpt-realtime-mini --all-tools
    """
    import json
    import time
    from datetime import datetime
    from eval.audio.audio_runner_v2 import AudioTaskRunner
    from eval.data.task import Task

    # 检查 API key
    api_key_env_map = {
        "openai": "OPENAI_API_KEY",
        "openai-chat": "OPENAI_API_KEY",
        "gemini": "GOOGLE_API_KEY",
        "gemini-chat": "GOOGLE_API_KEY",
        "grok": "XAI_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "doubao": "VOLCENGINE_API_KEY",
        "glm": "ZHIPU_API_KEY",
        "minimax": "MINIMAX_API_KEY",
    }

    if provider not in api_key_env_map:
        typer.echo(f"错误: 不支持的提供商: {provider}", err=True)
        raise typer.Exit(1)

    env_var = api_key_env_map[provider]
    api_key = os.getenv(env_var)
    if not api_key:
        typer.echo(f"错误: 请设置 {env_var} 环境变量", err=True)
        raise typer.Exit(1)

    # 扫描任务文件
    tasks_path = Path(tasks_dir)
    if not tasks_path.exists():
        typer.echo(f"错误: 任务目录不存在: {tasks_dir}", err=True)
        raise typer.Exit(1)

    task_files = sorted(tasks_path.glob("*.json"))
    if not task_files:
        typer.echo(f"错误: 没有找到任务文件", err=True)
        raise typer.Exit(1)

    # 输出目录: <trace_root>/{provider}_{model}/{task_set_name}/
    trace_root_path = Path(trace_root).expanduser() if trace_root else default_trace_root()
    actual_model = model.replace("/", "-")
    mode_suffix = "_text" if input_mode == "text" else ""
    base_name = f"{provider}_{actual_model}{mode_suffix}"
    if task_set_name:
        run_dir = trace_root_path / base_name / task_set_name
    else:
        # 无 task_set_name 时用时间戳子目录（兼容旧用法）
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        run_dir = trace_root_path / base_name / timestamp
    run_dir.mkdir(parents=True, exist_ok=True)
    # run_id 用于 generate 命令的 --run-id 兼容
    run_id = str(run_dir.relative_to(trace_root_path))

    # 解析 exclude_tools 为 set
    exclude_set = set(t.strip() for t in exclude_tools.split(",") if t.strip())

    typer.echo(f"🚀 批量运行 {len(task_files)} 个任务")
    typer.echo(f"提供商: {provider.upper()}")
    typer.echo(f"模型: {model}")
    typer.echo(f"输出目录: {run_dir}")
    typer.echo("")

    success = 0
    failed = 0
    skipped = 0
    failed_tasks = []

    for i, task_file in enumerate(task_files, 1):
        task_name = task_file.stem

        if skip_existing and (run_dir / f"{task_name}.json").exists():
            typer.echo(f"[{i}/{len(task_files)}] {task_name}... ⏭️  skip")
            skipped += 1
            continue

        typer.echo(f"[{i}/{len(task_files)}] {task_name}...", nl=False)

        try:
            # 加载任务
            with open(task_file, 'r', encoding='utf-8') as f:
                task_data = json.load(f)

            # exclude_tools 过滤：含指定工具的任务整体跳过
            if exclude_set:
                task_tools = set(task_data.get("tools", []))
                hit = task_tools & exclude_set
                if hit:
                    typer.echo(f" ⏭️  skip (excluded tool: {','.join(hit)})")
                    skipped += 1
                    continue

            task_obj = Task.from_dict(task_data)

            # 创建工具执行器
            tool_executor = _create_tool_executor(
                str(task_file),
                provider,
                api_key,
                all_tools=all_tools,
                doc_mode=doc_mode,
            )

            if provider == "openai-chat":
                # Chat Completions API（GPT-5.2 等纯文本模型）
                from eval.models.chat_completions_runner import ChatCompletionsRunner
                runner = ChatCompletionsRunner(
                    api_key=api_key, model=model,
                    tool_executor=tool_executor, quiet=True,
                )
                trace = runner.run_task(task_obj, str(task_file))
            elif provider == "gemini-chat":
                # Gemini generate_content（Gemini 3.x Pro 等文本模型）
                from eval.models.gemini_chat_runner import GeminiChatRunner
                runner = GeminiChatRunner(
                    api_key=api_key, model=model,
                    tool_executor=tool_executor, quiet=True,
                )
                trace = runner.run_task(task_obj, str(task_file))
            else:
                # Realtime API（音频/文本模式）
                runner = AudioTaskRunner(
                    api_key=api_key,
                    provider=provider,
                    model=model,
                    voice=voice,
                    tool_executor=tool_executor,
                    output_dir=str(trace_root_path),
                    audio_cache_dir=audio_cache_dir,
                    region=region,
                    quiet=True,
                    input_mode=input_mode,
                    turn_detection_mode=turn_detection,
                    audio_variant=audio_variant,
                    tts_backend=tts_backend,
                    clone_manifest=clone_manifest,
                    clone_accent=clone_accent,
                    clone_policy=clone_policy,
                    clone_model=clone_model,
                )
                trace = runner.run_task_sync(task_obj, str(task_file), None)

            # 保存 trace
            output_path = run_dir / f"{task_name}.json"
            trace.save_to_file(str(output_path))

            typer.echo(" ✅")
            success += 1

        except Exception as e:
            typer.echo(f" ❌ {str(e)[:50]}")
            failed += 1
            failed_tasks.append(task_name)

        # 延迟避免限流
        if i < len(task_files):
            time.sleep(delay)

    typer.echo("")
    typer.echo(f"=== 完成: {success} 成功, {failed} 失败, {skipped} 跳过 ===")
    if failed_tasks:
        typer.echo(f"失败的任务: {', '.join(failed_tasks)}")
    typer.echo(f"Traces 保存在: {run_dir}")


def _create_tool_executor(
    task_path: str,
    provider: str,
    api_key: str,
    all_tools: bool = False,
    doc_mode: str = "default",
) -> ToolExecutor:
    """创建工具执行器（根据任务类别注册相应工具）"""
    tool_executor = ToolExecutor(doc_mode=doc_mode)

    # 从 JSON 文件读取类别和工具列表
    data = {}
    category = None
    task_tools = []
    try:
        import json
        with open(task_path, encoding='utf-8') as f:
            data = json.load(f)
        category = data.get('tool_category')
        task_tools = data.get('tools', [])
    except Exception:
        pass

    # Multi-step 任务：使用 Failing_Tools adapter
    scenario_type = data.get("scenario_type", "") if data else ""
    if scenario_type == "multi_step" and data.get("server"):
        from eval.tools.failing_tools.adapter import create_executor_for_server
        _, ft_executor = create_executor_for_server(
            data["server"], tool_names=task_tools or None
        )
        ft_executor.doc_mode = doc_mode
        return ft_executor

    # 优先使用 task JSON 中的 tools 字段（支持 proactive 和跨领域任务）
    if task_tools:
        for tool_name in task_tools:
            if tool_name in TOOL_MAP:
                tool_executor.register_tool(TOOL_MAP[tool_name]())
        if len(tool_executor.tools) > 0:
            if all_tools:
                _register_all_tools(tool_executor)
            if provider in ("openai", "openai-chat") and any(
                name in tool_executor.tools for name in ("web_search", "fetch_url")
            ):
                from openai import OpenAI
                llm_client = OpenAI(api_key=api_key)
                tool_executor.register_tool(ExtractInfoTool(llm_client))
            return tool_executor

    # Fallback: 根据任务类别注册相应的工具
    if category == 'healthcare':
        tool_executor.register_tool(DoctorSearchTool())
        tool_executor.register_tool(BookAppointmentTool())
        tool_executor.register_tool(MedicineSearchTool())
    elif category == 'financial':
        tool_executor.register_tool(TransferMoneyTool())
        tool_executor.register_tool(CheckBalanceTool())
        tool_executor.register_tool(GetTransactionHistoryTool())
        tool_executor.register_tool(ListBillsTool())
        tool_executor.register_tool(PayBillTool())
    elif category == 'education':
        tool_executor.register_tool(CourseSearchTool())
        tool_executor.register_tool(EnrollCourseTool())
        tool_executor.register_tool(BookSearchTool())
        tool_executor.register_tool(ReserveBookTool())
        tool_executor.register_tool(RenewBookTool())
    elif category == 'transportation':
        tool_executor.register_tool(RequestRideTool())
        tool_executor.register_tool(CheckRideStatusTool())
        tool_executor.register_tool(CancelRideTool())
        tool_executor.register_tool(SearchParkingTool())
        tool_executor.register_tool(ReserveParkingSpotTool())
    elif category == 'travel_booking':
        tool_executor.register_tool(RestaurantSearchTool())
        tool_executor.register_tool(MakeReservationTool())
        tool_executor.register_tool(FlightSearchTool())
        tool_executor.register_tool(BookFlightTool())
        tool_executor.register_tool(HotelSearchTool())
        tool_executor.register_tool(BookHotelTool())
        tool_executor.register_tool(CarRentalTool())
        tool_executor.register_tool(BookCarTool())
        tool_executor.register_tool(TrainSearchTool())
        tool_executor.register_tool(BookTrainTool())
        tool_executor.register_tool(AttractionSearchTool())
        tool_executor.register_tool(BookAttractionTicketTool())
    elif category == 'entertainment':
        tool_executor.register_tool(MovieSearchTool())
        tool_executor.register_tool(BookMovieTicketTool())
        tool_executor.register_tool(ShowSearchTool())
        tool_executor.register_tool(BookShowTicketTool())
        tool_executor.register_tool(SportsEventSearchTool())
        tool_executor.register_tool(BookSportsTicketTool())
    elif category == 'life_services':
        tool_executor.register_tool(DeliveryRestaurantSearchTool())
        tool_executor.register_tool(PlaceFoodOrderTool())
        tool_executor.register_tool(TrackPackageTool())
        tool_executor.register_tool(HomeServiceSearchTool())
        tool_executor.register_tool(BookCleaningServiceTool())
    elif category == 'shopping_retail':
        tool_executor.register_tool(ProductSearchTool())
        tool_executor.register_tool(ProductDetailsTool())
        tool_executor.register_tool(PlaceRetailOrderTool())
        tool_executor.register_tool(TrackRetailOrderTool())
        tool_executor.register_tool(CheckReturnPolicyTool())
    elif category == 'calendar_communication':
        tool_executor.register_tool(CheckCalendarTool())
        tool_executor.register_tool(CreateEventTool())
        tool_executor.register_tool(ContactSearchTool())
        tool_executor.register_tool(DraftMessageTool())
        tool_executor.register_tool(SendMessageTool())
    elif category == 'housing_rental':
        tool_executor.register_tool(RentalListingSearchTool())
        tool_executor.register_tool(RentalListingDetailsTool())
        tool_executor.register_tool(BookViewingTool())
        tool_executor.register_tool(RentalAgentSearchTool())
        tool_executor.register_tool(DraftAgentMessageTool())
    elif category == 'jobs_career':
        tool_executor.register_tool(JobSearchTool())
        tool_executor.register_tool(JobDetailsTool())
        tool_executor.register_tool(SaveJobTool())
        tool_executor.register_tool(DraftApplicationTool())
        tool_executor.register_tool(TrackApplicationStatusTool())
    elif category == 'civic_services':
        tool_executor.register_tool(ServiceCenterSearchTool())
        tool_executor.register_tool(BookServiceAppointmentTool())
        tool_executor.register_tool(CheckCivicApplicationStatusTool())
        tool_executor.register_tool(RequiredDocumentsTool())
    elif category == 'telecom_services':
        tool_executor.register_tool(CheckMobilePlanTool())
        tool_executor.register_tool(PhonePlanSearchTool())
        tool_executor.register_tool(ChangePhonePlanTool())
        tool_executor.register_tool(CheckDataUsageTool())
        tool_executor.register_tool(PayPhoneBillTool())
    elif category == 'personal_productivity':
        tool_executor.register_tool(CreateReminderTool())
        tool_executor.register_tool(ListRemindersTool())
        tool_executor.register_tool(CreateNoteTool())
        tool_executor.register_tool(SearchNotesTool())
    elif category == 'multi':
        # 多领域场景：娱乐 + 餐饮
        # Entertainment tools
        tool_executor.register_tool(MovieSearchTool())
        tool_executor.register_tool(BookMovieTicketTool())
        tool_executor.register_tool(ShowSearchTool())
        tool_executor.register_tool(BookShowTicketTool())
        tool_executor.register_tool(SportsEventSearchTool())
        tool_executor.register_tool(BookSportsTicketTool())
        # Restaurant tools
        tool_executor.register_tool(RestaurantSearchTool())
        tool_executor.register_tool(MakeReservationTool())
    else:
        tool_executor.register_tool(WebSearchTool())
        tool_executor.register_tool(FetchURLTool())

    if all_tools:
        _register_all_tools(tool_executor)

    if provider in ("openai", "openai-chat") and any(
        name in tool_executor.tools for name in ("web_search", "fetch_url")
    ):
        from openai import OpenAI
        llm_client = OpenAI(api_key=api_key)
        tool_executor.register_tool(ExtractInfoTool(llm_client))

    return tool_executor


@app.command()
def tts_generate(
    path: str = typer.Argument(..., help="场景文件或目录路径"),
    force: bool = typer.Option(False, "--force", "-f", help="强制重新生成（忽略已有缓存）"),
    cache_dir: Optional[str] = typer.Option(None, "--cache-dir", help="TTS 缓存目录（默认项目级 outputs/audio）"),
    variant: str = typer.Option("default", "--variant", help="audio 变体: default / no_prosody / noisy"),
    tts_backend: str = typer.Option("openai", "--tts-backend", help="TTS backend: openai / voice_cloning"),
    clone_manifest: Optional[str] = typer.Option(None, "--clone-manifest", help="CommonVoice clone manifest path"),
    clone_accent: Optional[str] = typer.Option(None, "--clone-accent", help="Optional CommonVoice accent filter for ablation"),
    clone_policy: str = typer.Option("task_hash", "--clone-policy", help="Voice clone speaker policy"),
    clone_model: str = typer.Option("tts_models/multilingual/multi-dataset/xtts_v2", "--clone-model", help="Local Coqui TTS voice-cloning model"),
):
    """
    预生成 TTS 音频缓存

    可以指定单个场景文件或整个目录。
    """
    from eval.audio.tts_cache import TTSCache, generate_all_caches

    target = Path(path)

    if target.is_file():
        # 单个文件
        typer.echo(f"生成音频缓存: {path}")
        cache = TTSCache(
            cache_dir=cache_dir,
            variant=variant,
            tts_backend=tts_backend,
            clone_manifest=clone_manifest,
            clone_accent=clone_accent,
            clone_policy=clone_policy,
            clone_model=clone_model,
        )

        if cache.has_cache(path) and not force:
            typer.echo("缓存已存在，跳过（使用 --force 强制重新生成）")
            return

        cache.generate_cache(path)
        typer.echo("✅ 完成")

    elif target.is_dir():
        # 整个目录
        typer.echo(f"批量生成音频缓存: {path}")
        generate_all_caches(
            path,
            cache_dir=cache_dir,
            variant=variant,
            tts_backend=tts_backend,
            clone_manifest=clone_manifest,
            clone_accent=clone_accent,
            clone_policy=clone_policy,
            clone_model=clone_model,
        )
        typer.echo("✅ 完成")

    else:
        typer.echo(f"错误: 路径不存在: {path}", err=True)
        raise typer.Exit(1)


@app.command()
def version():
    """
    显示版本信息
    """
    from eval import __version__
    typer.echo(f"Audio Tool Bench v{__version__}")


if __name__ == "__main__":
    app()
