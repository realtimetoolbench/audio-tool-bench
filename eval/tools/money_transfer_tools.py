"""
Transfer Tools - 转账工具
包含转账汇款功能
"""

from typing import Dict, Any, List
from .base import Tool


class TransferMoneyTool(Tool):
    """转账汇款"""

    def __init__(self):
        # Mock 转账记录
        self.transfers = []
        # Mock 收款人信息
        self.payees = {
            "6217001234567891": {
                "account_number": "6217001234567891",
                "name": "张三",
                "bank": "建设银行"
            },
            "6228481234567891": {
                "account_number": "6228481234567891",
                "name": "李四",
                "bank": "农业银行"
            },
            "6222021234567891": {
                "account_number": "6222021234567891",
                "name": "王五",
                "bank": "工商银行"
            }
        }

    @property
    def name(self) -> str:
        return "transfer_money"

    @property
    def description(self) -> str:
        return "转账汇款，需要提供付款账户、收款账户、金额等信息"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                # TODO: optional 参数暂时禁用
                # "from_account": {
                #     "type": "string",
                #     "description": "付款账户号码"
                # },
                # "to_account": {
                #     "type": "string",
                #     "description": "收款账户号码"
                # },
                "amount": {
                    "type": "number",
                    "description": "转账金额（元）"
                },
                "payee_name": {
                    "type": "string",
                    "description": "收款人姓名（用于验证）"
                }
                # "remark": {
                #     "type": "string",
                #     "description": "转账备注（可选）"
                # },
                # "transfer_type": {
                #     "type": "string",
                #     "description": "转账类型：实时转账、普通转账、预约转账",
                #     "enum": ["实时转账", "普通转账", "预约转账"],
                #     "default": "实时转账"
                # }
            },
            "required": ["amount", "payee_name"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        import random
        import string
        from datetime import datetime

        from_account = kwargs.get("from_account")
        to_account = kwargs.get("to_account")
        amount = kwargs.get("amount")
        payee_name = kwargs.get("payee_name")
        remark = kwargs.get("remark", "")
        transfer_type = kwargs.get("transfer_type", "实时转账")

        # The public schema only requires amount + payee_name. If a hidden
        # to_account is provided, validate it; otherwise accept the named payee
        # as a mock transfer recipient.
        if to_account:
            if to_account not in self.payees:
                return {
                    "success": False,
                    "error": "收款账户不存在"
                }

            payee = self.payees[to_account]
            if payee["name"] != payee_name:
                return {
                    "success": False,
                    "error": "收款人姓名不匹配，请核对"
                }
        else:
            payee = {
                "name": payee_name,
                "bank": "Mock Bank",
            }

        # 验证金额
        if amount <= 0:
            return {
                "success": False,
                "error": "转账金额必须大于0"
            }

        if amount > 50000:
            return {
                "success": False,
                "error": "单笔转账金额不能超过50000元，请分批转账或联系银行"
            }

        # 生成转账记录
        transfer_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        transfer = {
            "transfer_id": transfer_id,
            "from_account": from_account,
            "to_account": to_account,
            "payee_name": payee_name,
            "payee_bank": payee["bank"],
            "amount": amount,
            "remark": remark,
            "transfer_type": transfer_type,
            "status": "成功",
            "timestamp": timestamp,
            "fee": 0 if transfer_type == "实时转账" else 2.0
        }

        self.transfers.append(transfer)

        return {
            "success": True,
            "message": "转账成功",
            "transfer": transfer
        }
