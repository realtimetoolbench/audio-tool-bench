"""
Parking tools (search and reservation)
"""
from typing import Dict, Any
import random
import string
from datetime import datetime

from .base import Tool
from .mock_data import PARKING_LOTS


class SearchParkingTool(Tool):
    """Parking lot search tool"""

    def __init__(self):
        self.parking_lots = PARKING_LOTS

    @property
    def name(self) -> str:
        return "search_parking"

    @property
    def description(self) -> str:
        return "Search for parking lots by city, location, price, and spot type."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name (e.g., Beijing, Shanghai, Chengdu)"}
                # TODO: optional 参数暂时禁用
                # "location": {"type": "string", "description": "Location keyword (e.g., CBD, Sanlitun, Zhongguancun)"},
                # "max_price_per_hour": {"type": "number", "description": "Maximum hourly price"},
                # "spot_type": {"type": "string", "description": "Spot type (Regular, EV Charging, Oversized, VIP)"},
                # "only_available": {"type": "boolean", "description": "Only show parking lots with available spots"},
                # "max_distance": {"type": "number", "description": "Maximum distance (km)"}
            },
            "required": ["city"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        city = kwargs.get("city")
        location = kwargs.get("location", "").lower()
        max_price_per_hour = kwargs.get("max_price_per_hour")
        spot_type = kwargs.get("spot_type")
        only_available = kwargs.get("only_available", False)
        max_distance = kwargs.get("max_distance")

        if city not in self.parking_lots:
            return {
                "success": False,
                "error": f"City not supported: {city}",
                "available_cities": list(self.parking_lots.keys())
            }

        results = self.parking_lots[city].copy()

        if location:
            results = [p for p in results if location in p["name"].lower() or location in p["address"].lower()]
        if max_price_per_hour is not None:
            results = [p for p in results if p["price_per_hour"] <= max_price_per_hour]
        if spot_type:
            results = [p for p in results if spot_type in p["spot_types"]]
        if only_available:
            results = [p for p in results if p["available_spots"] > 0]
        if max_distance is not None:
            results = [p for p in results if p["distance"] <= max_distance]

        # Add parking_id to output for easy reference
        output = f"Found {len(results)} parking lots:\n\n"
        for i, p in enumerate(results, 1):
            output += f"{i}. {p['name']} (ID: {p['parking_id']})\n"
            output += f"   Address: {p['address']}\n"
            output += f"   Price: ¥{p['price_per_hour']}/hour | Available: {p['available_spots']} spots\n\n"

        return {
            "success": True,
            "count": len(results),
            "output": output,
            "parking_lots": results
        }


class ReserveParkingSpotTool(Tool):
    """Parking spot reservation tool"""

    def __init__(self):
        self.reservations = []

    @property
    def name(self) -> str:
        return "reserve_parking_spot"

    @property
    def description(self) -> str:
        return "Reserve a parking spot with parking lot ID, time, and license plate info."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "parking_id": {"type": "string", "description": "Parking lot ID (from search_parking)"},
                "start_time": {"type": "string", "description": "Start time (YYYY-MM-DD HH:MM)"},
                "duration_hours": {"type": "number", "description": "Parking duration (hours)"},
                "license_plate": {"type": "string", "description": "License plate number"},
                # TODO: optional 参数暂时禁用
                # "spot_type": {"type": "string", "description": "Spot type (Regular, EV Charging, Oversized, VIP)", "enum": ["Regular", "EV Charging", "Oversized", "VIP"], "default": "Regular"},
                "driver_phone": {"type": "string", "description": "Driver phone number"}
            },
            "required": ["parking_id", "start_time", "duration_hours", "license_plate", "driver_phone"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        parking_id = kwargs.get("parking_id")
        start_time = kwargs.get("start_time")
        duration_hours = kwargs.get("duration_hours")
        license_plate = kwargs.get("license_plate")
        spot_type = kwargs.get("spot_type", "Regular")
        driver_phone = kwargs.get("driver_phone")

        reservation_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=10))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        spot_number = f"{random.choice(['A', 'B', 'C', 'D'])}{random.randint(100, 999)}"

        estimated_cost = duration_hours * 10

        reservation = {
            "reservation_id": reservation_id,
            "parking_id": parking_id,
            "start_time": start_time,
            "duration_hours": duration_hours,
            "license_plate": license_plate,
            "spot_type": spot_type,
            "spot_number": spot_number,
            "driver_phone": driver_phone,
            "estimated_cost": estimated_cost,
            "status": "Reserved",
            "reservation_time": timestamp
        }

        self.reservations.append(reservation)

        return {
            "success": True,
            "message": "Reservation successful",
            "reservation": reservation
        }
