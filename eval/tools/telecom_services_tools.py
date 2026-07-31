"""
Telecom service tools
"""
from typing import Dict, Any
import random
import string

from .base import Tool
from .mock_data import MOBILE_PLANS, TELECOM_ACCOUNTS


def _find_plan(plan_id: str):
    for plan in MOBILE_PLANS:
        if plan["plan_id"] == plan_id:
            return plan
    return None


class CheckMobilePlanTool(Tool):
    @property
    def name(self) -> str:
        return "check_mobile_plan"

    @property
    def description(self) -> str:
        return "Check current mobile plan by phone number."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Mobile phone number"}
            },
            "required": ["phone_number"],
        }

    def execute(self, phone_number: str, **kwargs) -> Dict[str, Any]:
        account = TELECOM_ACCOUNTS.get(phone_number)
        if not account:
            return {"success": False, "error": f"Telecom account not found: {phone_number}"}
        plan = _find_plan(account["current_plan_id"])
        return {"success": True, "account": account, "plan": plan}


class PhonePlanSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_phone_plans"

    @property
    def description(self) -> str:
        return "Search mobile phone plans by carrier, data amount, and price."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "carrier": {"type": "string", "description": "Carrier name"},
                "min_data_gb": {"type": "number", "description": "Minimum data in GB"},
                "max_monthly_fee": {"type": "number", "description": "Maximum monthly fee"},
            },
            "required": [],
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        carrier = kwargs.get("carrier")
        min_data_gb = kwargs.get("min_data_gb")
        max_monthly_fee = kwargs.get("max_monthly_fee")
        results = MOBILE_PLANS.copy()
        if carrier:
            results = [p for p in results if carrier.lower() in p["carrier"].lower()]
        if min_data_gb is not None:
            results = [p for p in results if p["data_gb"] >= min_data_gb]
        if max_monthly_fee is not None:
            results = [p for p in results if p["monthly_fee"] <= max_monthly_fee]
        return {"success": True, "count": len(results), "plans": results}


class ChangePhonePlanTool(Tool):
    @property
    def name(self) -> str:
        return "change_phone_plan"

    @property
    def description(self) -> str:
        return "Change a mobile account to a new phone plan."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Mobile phone number"},
                "plan_id": {"type": "string", "description": "Plan ID from search_phone_plans"},
            },
            "required": ["phone_number", "plan_id"],
        }

    def execute(self, phone_number: str, plan_id: str, **kwargs) -> Dict[str, Any]:
        if phone_number not in TELECOM_ACCOUNTS:
            return {"success": False, "error": f"Telecom account not found: {phone_number}"}
        plan = _find_plan(plan_id)
        if not plan:
            return {"success": False, "error": f"Plan not found: {plan_id}"}
        change = {
            "change_id": "planchg_" + "".join(random.choices(string.digits, k=6)),
            "phone_number": phone_number,
            "new_plan_id": plan_id,
            "new_plan_name": plan["name"],
            "status": "Scheduled",
        }
        return {"success": True, "message": "Phone plan change scheduled", "change": change}


class CheckDataUsageTool(Tool):
    @property
    def name(self) -> str:
        return "check_data_usage"

    @property
    def description(self) -> str:
        return "Check mobile data usage by phone number."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Mobile phone number"}
            },
            "required": ["phone_number"],
        }

    def execute(self, phone_number: str, **kwargs) -> Dict[str, Any]:
        account = TELECOM_ACCOUNTS.get(phone_number)
        if not account:
            return {"success": False, "error": f"Telecom account not found: {phone_number}"}
        plan = _find_plan(account["current_plan_id"])
        return {
            "success": True,
            "phone_number": phone_number,
            "data_used_gb": account["data_used_gb"],
            "plan_data_gb": plan["data_gb"] if plan else None,
        }


class PayPhoneBillTool(Tool):
    @property
    def name(self) -> str:
        return "pay_phone_bill"

    @property
    def description(self) -> str:
        return "Pay a mobile phone bill."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "phone_number": {"type": "string", "description": "Mobile phone number"},
                "amount": {"type": "number", "description": "Payment amount"},
                "payment_account": {"type": "string", "description": "Payment account number"},
            },
            "required": ["phone_number", "amount", "payment_account"],
        }

    def execute(self, phone_number: str, amount: float, payment_account: str, **kwargs) -> Dict[str, Any]:
        if phone_number not in TELECOM_ACCOUNTS:
            return {"success": False, "error": f"Telecom account not found: {phone_number}"}
        payment = {
            "payment_id": "telpay_" + "".join(random.choices(string.digits, k=6)),
            "phone_number": phone_number,
            "amount": amount,
            "payment_account": payment_account,
            "status": "Paid",
        }
        return {"success": True, "message": "Phone bill paid", "payment": payment}
