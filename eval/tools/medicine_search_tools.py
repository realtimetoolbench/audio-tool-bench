"""
Medicine search tools
"""
from typing import Dict, Any

from .base import Tool
from .mock_data import MEDICINES


class MedicineSearchTool(Tool):
    """Medicine search tool"""

    def __init__(self):
        self.medicines = MEDICINES

    @property
    def name(self) -> str:
        return "search_medicine"

    @property
    def description(self) -> str:
        return "Search for medicine information by name, category, and indications."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # TODO: optional 参数暂时禁用
                # "medicine_name": {"type": "string", "description": "Medicine name (supports fuzzy search)"},
                # "category": {"type": "string", "description": "Category (Antibiotic, Analgesic, Cold Medicine, Cough Medicine, Antihypertensive)"},
                # "indication": {"type": "string", "description": "Indication (e.g., cold, headache, cough, hypertension)"},
                # "max_price": {"type": "number", "description": "Maximum price"},
                # "prescription_required": {"type": "boolean", "description": "Whether prescription is required"}
            },
            "required": []
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        medicine_name = kwargs.get("medicine_name", "").lower()
        category = kwargs.get("category")
        indication = kwargs.get("indication")
        max_price = kwargs.get("max_price")
        prescription_required = kwargs.get("prescription_required")

        results = self.medicines.copy()

        if medicine_name:
            results = [m for m in results if medicine_name in m["name"].lower()]
        if category:
            results = [m for m in results if category.lower() in m["category"].lower()]
        if indication:
            results = [m for m in results if indication.lower() in m["indications"].lower()]
        if max_price is not None:
            results = [m for m in results if m["price"] <= max_price]
        if prescription_required is not None:
            results = [m for m in results if m["prescription_required"] == prescription_required]

        return {
            "success": True,
            "count": len(results),
            "medicines": results
        }
