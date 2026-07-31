"""
Adapter: Failing_Tools BaseServiceAPI → Audio Tool Bench Tool interface.

Reads func_doc JSONL for parameter schemas, routes calls to server methods,
and returns results in the standard {success, output, raw_output, error} format.
"""

import json
import time
import importlib
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..base import Tool, ToolExecutor

# Server module → class name mapping
SERVER_CLASSES = {
    "uber_eats": ("eval.tools.failing_tools.servers.uber_eats", "UberEatsOrderAPI"),
    "amazon": ("eval.tools.failing_tools.servers.amazon", "AmazonAPI"),
    "booking": ("eval.tools.failing_tools.servers.booking", "BookingAPI"),
    "spotify": ("eval.tools.failing_tools.servers.spotify", "SpotifyAPI"),
    "instacart": ("eval.tools.failing_tools.servers.instacart", "InstacartAPI"),
    "google_calendar": ("eval.tools.failing_tools.servers.google_calendar", "GoogleCalendarAPI"),
    "gmail": ("eval.tools.failing_tools.servers.gmail", "GmailAPI"),
    "robinhood": ("eval.tools.failing_tools.servers.robinhood", "RobinhoodAPI"),
    "uber": ("eval.tools.failing_tools.servers.uber", "UberAPI"),
    "lyft": ("eval.tools.failing_tools.servers.lyft", "LyftAPI"),
}

_BASE_DIR = Path(__file__).parent


def _convert_type(bfcl_type: str) -> str:
    """Convert BFCL type names to JSON Schema types."""
    mapping = {
        "dict": "object",
        "any": "string",
        "float": "number",
        "integer": "integer",
        "int": "integer",
        "string": "string",
        "boolean": "boolean",
        "array": "array",
        "list": "array",
    }
    return mapping.get(bfcl_type, "string")


def _convert_schema(bfcl_params: Dict[str, Any]) -> Dict[str, Any]:
    """Convert BFCL parameter schema to OpenAI JSON Schema format."""
    properties = {}
    for param_name, param_def in bfcl_params.get("properties", {}).items():
        prop = {"description": param_def.get("description", "")}
        ptype = param_def.get("type", "string")
        prop["type"] = _convert_type(ptype)

        if ptype == "array" and "items" in param_def:
            items = param_def["items"]
            if isinstance(items, dict):
                item_type = items.get("type", "string")
                prop["items"] = {"type": _convert_type(item_type)}

        if "default" in param_def and param_def["default"] is not None:
            prop["default"] = param_def["default"]

        properties[param_name] = prop

    schema = {
        "type": "object",
        "properties": properties,
    }
    required = bfcl_params.get("required", [])
    if required:
        schema["required"] = required
    return schema


def _load_func_docs(server_name: str) -> Dict[str, Dict[str, Any]]:
    """Load function docs from JSONL file, keyed by function name."""
    path = _BASE_DIR / "func_docs" / f"{server_name}.json"
    docs = {}
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            doc = json.loads(line)
            docs[doc["name"]] = doc
    return docs


class FailingToolAdapter(Tool):
    """Wraps a single method of a Failing_Tools server as a Tool."""

    def __init__(
        self,
        server_instance: Any,
        func_name: str,
        func_doc: Dict[str, Any],
    ):
        self._server = server_instance
        self._func_name = func_name
        self._func_doc = func_doc
        schema = _convert_schema(func_doc.get("parameters", {}))

        # Strip optional params that the benchmark doesn't use.
        # Optional fields (guest_name, payment_method_id, etc.) cause models to
        # unnecessarily ask the user, which isn't what we're evaluating.
        # Keep: required params + params used in chain templates (e.g. variant_id).
        self._keep_params: Optional[set] = None  # set by strip_optional_params()


        self._openai_params = schema

    @property
    def name(self) -> str:
        return self._func_name

    @property
    def description(self) -> str:
        return self._func_doc.get("description", "")

    def strip_optional_params(self, keep_params: set):
        """Remove optional params not in keep_params from the schema shown to models."""
        required = set(self._openai_params.get("required", []))
        keep = required | keep_params
        if "properties" in self._openai_params:
            self._openai_params["properties"] = {
                k: v for k, v in self._openai_params["properties"].items()
                if k in keep
            }

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._openai_params

    def execute(self, **kwargs) -> Dict[str, Any]:
        start = time.time()
        try:
            # Normalize location param: string → default coords, missing → default
            if "location" in self._openai_params.get("properties", {}):
                loc = kwargs.get("location")
                if loc is None or isinstance(loc, str):
                    kwargs["location"] = {"lat": 37.7749, "lng": -122.4194}
                elif isinstance(loc, dict) and "lat" not in loc:
                    kwargs["location"] = {"lat": 37.7749, "lng": -122.4194}

            method = getattr(self._server, self._func_name)
            result = method(**kwargs)
            elapsed = (time.time() - start) * 1000

            # Format output text for the model
            if isinstance(result, (dict, list)):
                output = json.dumps(result, ensure_ascii=False, indent=2)
            else:
                output = str(result)

            return {
                "success": True,
                "output": output,
                "raw_output": result,
                "error": None,
                "latency_ms": elapsed,
            }
        except Exception as e:
            elapsed = (time.time() - start) * 1000
            error_msg = str(e)
            # Failing_Tools servers raise structured errors
            error_dict = getattr(e, "error", None)
            if error_dict:
                error_msg = json.dumps(error_dict, ensure_ascii=False)
            return {
                "success": False,
                "output": f"Error: {error_msg}",
                "raw_output": error_dict,
                "error": error_msg,
                "latency_ms": elapsed,
            }


