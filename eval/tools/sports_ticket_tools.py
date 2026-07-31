"""
Sports event ticket booking tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import SPORTS_EVENTS


def _find_event_by_id(event_id: str):
    """Find event by event_id across all cities"""
    for city_events in SPORTS_EVENTS.values():
        for event in city_events:
            if event.get("event_id") == event_id:
                return event
    return None


class SportsEventSearchTool(Tool):
    """Sports event search tool"""

    def __init__(self):
        self.events = SPORTS_EVENTS

    @property
    def name(self) -> str:
        return "search_sports_events"

    @property
    def description(self) -> str:
        return "Search for sports events including basketball, football, tennis, and marathons."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
                # TODO: optional 参数暂时禁用
                # "sport_type": {"type": "string", "description": "Sport type (Basketball, Football, Tennis, etc.)"},
                # "team": {"type": "string", "description": "Team name (home or away team)"},
                # "venue": {"type": "string", "description": "Venue name (optional)"},
                # "date": {"type": "string", "description": "Date (e.g., '2026-03-06')"},
                # "max_price": {"type": "number", "description": "Maximum ticket price"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, sport_type: str = None, team: str = None,
                venue: str = None, date: str = None, max_price: int = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            results = self.events.get(city, []).copy()

            if not results:
                output = f"No sports events found in {city}."
                return {
                    "success": True,
                    "output": output,
                    "raw_output": [],
                    "error": None,
                    "latency_ms": (time.time() - start_time) * 1000
                }

            if sport_type:
                results = [e for e in results if sport_type.lower() in e["sport_type"].lower()]
            if team:
                results = [e for e in results if (e["home_team"] and team.lower() in e["home_team"].lower()) or
                          (e["away_team"] and team.lower() in e["away_team"].lower())]
            if venue:
                results = [e for e in results if venue.lower() in e["venue"].lower()]
            if date:
                results = [e for e in results if date in e["date"]]
            if max_price:
                results = [e for e in results if int(e["price_range"].split("-")[0]) <= max_price]

            if not results:
                output = f"No sports events found in {city} matching criteria."
            else:
                output = f"Found {len(results)} sports events in {city}:\n\n"
                for i, e in enumerate(results, 1):
                    output += f"{i}. {e['name']} (ID: {e['event_id']})\n"
                    output += f"   Sport: {e['sport_type']}\n"
                    output += f"   Venue: {e['venue']}\n"
                    output += f"   Date/Time: {e['date']} {e['time']}\n"
                    if e['home_team'] and e['away_team']:
                        output += f"   Match: {e['home_team']} vs {e['away_team']}\n"
                    output += f"   Price: ¥{e['price_range']}\n"
                    output += f"   Available zones: {', '.join(e['available_zones'])}\n"
                    output += f"   Rating: {e['rating']}/10.0\n\n"

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


class BookSportsTicketTool(Tool):
    """Sports event ticket booking tool"""

    def __init__(self):
        self.bookings = []
        self.booking_counter = 80001

    @property
    def name(self) -> str:
        return "book_sports_ticket"

    @property
    def description(self) -> str:
        return "Book tickets for sports events."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "event_id": {"type": "string", "description": "Event ID from search results (e.g., 'evt_bj_001')"},
                "seat_zone": {"type": "string", "description": "Seat zone (VIP, Stand A, Home Stand, etc.)"},
                "ticket_count": {"type": "integer", "description": "Number of tickets"},
                "buyer_name": {"type": "string", "description": "Buyer name"},
                "phone": {"type": "string", "description": "Contact phone number"},
                "id_number": {"type": "string", "description": "ID card number (required for real-name registration)"}
            },
            "required": ["event_id", "seat_zone", "ticket_count", "buyer_name", "phone", "id_number"]
        }

    def execute(self, event_id: str, seat_zone: str,
                ticket_count: int, buyer_name: str, phone: str, id_number: str, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            # Look up event by ID
            event = _find_event_by_id(event_id)
            if not event:
                return {
                    "success": False,
                    "output": f"Event not found: {event_id}. Please search for events first.",
                    "raw_output": None,
                    "error": f"Invalid event_id: {event_id}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            event_name = event["name"]
            venue = event["venue"]
            date = event["date"]

            booking_id = f"SP{self.booking_counter}"
            self.booking_counter += 1

            # Generate seat numbers
            if "VIP" in seat_zone:
                seats = [f"VIP Row {i+1} Seat {j+5}" for i in range(ticket_count) for j in range(1)]
            elif "Stand" in seat_zone:
                seats = [f"{seat_zone} Row {i+10} Seat {j+20}" for i in range(ticket_count) for j in range(1)]
            else:
                seats = [f"{seat_zone} Row {i+15} Seat {j+25}" for i in range(ticket_count) for j in range(1)]

            # Calculate price
            price_map = {
                "VIP": 1280,
                "Stand A": 680,
                "Stand B": 380,
                "Stand C": 180,
                "Home Stand": 480,
                "Away Stand": 380,
                "Neutral Stand": 280,
                "Regular Stand": 280,
                "Center Court": 2880,
                "Court 1": 1280,
                "Court 2": 680,
            }

            ticket_price = price_map.get(seat_zone, 380)
            total_price = ticket_price * ticket_count

            booking = {
                "booking_id": booking_id,
                "event_id": event_id,
                "event_name": event_name,
                "venue": venue,
                "date": date,
                "seat_zone": seat_zone,
                "ticket_count": ticket_count,
                "seats": seats,
                "buyer_name": buyer_name,
                "phone": phone,
                "id_number": id_number,
                "total_price": total_price,
                "status": "confirmed"
            }
            self.bookings.append(booking)

            output = f"Sports ticket booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Event ID: {event_id}\n"
            output += f"Event: {event_name}\n"
            output += f"Venue: {venue}\n"
            output += f"Date: {date}\n"
            output += f"Zone: {seat_zone}\n"
            output += f"Seats: {', '.join(seats)}\n"
            output += f"Quantity: {ticket_count}\n"
            output += f"Buyer: {buyer_name}\n"
            output += f"Phone: {phone}\n"
            output += f"ID: {id_number[:6]}****{id_number[-4:]}\n"
            output += f"Total: ¥{total_price}\n"
            output += f"Status: Confirmed (Real-name Required)\n"

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
