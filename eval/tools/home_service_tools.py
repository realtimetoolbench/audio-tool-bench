"""
Home service tools
"""
from typing import Dict, Any
import random
import string

from .base import Tool
from .mock_data import HOME_SERVICES


class HomeServiceSearchTool(Tool):
    """Home service search tool"""

    def __init__(self):
        self.services = HOME_SERVICES

    @property
    def name(self) -> str:
        return "search_home_services"

    @property
    def description(self) -> str:
        return "Search for home services by city, service type, price range."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (e.g., Beijing, Shanghai, Chengdu)"}
                # TODO: optional 参数暂时禁用
                # "service_type": {"type": "string", "description": "Service type (cleaning, nanny, etc.)", "enum": ["cleaning", "nanny", "babysitter"]},
                # "max_price": {"type": "number", "description": "Maximum price (per hour or per day)"},
                # "time_preference": {"type": "string", "description": "Time preference (morning, afternoon, evening, all day)"}
            },
            "required": ["city"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        city = kwargs.get("city")
        service_type = kwargs.get("service_type")
        max_price = kwargs.get("max_price")
        time_preference = kwargs.get("time_preference")

        if city not in self.services:
            return {
                "success": False,
                "error": f"City not supported: {city}",
                "available_cities": list(self.services.keys())
            }

        results = self.services[city].copy()

        if service_type:
            results = [s for s in results if s["service_type"] == service_type]

        if max_price:
            results = [s for s in results if s.get("price_per_hour", s.get("price_per_day", 0)) <= max_price]

        if time_preference:
            results = [s for s in results if time_preference in s["available_time"]]

        # Add service_id to output for easy reference
        output = f"Found {len(results)} services:\n\n"
        for i, s in enumerate(results, 1):
            output += f"{i}. {s['name']} (ID: {s['service_id']})\n"
            output += f"   Type: {s['service_type']} | Rating: {s['rating']}/5.0\n"
            price_key = 'price_per_hour' if 'price_per_hour' in s else 'price_per_day'
            output += f"   Price: ¥{s.get(price_key, 'N/A')}\n\n"

        return {
            "success": True,
            "count": len(results),
            "output": output,
            "services": results
        }


class BookCleaningServiceTool(Tool):
    """Home service booking tool"""

    def __init__(self):
        self.bookings = []

    @property
    def name(self) -> str:
        return "book_home_service"

    @property
    def description(self) -> str:
        return "Book a home service with service ID, date, time slot, and contact info."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "service_id": {"type": "string", "description": "Service ID (from search_home_services)"},
                "date": {"type": "string", "description": "Service date (YYYY-MM-DD)"},
                "time_slot": {"type": "string", "description": "Time slot (morning, afternoon, evening)"},
                "address": {"type": "string", "description": "Service address"},
                "phone": {"type": "string", "description": "Contact phone"}
                # TODO: optional 参数暂时禁用
                # "special_requirements": {"type": "string", "description": "Special requirements (optional)"}
            },
            "required": ["service_id", "date", "time_slot", "address", "phone"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        booking_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=8))

        booking = {
            "booking_id": booking_id,
            "service_id": kwargs.get("service_id"),
            "date": kwargs.get("date"),
            "time_slot": kwargs.get("time_slot"),
            "address": kwargs.get("address"),
            "phone": kwargs.get("phone"),
            "special_requirements": kwargs.get("special_requirements", "None"),
            "status": "Confirmed"
        }

        self.bookings.append(booking)

        return {
            "success": True,
            "message": "Booking successful",
            "booking": booking
        }
