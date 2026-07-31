"""
Train ticket booking tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import TRAINS


class TrainSearchTool(Tool):
    """Train ticket search tool"""

    def __init__(self):
        self.trains = TRAINS

    @property
    def name(self) -> str:
        return "search_trains"

    @property
    def description(self) -> str:
        return "Search for available train tickets between cities."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "origin": {"type": "string", "description": "Departure city"},
                "destination": {"type": "string", "description": "Arrival city"}
                # TODO: optional 参数暂时禁用
                # "date": {"type": "string", "description": "Travel date (e.g., '2026-03-02')"},
                # "train_type": {"type": "string", "description": "Train type (High-speed, Express, all)"},
                # "seat_class": {"type": "string", "description": "Seat class (second class, first class)"}
            },
            "required": ["origin", "destination"]
        }

    def execute(self, origin: str, destination: str, date: str = None, train_type: str = None, seat_class: str = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            route = (origin, destination)
            if route not in self.trains:
                return {
                    "success": False,
                    "output": f"Sorry, no trains found from {origin} to {destination}.",
                    "raw_output": None,
                    "error": f"Route not found: {origin} -> {destination}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            results = self.trains[route].copy()

            if train_type and train_type.lower() != "all":
                results = [t for t in results if train_type.lower() in t["type"].lower()]

            if not results:
                return {
                    "success": True,
                    "output": f"No trains found matching criteria.",
                    "raw_output": [],
                    "error": None,
                    "latency_ms": (time.time() - start_time) * 1000
                }

            output = f"Found {len(results)} trains ({origin} -> {destination}):\n\n"
            for i, train in enumerate(results, 1):
                output += f"{i}. {train['train_no']} - {train['type']} (ID: {train['train_id']})\n"
                output += f"   Departure: {train['departure']} -> Arrival: {train['arrival']}\n"
                output += f"   Duration: {train['duration']}\n"
                output += f"   Second class: ¥{train['price_second']} | First class: ¥{train['price_first']}\n"
                output += f"   {'Available' if train['seats_available'] else 'Sold out'}\n\n"

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


class BookTrainTool(Tool):
    """Train ticket booking tool"""

    def __init__(self):
        self.bookings = []
        self.booking_counter = 40001

    @property
    def name(self) -> str:
        return "book_train"

    @property
    def description(self) -> str:
        return "Book a train ticket with specified details."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "train_id": {"type": "string", "description": "Train ID (from search_trains)"},
                "date": {"type": "string", "description": "Travel date"},
                "passenger_name": {"type": "string", "description": "Passenger name"},
                "seat_class": {"type": "string", "description": "Seat class (second class, first class)"}
                # TODO: optional 参数暂时禁用
                # "id_number": {"type": "string", "description": "ID card number (optional)"}
            },
            "required": ["train_id", "date", "passenger_name", "seat_class"]
        }

    def execute(self, train_id: str, date: str, passenger_name: str, seat_class: str, id_number: str = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            booking_id = f"TR{self.booking_counter}"
            self.booking_counter += 1

            seat_no = f"{booking_id[-2:]}{'A' if 'first' in seat_class.lower() else 'F'}"

            booking = {
                "booking_id": booking_id,
                "train_id": train_id,
                "date": date,
                "passenger_name": passenger_name,
                "seat_class": seat_class,
                "seat_no": seat_no,
                "status": "confirmed"
            }
            self.bookings.append(booking)

            output = f"Train ticket booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Train ID: {train_id}\n"
            output += f"Date: {date}\n"
            output += f"Passenger: {passenger_name}\n"
            output += f"Seat: {seat_class} {seat_no}\n"
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
