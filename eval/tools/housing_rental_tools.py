"""
Housing rental tools
"""
from typing import Dict, Any
import random
import string

from .base import Tool
from .mock_data import RENTAL_LISTINGS, RENTAL_AGENTS


def _find_listing(listing_id: str):
    for listing in RENTAL_LISTINGS:
        if listing["listing_id"] == listing_id:
            return listing
    return None


def _find_agent(agent_id: str):
    for agent in RENTAL_AGENTS:
        if agent["agent_id"] == agent_id:
            return agent
    return None


class RentalListingSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_rental_listings"

    @property
    def description(self) -> str:
        return "Search rental listings by city, district, rent, and bedroom count."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "district": {"type": "string", "description": "District or area"},
                "max_rent": {"type": "number", "description": "Maximum monthly rent"},
                "bedrooms": {"type": "integer", "description": "Number of bedrooms"},
            },
            "required": ["city"],
        }

    def execute(self, city: str, district: str = None, max_rent: float = None, bedrooms: int = None, **kwargs) -> Dict[str, Any]:
        results = [l for l in RENTAL_LISTINGS if l["city"].lower() == city.lower()]
        if district:
            results = [l for l in results if district.lower() in l["district"].lower()]
        if max_rent is not None:
            results = [l for l in results if l["monthly_rent"] <= max_rent]
        if bedrooms is not None:
            results = [l for l in results if l["bedrooms"] == bedrooms]
        return {"success": True, "count": len(results), "listings": results}


class RentalListingDetailsTool(Tool):
    @property
    def name(self) -> str:
        return "get_listing_details"

    @property
    def description(self) -> str:
        return "Get rental listing details by listing ID."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string", "description": "Listing ID from search_rental_listings"}
            },
            "required": ["listing_id"],
        }

    def execute(self, listing_id: str, **kwargs) -> Dict[str, Any]:
        listing = _find_listing(listing_id)
        if not listing:
            return {"success": False, "error": f"Listing not found: {listing_id}"}
        return {"success": True, "listing": listing}


class BookViewingTool(Tool):
    @property
    def name(self) -> str:
        return "book_viewing"

    @property
    def description(self) -> str:
        return "Book a viewing appointment for a rental listing."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "listing_id": {"type": "string", "description": "Listing ID"},
                "date": {"type": "string", "description": "Viewing date (YYYY-MM-DD)"},
                "time": {"type": "string", "description": "Viewing time (HH:MM)"},
                "viewer_name": {"type": "string", "description": "Viewer name"},
                "phone": {"type": "string", "description": "Viewer phone number"},
            },
            "required": ["listing_id", "date", "time", "viewer_name", "phone"],
        }

    def execute(self, listing_id: str, date: str, time: str, viewer_name: str, phone: str, **kwargs) -> Dict[str, Any]:
        listing = _find_listing(listing_id)
        if not listing:
            return {"success": False, "error": f"Listing not found: {listing_id}"}
        viewing = {
            "viewing_id": "view_" + "".join(random.choices(string.digits, k=6)),
            "listing_id": listing_id,
            "date": date,
            "time": time,
            "viewer_name": viewer_name,
            "phone": phone,
            "status": "Booked",
        }
        return {"success": True, "message": "Viewing booked", "viewing": viewing}


class RentalAgentSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_agents"

    @property
    def description(self) -> str:
        return "Search rental agents by city."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
            },
            "required": ["city"],
        }

    def execute(self, city: str, **kwargs) -> Dict[str, Any]:
        results = [a for a in RENTAL_AGENTS if a["city"].lower() == city.lower()]
        return {"success": True, "count": len(results), "agents": results}


class DraftAgentMessageTool(Tool):
    @property
    def name(self) -> str:
        return "draft_agent_message"

    @property
    def description(self) -> str:
        return "Draft a message to a rental agent."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "agent_id": {"type": "string", "description": "Agent ID from search_agents"},
                "message": {"type": "string", "description": "Message content"},
            },
            "required": ["agent_id", "message"],
        }

    def execute(self, agent_id: str, message: str, **kwargs) -> Dict[str, Any]:
        agent = _find_agent(agent_id)
        if not agent:
            return {"success": False, "error": f"Agent not found: {agent_id}"}
        draft = {
            "draft_id": "agentdraft_" + "".join(random.choices(string.digits, k=6)),
            "agent_id": agent_id,
            "to": agent["name"],
            "message": message,
            "status": "Drafted",
        }
        return {"success": True, "message": "Agent message drafted", "draft": draft}
