"""
Account Tools - 账户查询工具
包含余额查询和交易记录查询功能
"""

from typing import Dict, Any, List
from .base import Tool
from .mock_data import BANK_ACCOUNTS, TRANSACTIONS


def _build_account_index() -> Dict[str, Dict]:
    """从 mock_data.BANK_ACCOUNTS 构建 account_number → detail 映射"""
    return {
        a["account_id"]: {
            "account_number": a["account_id"],
            "account_type": a["type"],
            "bank": a["bank"],
            "balance": a["balance"],
            "currency": "CNY",
            "status": a["status"],
        }
        for a in BANK_ACCOUNTS
    }


def _build_transaction_index() -> Dict[str, List[Dict]]:
    """从 mock_data.TRANSACTIONS 构建 account_number → [transaction] 映射"""
    index: Dict[str, List[Dict]] = {}
    for t in TRANSACTIONS:
        aid = t["account_id"]
        index.setdefault(aid, []).append({
            "transaction_id": t["transaction_id"],
            "date": t["time"].split(" ")[0],
            "time": t["time"].split(" ")[1] if " " in t["time"] else "",
            "type": t["type"],
            "amount": t["amount"],
            "balance_after": t["balance_after"],
            "description": t.get("note", ""),
            "merchant": t.get("counterparty", ""),
        })
    return index


class CheckBalanceTool(Tool):
    """查询账户余额"""

    def __init__(self):
        self.accounts = _build_account_index()

    @property
    def name(self) -> str:
        return "check_balance"

    @property
    def description(self) -> str:
        return "查询账户余额，需要提供账户号码"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "账户号码"
                }
            },
            "required": ["account_number"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        account_number = kwargs.get("account_number")

        if account_number not in self.accounts:
            return {
                "success": False,
                "error": "账户不存在或账户号码错误"
            }

        account = self.accounts[account_number]

        return {
            "success": True,
            "account": account
        }


class GetTransactionHistoryTool(Tool):
    """查询交易记录"""

    def __init__(self):
        self.accounts = _build_account_index()
        self.transactions = _build_transaction_index()

    @property
    def name(self) -> str:
        return "get_transaction_history"

    @property
    def description(self) -> str:
        return "查询账户交易记录，支持按时间范围、交易类型筛选"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "account_number": {
                    "type": "string",
                    "description": "账户号码"
                }
                # TODO: optional 参数暂时禁用
                # "start_date": {
                #     "type": "string",
                #     "description": "开始日期，格式：YYYY-MM-DD"
                # },
                # "end_date": {
                #     "type": "string",
                #     "description": "结束日期，格式：YYYY-MM-DD"
                # },
                # "transaction_type": {
                #     "type": "string",
                #     "description": "交易类型：收入、支出",
                #     "enum": ["收入", "支出"]
                # },
                # "limit": {
                #     "type": "integer",
                #     "description": "返回记录数量限制，默认10条"
                # }
            },
            "required": ["account_number"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        account_number = kwargs.get("account_number")
        start_date = kwargs.get("start_date")
        end_date = kwargs.get("end_date")
        transaction_type = kwargs.get("transaction_type")
        limit = kwargs.get("limit", 10)

        if account_number not in self.accounts:
            return {
                "success": False,
                "error": "账户不存在或账户号码错误"
            }

        results = self.transactions.get(account_number, [])

        # 按日期范围筛选
        if start_date:
            results = [t for t in results if t["date"] >= start_date]
        if end_date:
            results = [t for t in results if t["date"] <= end_date]

        # 按交易类型筛选
        if transaction_type:
            results = [t for t in results if t["type"] == transaction_type]

        # 限制返回数量
        results = results[:limit]

        return {
            "success": True,
            "count": len(results),
            "transactions": results
        }
