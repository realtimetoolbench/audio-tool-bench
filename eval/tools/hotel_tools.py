"""
Hotel booking tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import HOTELS


class HotelSearchTool(Tool):
    """Hotel search tool"""

    def __init__(self):
        self.hotels = HOTELS

    @property
    def name(self) -> str:
        return "search_hotels"

    @property
    def description(self) -> str:
        return "Search for hotels in a city."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "checkin_date": {"type": "string", "description": "Check-in date (e.g., '2026-03-15')"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, checkin_date: str = None, nights: int = 1, location: str = None, min_stars: int = None, max_price: int = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            if city not in self.hotels:
                return {
                    "success": False,
                    "output": f"Sorry, no hotel information available for {city}.",
                    "raw_output": None,
                    "error": f"City not found: {city}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            results = self.hotels[city].copy()

            if location:
                results = [h for h in results if location.lower() in h["location"].lower()]

            if min_stars:
                results = [h for h in results if h["stars"] >= min_stars]

            if max_price:
                results = [h for h in results if h["price"] <= max_price]

            if not results:
                output = f"No hotels found in {city} matching criteria."
            else:
                output = f"Found {len(results)} hotels in {city}:\n\n"
                for i, h in enumerate(results, 1):
                    output += f"{i}. {h['name']} (ID: {h['hotel_id']})\n"
                    output += f"   Location: {h['location']} | {h['stars']} stars\n"
                    output += f"   Price: ¥{h['price']}/night | Rating: {h['rating']}/5.0\n\n"

            return {
                "success": True,
                "output": output,
                "raw_output": results,
                "error": None,
                "latency_ms": (time.time() - start_time) * 1000
            }

        except Exception as e:
            return {
                "success": False,
                "output": f"Search failed: {str(e)}",
                "raw_output": None,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000
            }


class BookHotelTool(Tool):
    """Hotel booking tool"""

    def __init__(self):
        self.bookings = []

    @property
    def name(self) -> str:
        return "book_hotel"

    @property
    def description(self) -> str:
        return "Book a hotel room."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "hotel_id": {"type": "string", "description": "Hotel ID (from search_hotels)"},
                "checkin_date": {"type": "string", "description": "Check-in date"},
                "nights": {"type": "integer", "description": "Number of nights"},
                "guest_name": {"type": "string", "description": "Guest name"}
            },
            "required": ["hotel_id", "checkin_date", "nights", "guest_name"]
        }

    def execute(self, hotel_id: str, checkin_date: str, nights: int, guest_name: str, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            booking_id = f"HT{len(self.bookings) + 20001}"

            booking = {
                "booking_id": booking_id,
                "hotel_id": hotel_id,
                "checkin_date": checkin_date,
                "nights": nights,
                "guest_name": guest_name,
                "status": "confirmed"
            }

            self.bookings.append(booking)

            output = f"Hotel booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Hotel ID: {hotel_id}\n"
            output += f"Check-in: {checkin_date}\n"
            output += f"Nights: {nights}\n"
            output += f"Guest: {guest_name}\n"
            output += f"Status: Confirmed\n"

            return {
                "success": True,
                "output": output,
                "raw_output": booking,
                "error": None,
                "latency_ms": (time.time() - start_time) * 1000
            }

        except Exception as e:
            return {
                "success": False,
                "output": f"Booking failed: {str(e)}",
                "raw_output": None,
                "error": str(e),
                "latency_ms": (time.time() - start_time) * 1000
            }
