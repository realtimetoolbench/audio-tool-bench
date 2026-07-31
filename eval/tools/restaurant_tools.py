"""
Restaurant booking tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import RESTAURANTS


def _find_restaurant_by_id(restaurant_id: str):
    """Find restaurant by restaurant_id across all cities"""
    for city_restaurants in RESTAURANTS.values():
        for restaurant in city_restaurants:
            if restaurant.get("restaurant_id") == restaurant_id:
                return restaurant
    return None


class RestaurantSearchTool(Tool):
    """Restaurant search tool"""

    def __init__(self):
        self.restaurants = RESTAURANTS

    @property
    def name(self) -> str:
        return "search_restaurants"

    @property
    def description(self) -> str:
        return "Search for restaurants based on location, cuisine type, and other preferences."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (e.g., Beijing, Shanghai)"},
                "cuisine": {"type": "string", "description": "Type of cuisine (e.g., Sichuan, Beijing, Shanghainese)"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, cuisine: str = None, location: str = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()

        try:
            if city not in self.restaurants:
                return {
                    "success": False,
                    "output": f"Sorry, no restaurant information available for {city}.",
                    "raw_output": None,
                    "error": f"City not found: {city}",
                    "latency_ms": (time.time() - start_time) * 1000
                }

            results = self.restaurants[city].copy()

            if cuisine:
                results = [r for r in results if cuisine.lower() in r["cuisine"].lower()]

            if location:
                results = [r for r in results if location.lower() in r["location"].lower()]

            if not results:
                output = f"No restaurants found in {city} matching criteria."
            else:
                output = f"Found {len(results)} restaurants in {city}:\n\n"
                for i, r in enumerate(results, 1):
                    output += f"{i}. {r['name']} (ID: {r['restaurant_id']})\n"
                    output += f"   Cuisine: {r['cuisine']}\n"
                    output += f"   Location: {r['location']}\n"
                    output += f"   Rating: {r['rating']}/5.0\n\n"

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


class MakeReservationTool(Tool):
    """Restaurant reservation tool"""

    def __init__(self):
        self.bookings = []
        self.booking_counter = 1001

    @property
    def name(self) -> str:
        return "book_restaurant"

    @property
    def description(self) -> str:
        return "Make a restaurant reservation with specified details."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "restaurant_id": {"type": "string", "description": "Restaurant ID from search results (e.g., 'rst_bj_001')"},
                "date": {"type": "string", "description": "Reservation date (e.g., '2026-03-01')"},
                "time": {"type": "string", "description": "Reservation time (e.g., '19:00')"},
                "party_size": {"type": "integer", "description": "Number of people"},
                "contact_name": {"type": "string", "description": "Contact person name"},
                "phone": {"type": "string", "description": "Contact phone number"}
            },
            "required": ["restaurant_id", "date", "time", "party_size", "contact_name", "phone"]
        }

    def execute(self, restaurant_id: str, date: str, time: str, party_size: int, contact_name: str, phone: str, **kwargs) -> Dict[str, Any]:
        reservation_time = time
        import time as time_module
        start_time = time_module.time()

        try:
            # Look up restaurant by ID
            restaurant = _find_restaurant_by_id(restaurant_id)
            if not restaurant:
                return {
                    "success": False,
                    "output": f"Restaurant not found: {restaurant_id}. Please search for restaurants first.",
                    "raw_output": None,
                    "error": f"Invalid restaurant_id: {restaurant_id}",
                    "latency_ms": (time_module.time() - start_time) * 1000
                }

            restaurant_name = restaurant["name"]

            booking_id = f"BK{self.booking_counter}"
            self.booking_counter += 1

            booking = {
                "booking_id": booking_id,
                "restaurant_id": restaurant_id,
                "restaurant_name": restaurant_name,
                "date": date,
                "time": reservation_time,
                "party_size": party_size,
                "contact_name": contact_name,
                "phone": phone,
                "status": "confirmed"
            }

            self.bookings.append(booking)

            output = f"Reservation successful!\n\n"
            output += f"Booking ID: {booking_id}\n"
            output += f"Restaurant ID: {restaurant_id}\n"
            output += f"Restaurant: {restaurant_name}\n"
            output += f"Date: {date}\n"
            output += f"Time: {reservation_time}\n"
            output += f"Party size: {party_size}\n"
            output += f"Contact: {contact_name} ({phone})\n"
            output += f"Status: Confirmed\n"

            return {
                "success": True,
                "output": output,
                "raw_output": booking,
                "error": None,
                "latency_ms": (time_module.time() - start_time) * 1000
            }

        except Exception as e:
            import time as time_module
            return {
                "success": False,
                "output": f"Reservation failed: {str(e)}",
                "raw_output": None,
                "error": str(e),
                "latency_ms": (time_module.time() - start_time) * 1000
            }
