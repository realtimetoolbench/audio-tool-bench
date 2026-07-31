"""
Attraction ticket tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import ATTRACTIONS


class AttractionSearchTool(Tool):
    """Attraction search tool"""

    def __init__(self):
        self.attractions = ATTRACTIONS

    @property
    def name(self) -> str:
        return "search_attractions"

    @property
    def description(self) -> str:
        return "Search for tourist attractions in a city."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
                # TODO: optional 参数暂时禁用
                # "attraction_type": {"type": "string", "description": "Type of attraction (Historical, Garden, Theme Park, Sightseeing, Zoo, Modern)"},
                # "max_price": {"type": "number", "description": "Maximum ticket price"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, attraction_type: str = None, max_price: int = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            results = self.attractions.get(city, []).copy()

            if attraction_type:
                results = [a for a in results if attraction_type.lower() in a["type"].lower()]

            if max_price is not None:
                results = [a for a in results if a["price"] <= max_price]

            if not results:
                output = f"No attractions found in {city} matching criteria."
            else:
                output = f"Found {len(results)} attractions in {city}:\n\n"
                for i, a in enumerate(results, 1):
                    output += f"{i}. {a['name']} (ID: {a['attraction_id']})\n"
                    output += f"   Type: {a['type']}\n"
                    output += f"   Rating: {a['rating']}/5.0\n"
                    price_str = "Free" if a['price'] == 0 else f"¥{a['price']}"
                    output += f"   Ticket: {price_str}\n"
                    output += f"   Hours: {a['opening_hours']}\n"
                    output += f"   Location: {a['location']}\n\n"

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


class BookAttractionTicketTool(Tool):
    """Attraction ticket booking tool"""

    def __init__(self):
        self.bookings = []
        self.booking_counter = 50001

    @property
    def name(self) -> str:
        return "book_attraction_ticket"

    @property
    def description(self) -> str:
        return "Book attraction tickets with specified date and time slot."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "attraction_id": {"type": "string", "description": "Attraction ID (from search_attractions)"},
                "date": {"type": "string", "description": "Visit date (e.g., '2026-03-01')"},
                "time_slot": {"type": "string", "description": "Time slot (e.g., 'morning', 'afternoon', '09:00-12:00')"},
                "visitor_name": {"type": "string", "description": "Visitor name"},
                "ticket_count": {"type": "integer", "description": "Number of tickets"}
                # TODO: optional 参数暂时禁用
                # "id_number": {"type": "string", "description": "ID card number (optional)"}
            },
            "required": ["attraction_id", "date", "time_slot", "visitor_name", "ticket_count"]
        }

    def execute(self, attraction_id: str, date: str, time_slot: str,
                visitor_name: str, ticket_count: int, id_number: str = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            booking_id = f"AT{self.booking_counter}"
            self.booking_counter += 1

            ticket_numbers = [f"{booking_id}-{i+1:02d}" for i in range(ticket_count)]

            booking = {
                "booking_id": booking_id,
                "attraction_id": attraction_id,
                "date": date,
                "time_slot": time_slot,
                "visitor_name": visitor_name,
                "ticket_count": ticket_count,
                "ticket_numbers": ticket_numbers,
                "status": "confirmed"
            }
            self.bookings.append(booking)

            output = f"Attraction ticket booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Attraction ID: {attraction_id}\n"
            output += f"Date: {date}\n"
            output += f"Time slot: {time_slot}\n"
            output += f"Visitor: {visitor_name}\n"
            output += f"Tickets: {ticket_count}\n"
            output += f"Ticket numbers: {', '.join(ticket_numbers)}\n"
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
