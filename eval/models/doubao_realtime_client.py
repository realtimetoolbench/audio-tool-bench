"""
ByteDance Volcengine Doubao Realtime API client.
Compatible with the OpenAI Realtime API format.
"""
from eval.models.openai_realtime_client import OpenAIRealtimeClient


class DoubaoRealtimeClient(OpenAIRealtimeClient):
    """ByteDance Doubao Realtime API client (OpenAI Realtime API compatible)."""

    def __init__(
        self,
        api_key: str,
        model: str = "doubao-1.5-realtime-voice-pro",
        voice: str = "zh_female_wanwanxiaohe_moon_bigtts",
        tool_executor=None
    ):
        """
        Initialize the Doubao Realtime API client.

        Args:
            api_key: Volcengine API key (gateway access key).
            model: Model name.
            voice: Voice (Doubao prebuilt voice or a custom cloned voice ID).
            tool_executor: Tool executor (optional).
        """
        super().__init__(
            api_key=api_key,
            model=model,
            voice=voice,
            tool_executor=tool_executor,
            base_url="wss://ai-gateway.vei.volces.com/v1/realtime"
        )
