"""
Car rental tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import RENTAL_CARS


class CarRentalTool(Tool):
    """Car rental search tool"""

    def __init__(self):
        self.cars = RENTAL_CARS

    @property
    def name(self) -> str:
        return "search_cars"

    @property
    def description(self) -> str:
        return "Search for available rental cars in a city."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"},
                "car_type": {"type": "string", "description": "Car type (economy, comfort, luxury, business)"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, car_type: str = None, pickup_date: str = None, days: int = None, max_price: int = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            if city not in self.cars:
                return {
                    "success": False,
                    "output": f"Sorry, no rental cars available in {city}.",
                    "raw_output": None,
                    "error": f"City not found: {city}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            results = self.cars[city].copy()

            if car_type:
                results = [c for c in results if car_type.lower() in c["type"].lower()]

            if max_price:
                results = [c for c in results if c["price_per_day"] <= max_price]

            if not results:
                return {
                    "success": True,
                    "output": f"No cars found in {city} matching criteria.",
                    "raw_output": [],
                    "error": None,
                    "latency_ms": (time.time() - start_time) * 1000
                }

            output = f"Found {len(results)} rental cars in {city}:\n\n"
            for i, car in enumerate(results, 1):
                output += f"{i}. {car['model']} (ID: {car['car_id']})\n"
                output += f"   Type: {car['type']} | Seats: {car['seats']}\n"
                output += f"   Price: ¥{car['price_per_day']}/day | Insurance: ¥{car['insurance']}/day\n"
                output += f"   Rating: {car['rating']}/5.0\n\n"

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


class BookCarTool(Tool):
    """Car rental booking tool"""

    def __init__(self):
        self.bookings = []
        self.booking_counter = 30001

    @property
    def name(self) -> str:
        return "book_car"

    @property
    def description(self) -> str:
        return "Book a rental car with specified details."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "car_id": {"type": "string", "description": "Car ID (from search_cars)"},
                "pickup_date": {"type": "string", "description": "Pickup date"},
                "days": {"type": "integer", "description": "Number of rental days"},
                "renter_name": {"type": "string", "description": "Renter name"}
                # TODO: optional 参数暂时禁用
                # "with_insurance": {"type": "boolean", "description": "Whether to include insurance", "default": True}
            },
            "required": ["car_id", "pickup_date", "days", "renter_name"]
        }

    def execute(self, car_id: str, pickup_date: str, days: int, renter_name: str, with_insurance: bool = True, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            booking_id = f"CR{self.booking_counter}"
            self.booking_counter += 1

            booking = {
                "booking_id": booking_id,
                "car_id": car_id,
                "pickup_date": pickup_date,
                "days": days,
                "renter_name": renter_name,
                "with_insurance": with_insurance,
                "status": "confirmed"
            }
            self.bookings.append(booking)

            output = f"Car rental booking successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Car ID: {car_id}\n"
            output += f"Pickup: {pickup_date}\n"
            output += f"Days: {days}\n"
            output += f"Renter: {renter_name}\n"
            output += f"Insurance: {'Included' if with_insurance else 'Not included'}\n"
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