def load_server(
    server_name: str,
    scenario: Optional[Dict[str, Any]] = None,
) -> Any:
    """Instantiate a server and optionally load scenario state.

    Args:
        server_name: Key in SERVER_CLASSES (e.g. "uber_eats")
        scenario: If None, loads from initial_states/{server_name}.json
    Returns:
        The server instance (BaseServiceAPI subclass)
    """
    module_path, class_name = SERVER_CLASSES[server_name]
    mod = importlib.import_module(module_path)
    cls = getattr(mod, class_name)
    instance = cls()

    if scenario is None:
        state_path = _BASE_DIR / "initial_states" / f"{server_name}.json"
        with open(state_path) as f:
            scenario = json.load(f)

    instance._load_scenario(scenario)

    # Server-specific setup
    if server_name == "gmail" and not instance.user_id:
        # Gmail requires a user_id to be set
        users = scenario.get("profile", scenario.get("users", {}))
        if users:
            instance.user_id = next(iter(users))

    return instance


def create_tools_for_server(
    server_name: str,
    scenario: Optional[Dict[str, Any]] = None,
    tool_names: Optional[List[str]] = None,
) -> tuple[Any, List[FailingToolAdapter]]:
    """Create Tool adapters for a server's functions.

    Args:
        server_name: Key in SERVER_CLASSES
        scenario: Optional initial state override
        tool_names: If provided, only wrap these functions. Otherwise wrap all.
    Returns:
        (server_instance, list_of_tool_adapters)
    """
    instance = load_server(server_name, scenario)
    func_docs = _load_func_docs(server_name)

    tools = []
    for func_name, doc in func_docs.items():
        if tool_names and func_name not in tool_names:
            continue
        # Verify the method exists on the server
        if hasattr(instance, func_name) and callable(getattr(instance, func_name)):
            tools.append(FailingToolAdapter(instance, func_name, doc))

    return instance, tools


def create_executor_for_server(
    server_name: str,
    scenario: Optional[Dict[str, Any]] = None,
    tool_names: Optional[List[str]] = None,
    strip_optional: bool = True,
) -> tuple[Any, ToolExecutor]:
    """Create a ToolExecutor loaded with a server's tools.

    Returns:
        (server_instance, tool_executor)
    """
    instance, tools = create_tools_for_server(server_name, scenario, tool_names)

    # Strip optional params not used by any chain template for this server
    if strip_optional:
        from eval.tools.failing_tools.chain_templates import _merged_templates
        server_templates = _merged_templates().get(server_name, {})
        # Collect all params used per tool across all templates
        used_params: Dict[str, set] = {}
        for tdef in server_templates.values():
            for fk in tdef.get("param_flow", {}):
                parts = fk.split(".", 1)
                if len(parts) == 2:
                    tool_name = parts[0]
                    param_name = parts[1].split(".")[0].split("[")[0]
                    used_params.setdefault(tool_name, set()).add(param_name)
            for uk in tdef.get("user_params", {}):
                parts = uk.split(".", 1)
                if len(parts) == 2:
                    tool_name = parts[0]
                    param_name = parts[1].split(".")[0].split("[")[0]
                    used_params.setdefault(tool_name, set()).add(param_name)

        for tool in tools:
            keep = used_params.get(tool.name, set())
            if keep:
                tool.strip_optional_params(keep)

    executor = ToolExecutor()
    for tool in tools:
        executor.register_tool(tool)
    return instance, executor
