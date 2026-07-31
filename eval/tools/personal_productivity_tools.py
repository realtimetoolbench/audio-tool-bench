"""
Personal productivity tools
"""
from typing import Dict, Any
import random
import string

from .base import Tool
from .mock_data import REMINDERS, NOTES


class CreateReminderTool(Tool):
    @property
    def name(self) -> str:
        return "create_reminder"

    @property
    def description(self) -> str:
        return "Create a personal reminder."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Reminder title"},
                "due_time": {"type": "string", "description": "Due time (YYYY-MM-DD HH:MM)"},
            },
            "required": ["title", "due_time"],
        }

    def execute(self, title: str, due_time: str, **kwargs) -> Dict[str, Any]:
        reminder = {
            "reminder_id": "rem_" + "".join(random.choices(string.digits, k=6)),
            "title": title,
            "due_time": due_time,
            "status": "Pending",
        }
        return {"success": True, "message": "Reminder created", "reminder": reminder}


class ListRemindersTool(Tool):
    @property
    def name(self) -> str:
        return "list_reminders"

    @property
    def description(self) -> str:
        return "List personal reminders."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "status": {"type": "string", "description": "Reminder status"}
            },
            "required": [],
        }

    def execute(self, status: str = None, **kwargs) -> Dict[str, Any]:
        results = REMINDERS.copy()
        if status:
            results = [r for r in results if r["status"].lower() == status.lower()]
        return {"success": True, "count": len(results), "reminders": results}


class CreateNoteTool(Tool):
    @property
    def name(self) -> str:
        return "create_note"

    @property
    def description(self) -> str:
        return "Create a personal note."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Note title"},
                "content": {"type": "string", "description": "Note content"},
            },
            "required": ["title", "content"],
        }

    def execute(self, title: str, content: str, **kwargs) -> Dict[str, Any]:
        note = {
            "note_id": "note_" + "".join(random.choices(string.digits, k=6)),
            "title": title,
            "content": content,
        }
        return {"success": True, "message": "Note created", "note": note}


class SearchNotesTool(Tool):
    @property
    def name(self) -> str:
        return "search_notes"

    @property
    def description(self) -> str:
        return "Search personal notes by keyword."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Keyword to search in notes"}
            },
            "required": ["keyword"],
        }

    def execute(self, keyword: str, **kwargs) -> Dict[str, Any]:
        q = keyword.lower()
        results = [n for n in NOTES if q in n["title"].lower() or q in n["content"].lower()]
        return {"success": True, "count": len(results), "notes": results}
