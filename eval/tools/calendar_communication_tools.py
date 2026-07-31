"""
Calendar and communication tools
"""
from typing import Dict, Any
import random
import string
from datetime import datetime

from .base import Tool
from .mock_data import CALENDAR_EVENTS, CONTACTS


def _find_contact(contact_id: str):
    for contact in CONTACTS:
        if contact["contact_id"] == contact_id:
            return contact
    return None


class CheckCalendarTool(Tool):
    @property
    def name(self) -> str:
        return "check_calendar"

    @property
    def description(self) -> str:
        return "Check calendar events for a date."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "date": {"type": "string", "description": "Date to check (YYYY-MM-DD)"}
            },
            "required": ["date"],
        }

    def execute(self, date: str, **kwargs) -> Dict[str, Any]:
        events = [e for e in CALENDAR_EVENTS if e["date"] == date]
        return {"success": True, "count": len(events), "events": events}


class CreateEventTool(Tool):
    def __init__(self):
        self.events = []

    @property
    def name(self) -> str:
        return "create_event"

    @property
    def description(self) -> str:
        return "Create a calendar event."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Event title"},
                "date": {"type": "string", "description": "Event date (YYYY-MM-DD)"},
                "start_time": {"type": "string", "description": "Start time (HH:MM)"},
                "end_time": {"type": "string", "description": "End time (HH:MM)"},
                "location": {"type": "string", "description": "Event location"},
            },
            "required": ["title", "date", "start_time", "end_time"],
        }

    def execute(self, title: str, date: str, start_time: str, end_time: str, location: str = "", **kwargs) -> Dict[str, Any]:
        event = {
            "event_id": "evt_" + "".join(random.choices(string.digits, k=6)),
            "title": title,
            "date": date,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.events.append(event)
        return {"success": True, "message": "Event created", "event": event}


class ContactSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_contacts"

    @property
    def description(self) -> str:
        return "Search contacts by name."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "name": {"type": "string", "description": "Contact name keyword"}
            },
            "required": ["name"],
        }

    def execute(self, name: str, **kwargs) -> Dict[str, Any]:
        q = name.lower()
        results = [c for c in CONTACTS if q in c["name"].lower()]
        return {"success": True, "count": len(results), "contacts": results}


class DraftMessageTool(Tool):
    @property
    def name(self) -> str:
        return "draft_message"

    @property
    def description(self) -> str:
        return "Draft a message to a contact without sending it."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string", "description": "Contact ID from search_contacts"},
                "content": {"type": "string", "description": "Message content"},
            },
            "required": ["contact_id", "content"],
        }

    def execute(self, contact_id: str, content: str, **kwargs) -> Dict[str, Any]:
        contact = _find_contact(contact_id)
        if not contact:
            return {"success": False, "error": f"Contact not found: {contact_id}"}
        draft = {
            "draft_id": "msgdraft_" + "".join(random.choices(string.digits, k=6)),
            "contact_id": contact_id,
            "to": contact["name"],
            "content": content,
            "status": "Drafted",
        }
        return {"success": True, "message": "Message drafted", "draft": draft}


class SendMessageTool(Tool):
    @property
    def name(self) -> str:
        return "send_message"

    @property
    def description(self) -> str:
        return "Send a message to a contact."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "contact_id": {"type": "string", "description": "Contact ID from search_contacts"},
                "content": {"type": "string", "description": "Message content"},
            },
            "required": ["contact_id", "content"],
        }

    def execute(self, contact_id: str, content: str, **kwargs) -> Dict[str, Any]:
        contact = _find_contact(contact_id)
        if not contact:
            return {"success": False, "error": f"Contact not found: {contact_id}"}
        sent = {
            "message_id": "msg_" + "".join(random.choices(string.digits, k=6)),
            "contact_id": contact_id,
            "to": contact["name"],
            "phone": contact["phone"],
            "content": content,
            "status": "Sent",
        }
        return {"success": True, "message": "Message sent", "sent_message": sent}
