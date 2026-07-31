"""
Show ticket booking tools (concerts, theater, performances)
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import SHOWS


def _find_show_by_id(show_id: str):
    """Find show by show_id across all cities"""
    for city_shows in SHOWS.values():
        for show in city_shows:
            if show.get("show_id") == show_id:
                return show
    return None


class ShowSearchTool(Tool):
    """Show search tool"""

    def __init__(self):
        self.shows = SHOWS

    @property
    def name(self) -> str:
        return "search_shows"

    @property
    def description(self) -> str:
        return "Search for shows including concerts, theater performances, and music events."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "show_type": {"type": "string", "description": "Show type (Concert, Theater, etc.)"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, show_name: str = None, show_type: str = None,
                venue: str = None, date: str = None, max_price: int = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            results = self.shows.get(city, []).copy()

            if not results:
                output = f"No shows found in {city}."
                return {
                    "success": True,
                    "output": output,
                    "raw_output": [],
                    "error": None,
                    "latency_ms": (time.time() - start_time) * 1000
                }

            if show_name:
                results = [s for s in results if show_name.lower() in s["name"].lower()]
            if show_type:
                results = [s for s in results if show_type.lower() in s["type"].lower()]
            if venue:
                results = [s for s in results if venue.lower() in s["venue"].lower()]
            if date:
                results = [s for s in results if date in s["date"]]
            if max_price:
                results = [s for s in results if int(s["price_range"].split("-")[0]) <= max_price]

            if not results:
                output = f"No shows found in {city} matching criteria."
            else:
                output = f"Found {len(results)} shows in {city}:\n\n"
                for i, s in enumerate(results, 1):
                    output += f"{i}. {s['name']} (ID: {s['show_id']})\n"
                    output += f"   Type: {s['type']}\n"
                    output += f"   Venue: {s['venue']}\n"
                    output += f"   Date/Time: {s['date']} {s['time']}\n"
                    output += f"   Duration: {s['duration']} min\n"
                    output += f"   Price: ¥{s['price_range']}\n"
                    output += f"   Available zones: {', '.join(s['available_zones'])}\n"
                    output += f"   Rating: {s['rating']}/10.0\n\n"

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


class BookShowTicketTool(Tool):
    """Show ticket booking tool"""

    def __init__(self):
        self.bookings = []
        self.booking_counter = 70001

    @property
    def name(self) -> str:
        return "book_show_ticket"

    @property
    def description(self) -> str:
        return "Book tickets for shows including concerts, theater, and music events."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "show_id": {"type": "string", "description": "Show ID from search results (e.g., 'show_bj_001')"},
                "seat_zone": {"type": "string", "description": "Seat zone (Floor, Stand A, Orchestra, VIP, etc.)"},
                "ticket_count": {"type": "integer", "description": "Number of tickets"},
                "buyer_name": {"type": "string", "description": "Buyer name"},
                "phone": {"type": "string", "description": "Contact phone number"}
            },
            "required": ["show_id", "seat_zone", "ticket_count", "buyer_name", "phone"]
        }

    def execute(self, show_id: str, seat_zone: str,
                ticket_count: int, buyer_name: str, phone: str, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            # Look up show by ID
            show = _find_show_by_id(show_id)
            if not show:
                return {
                    "success": False,
                    "output": f"Show not found: {show_id}. Please search for shows first.",
                    "raw_output": None,
                    "error": f"Invalid show_id: {show_id}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            show_name = show["name"]
            venue = show["venue"]
            date = show["date"]

            booking_id = f"SH{self.booking_counter}"
            self.booking_counter += 1

            # Generate seat numbers
            if "Floor" in seat_zone:
                seats = [f"Floor Row {i+1} Seat {j+10}" for i in range(ticket_count) for j in range(1)]
            elif "Stand" in seat_zone:
                seats = [f"{seat_zone} Row {i+5} Seat {j+15}" for i in range(ticket_count) for j in range(1)]
            elif "Orchestra" in seat_zone:
                seats = [f"Orchestra Row {i+8} Seat {j+12}" for i in range(ticket_count) for j in range(1)]
            else:
                seats = [f"{seat_zone} Row {i+3} Seat {j+8}" for i in range(ticket_count) for j in range(1)]

            # Calculate price
            price_map = {
                "Floor": 1580,
                "Stand A": 880,
                "Stand B": 580,
                "Stand C": 380,
                "Orchestra": 680,
                "VIP": 880,
                "First Class": 480,
                "Second Class": 280,
                "First Floor": 580,
                "Second Floor": 380,
            }

            ticket_price = price_map.get(seat_zone, 480)
            total_price = ticket_price * ticket_count

            booking = {
                "booking_id": booking_id,
                "show_id": show_id,
                "show_name": show_name,
                "venue": venue,
                "date": date,
                "seat_zone": seat_zone,
                "ticket_count": ticket_count,
                "seats": seats,
                "buyer_name": buyer_name,
                "phone": phone,
                "total_price": total_price,
                "status": "confirmed"
            }
            self.bookings.append(booking)

            output = f"Show ticket booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Show ID: {show_id}\n"
            output += f"Show: {show_name}\n"
            output += f"Venue: {venue}\n"
            output += f"Date: {date}\n"
            output += f"Zone: {seat_zone}\n"
            output += f"Seats: {', '.join(seats)}\n"
            output += f"Quantity: {ticket_count}\n"
            output += f"Buyer: {buyer_name}\n"
            output += f"Phone: {phone}\n"
            output += f"Total: ¥{total_price}\n"
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
