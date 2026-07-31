"""
Flight booking tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import FLIGHTS


class FlightSearchTool(Tool):
    """Flight search tool"""

    def __init__(self):
        self.flights = FLIGHTS

    @property
    def name(self) -> str:
        return "search_flights"

    @property
    def description(self) -> str:
        return "Search for available flights between cities."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Departure city"},
                "destination": {"type": "string", "description": "Arrival city"},
                "cabin_class": {"type": "string", "description": "Cabin class (Economy, Business, First Class)"}
            },
            "required": ["origin", "destination"]
        }

    def execute(self, origin: str, destination: str, date: str = None, cabin_class: str = None, max_price: int = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            route = (origin, destination)
            if route not in self.flights:
                return {
                    "success": False,
                    "output": f"Sorry, no flights found from {origin} to {destination}.",
                    "raw_output": None,
                    "error": f"Route not found: {route}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            results = self.flights[route]

            if cabin_class:
                results = [f for f in results if cabin_class.lower() in f["class"].lower()]

            if max_price:
                results = [f for f in results if f["price"] <= max_price]

            if not results:
                output = f"No flights found matching criteria ({origin} -> {destination})."
            else:
                output = f"Found {len(results)} flights ({origin} -> {destination}):\n\n"
                for i, f in enumerate(results, 1):
                    output += f"{i}. {f['flight_no']} - {f['airline']} (ID: {f['flight_id']})\n"
                    output += f"   Departure: {f['departure']} -> Arrival: {f['arrival']}\n"
                    output += f"   Class: {f['class']} | Price: ¥{f['price']}\n\n"

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


class BookFlightTool(Tool):
    """Flight booking tool"""

    def __init__(self):
        self.bookings = []

    @property
    def name(self) -> str:
        return "book_flight"

    @property
    def description(self) -> str:
        return "Book a flight with specified details."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "flight_id": {"type": "string", "description": "Flight ID (from search_flights)"},
                "passenger_name": {"type": "string", "description": "Passenger name"},
                "date": {"type": "string", "description": "Flight date"}
            },
            "required": ["flight_id", "date", "passenger_name"]
        }

    def execute(self, flight_id: str, passenger_name: str = None, date: str = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            booking_id = f"FL{len(self.bookings) + 10001}"

            booking = {
                "booking_id": booking_id,
                "flight_id": flight_id,
                "passenger_name": passenger_name,
                "date": date,
                "status": "confirmed"
            }

            self.bookings.append(booking)

            output = f"Flight booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Flight ID: {flight_id}\n"
            output += f"Passenger: {passenger_name}\n"
            output += f"Date: {date}\n"
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
