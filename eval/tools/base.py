"""
工具基类和执行器
"""
from typing import Dict, Any, List, Optional
from abc import ABC, abstractmethod


class Tool(ABC):
    """工具基类"""

    @property
    @abstractmethod
    def name(self) -> str:
        """工具名称"""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """工具描述"""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """工具参数 schema（OpenAI function calling 格式）"""
        pass

    @abstractmethod
    def execute(self, **kwargs) -> Dict[str, Any]:
        """
        执行工具

        Returns:
            {
                "success": bool,
                "output": str,  # 返回给 LLM 的文本
                "raw_output": Any,  # 原始输出（用于 trace）
                "error": Optional[str]
            }
        """
        pass

    def to_openai_function(self, doc_mode: str = "default") -> Dict[str, Any]:
        """转换为 OpenAI function calling 格式"""
        if doc_mode == "minimal":
            params = self.parameters
            stripped: Dict[str, Any] = {"type": params.get("type", "object")}
            props = params.get("properties", {})
            stripped["properties"] = {
                key: {"type": value.get("type", "string")}
                for key, value in props.items()
            }
            if params.get("required"):
                stripped["required"] = list(params["required"])
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": "",
                    "parameters": stripped,
                }
            }

        if doc_mode == "verbose":
            extras = _VERBOSE_EXTRAS.get(self.name, {})
            description = self.description
            if extras.get("use_case"):
                description = f"{description}\n\nUse when: {extras['use_case']}"
            if extras.get("example"):
                description = f"{description}\n\nExample call: {extras['example']}"
            return {
                "type": "function",
                "function": {
                    "name": self.name,
                    "description": description,
                    "parameters": self.parameters,
                }
            }

        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters
            }
        }


_VERBOSE_EXTRAS: Dict[str, Dict[str, str]] = {}


def _load_verbose_extras() -> None:
    import json
    from pathlib import Path

    global _VERBOSE_EXTRAS
    path = Path(__file__).parent / "verbose_schemas.json"
    if path.exists():
        with path.open(encoding="utf-8") as f:
            _VERBOSE_EXTRAS = json.load(f)


_load_verbose_extras()


class ToolExecutor:
    """工具执行器"""

    def __init__(self, doc_mode: str = "default"):
        if doc_mode not in ("default", "minimal", "verbose"):
            raise ValueError(f"doc_mode must be default/minimal/verbose, got {doc_mode!r}")
        self.tools: Dict[str, Tool] = {}
        self.doc_mode = doc_mode

    def register_tool(self, tool: Tool):
        """注册工具"""
        self.tools[tool.name] = tool

    def get_tools_for_openai(self) -> List[Dict[str, Any]]:
        """获取所有工具的 OpenAI function calling 格式"""
        return [tool.to_openai_function(self.doc_mode) for tool in self.tools.values()]

    def execute_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        执行工具

        Returns:
            {
                "success": bool,
                "output": str,
                "raw_output": Any,
                "error": Optional[str],
                "latency_ms": float
            }
        """
        import time
        import json

        if tool_name not in self.tools:
            return {
                "success": False,
                "output": f"Unknown tool: {tool_name}",
                "raw_output": None,
                "error": f"Tool not found: {tool_name}",
                "latency_ms": 0
            }

        tool = self.tools[tool_name]

        start_time = time.time()
        try:
            result = tool.execute(**arguments)
        except Exception as e:
            return {
                "success": False,
                "output": f"Tool execution error: {str(e)}",
                "raw_output": None,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000
            }

        latency_ms = (time.time() - start_time) * 1000

        # 确保返回格式符合规范
        if not isinstance(result, dict):
            result = {"success": False, "error": "Tool returned non-dict result"}

        # 如果工具没有返回 output 字段，自动生成友好的文本输出
        if "output" not in result:
            if result.get("success"):
                output = self._format_tool_output(tool_name, result)
            else:
                # 失败时，使用 error 字段
                output = result.get("error", "Unknown error")
            result["output"] = output

        # 确保有 raw_output 字段
        if "raw_output" not in result:
            result["raw_output"] = result.copy()

        # 确保有 error 字段
        if "error" not in result:
            result["error"] = None

        # 添加延迟信息
        result["latency_ms"] = latency_ms

        return result

    def _format_tool_output(self, tool_name: str, result: Dict[str, Any]) -> str:
        """将工具结果格式化为友好的文本输出"""
        import json

        # 搜索类工具：格式化列表结果
        if "search" in tool_name or "list" in tool_name:
            count = result.get("count", 0)

            # 医生搜索
            if "doctors" in result:
                doctors = result.get("doctors", [])
                if not doctors:
                    return "未找到符合条件的医生。"
                output = f"找到 {count} 位医生：\n\n"
                for i, doc in enumerate(doctors, 1):
                    output += f"{i}. {doc.get('name', '未知')} - {doc.get('hospital', '')} {doc.get('department', '')}\n"
                    output += f"   职称: {doc.get('title', '未知')} | 专长: {doc.get('specialty', '未知')}\n"
                    if doc.get('available_dates'):
                        output += f"   可预约日期: {', '.join(doc['available_dates'])}\n"
                    output += "\n"
                return output

            # 航班搜索
            elif "flights" in result:
                flights = result.get("flights", [])
                if not flights:
                    return "未找到符合条件的航班。"
                output = f"找到 {count} 个航班：\n\n"
                for i, flight in enumerate(flights, 1):
                    output += f"{i}. {flight.get('flight_no', '')} - {flight.get('airline', '')}\n"
                    output += f"   起飞: {flight.get('departure', '')} → 到达: {flight.get('arrival', '')}\n"
                    output += f"   舱位: {flight.get('class', '')} | 价格: ¥{flight.get('price', 0)}\n\n"
                return output

            # 其他列表类结果：使用通用格式
            else:
                # 尝试找到列表字段
                for key in result:
                    if isinstance(result[key], list) and key not in ["available_dates"]:
                        items = result[key]
                        if not items:
                            return f"未找到符合条件的{key}。"
                        return f"找到 {count} 个结果。\n\n" + json.dumps(items, ensure_ascii=False, indent=2)

        # 预订/操作类工具：返回简洁的成功消息
        elif "book" in tool_name or "reserve" in tool_name or "pay" in tool_name:
            if result.get("success"):
                return "操作成功！\n\n" + json.dumps(result, ensure_ascii=False, indent=2)

        # 默认：返回 JSON 格式
        return json.dumps(result, ensure_ascii=False, indent=2)
