"""
Bill payment tools
"""
from typing import Dict, Any
import random
import string
from datetime import datetime

from .base import Tool
from .mock_data import BILLS


class ListBillsTool(Tool):
    """Bill listing tool"""

    def __init__(self):
        self.bills = BILLS

    @property
    def name(self) -> str:
        return "list_bills"

    @property
    def description(self) -> str:
        return "List bills filtered by type and status."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # TODO: optional 参数暂时禁用
                # "bill_type": {"type": "string", "description": "Bill type (Electricity, Water, Gas, Internet)", "enum": ["Electricity", "Water", "Gas", "Internet"]},
                # "status": {"type": "string", "description": "Bill status (Unpaid, Paid)", "enum": ["Unpaid", "Paid"]},
                # "start_date": {"type": "string", "description": "Start date (YYYY-MM-DD)"},
                # "end_date": {"type": "string", "description": "End date (YYYY-MM-DD)"}
            },
            "required": []
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        bill_type = kwargs.get("bill_type")
        status = kwargs.get("status")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")

        results = self.bills.copy()

        if bill_type:
            results = [b for b in results if b["bill_type"] == bill_type]
        if status:
            results = [b for b in results if b["status"] == status]
        if start_date:
            results = [b for b in results if b["due_date"] >= start_date]
        if end_date:
            results = [b for b in results if b["due_date"] <= end_date]

        return {
            "success": True,
            "count": len(results),
            "bills": results
        }


class PayBillTool(Tool):
    """Bill payment tool"""

    def __init__(self):
        self.payments = []

    @property
    def name(self) -> str:
        return "pay_bill"

    @property
    def description(self) -> str:
        return "Pay a bill with bill ID and payment account."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "bill_id": {"type": "string", "description": "Bill ID"}
                # TODO: optional 参数暂时禁用
                # "payment_account": {"type": "string", "description": "Payment account number"},
                # "auto_pay": {"type": "boolean", "description": "Enable auto-pay (optional)"}
            },
            "required": ["bill_id"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        bill_id = kwargs.get("bill_id")
        payment_account = kwargs.get("payment_account")
        auto_pay = kwargs.get("auto_pay", False)

        payment_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        payment = {
            "payment_id": payment_id,
            "bill_id": bill_id,
            "payment_account": payment_account,
            "status": "Payment Successful",
            "timestamp": timestamp,
            "auto_pay_enabled": auto_pay
        }

        self.payments.append(payment)

        message = "Payment successful"
        if auto_pay:
            message += ", auto-pay has been enabled"

        return {
            "success": True,
            "message": message,
            "payment": payment
        }
