"""
Package tracking tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import PACKAGES


class TrackPackageTool(Tool):
    """Package tracking tool"""

    def __init__(self):
        self.packages = PACKAGES

    @property
    def name(self) -> str:
        return "track_package"

    @property
    def description(self) -> str:
        return "Track package delivery status by tracking number."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "tracking_number": {"type": "string", "description": "Package tracking number"}
                # TODO: optional 参数暂时禁用
                # "company": {"type": "string", "description": "Delivery company (optional)"}
            },
            "required": ["tracking_number"]
        }

    def execute(self, tracking_number: str, company: str = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            package = self.packages.get(tracking_number)
            if not package:
                output = f"Package not found: {tracking_number}"
                return {"success": False, "output": output, "raw_output": None, "error": "Not found",
                        "latency_ms": (time.time() - start_time) * 1000}

            output = f"Package tracking successful!\n\nTracking number: {tracking_number}\nCompany: {package['company']}\n"
            output += f"Status: {package['status']}\n\nTracking history:\n"
            for record in package['history']:
                output += f"  {record['time']} - {record['location']}: {record['status']}\n"

            return {"success": True, "output": output, "raw_output": package, "error": None,
                    "latency_ms": (time.time() - start_time) * 1000}
        except Exception as e:
            return {"success": False, "output": f"Tracking failed: {str(e)}", "raw_output": None,
                    "error": str(e), "latency_ms": (time.time() - start_time) * 1000}
