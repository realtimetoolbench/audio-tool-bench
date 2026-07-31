"""
Ride-hailing tools (request, check status, cancel)
"""
from typing import Dict, Any
import random
import string
from datetime import datetime

from .base import Tool
from .mock_data import RIDE_STATUSES, CAR_TYPES


class RequestRideTool(Tool):
    """Ride request tool"""

    def __init__(self):
        self.rides = []

    @property
    def name(self) -> str:
        return "request_ride"

    @property
    def description(self) -> str:
        return "Request a ride with pickup location, destination, and car type."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "pickup_location": {"type": "string", "description": "Pickup location"},
                "dropoff_location": {"type": "string", "description": "Dropoff location"},
                "car_type": {"type": "string", "description": "Car type (economy, comfort, business, luxury)", "enum": ["economy", "comfort", "business", "luxury"]}
                # TODO: optional 参数暂时禁用
                # "passenger_count": {"type": "integer", "description": "Number of passengers (default: 1)", "default": 1},
                # "scheduled_time": {"type": "string", "description": "Scheduled time (YYYY-MM-DD HH:MM, optional for immediate rides)"},
                # "passenger_phone": {"type": "string", "description": "Passenger phone number"},
                # "special_requirements": {"type": "string", "description": "Special requirements (optional, e.g., child seat, pet)"}
            },
            "required": ["pickup_location", "dropoff_location", "car_type"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        pickup_location = kwargs.get("pickup_location")
        dropoff_location = kwargs.get("dropoff_location")
        car_type = kwargs.get("car_type")
        passenger_count = kwargs.get("passenger_count", 1)
        scheduled_time = kwargs.get("scheduled_time")
        passenger_phone = kwargs.get("passenger_phone")
        special_requirements = kwargs.get("special_requirements", "None")

        ride_id = ''.join(random.choices(string.ascii_uppercase + string.digits, k=12))
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        car_type_info = CAR_TYPES.get(car_type, {"base_price": 25, "name": "Comfort"})
        estimated_price = car_type_info["base_price"] + random.randint(10, 50)

        estimated_distance = round(random.uniform(5, 30), 1)
        estimated_duration = int(estimated_distance * 3)

        driver_names = ["Driver Wang", "Driver Li", "Driver Zhang", "Driver Liu"]

        ride = {
            "ride_id": ride_id,
            "pickup_location": pickup_location,
            "dropoff_location": dropoff_location,
            "car_type": car_type_info["name"],
            "passenger_count": passenger_count,
            "scheduled_time": scheduled_time if scheduled_time else "Immediate",
            "passenger_phone": passenger_phone,
            "special_requirements": special_requirements,
            "status": "Driver Accepted" if not scheduled_time else "Scheduled",
            "estimated_price": estimated_price,
            "estimated_distance": estimated_distance,
            "estimated_duration": estimated_duration,
            "order_time": timestamp,
            "driver_name": random.choice(driver_names),
            "driver_phone": f"138****{random.randint(1000, 9999)}",
            "car_plate": f"Beijing A{random.randint(10000, 99999)}"
        }

        self.rides.append(ride)

        return {
            "success": True,
            "message": "Ride requested successfully, driver is on the way",
            "ride": ride
        }


class CheckRideStatusTool(Tool):
    """Ride status check tool"""

    def __init__(self):
        self.ride_statuses = RIDE_STATUSES

    @property
    def name(self) -> str:
        return "check_ride_status"

    @property
    def description(self) -> str:
        return "Check ride status with ride ID."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ride_id": {"type": "string", "description": "Ride ID"}
            },
            "required": ["ride_id"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        ride_id = kwargs.get("ride_id")

        if ride_id not in self.ride_statuses:
            return {
                "success": False,
                "error": "Ride not found or invalid ride ID"
            }

        ride_status = self.ride_statuses[ride_id]

        return {
            "success": True,
            "ride_status": ride_status
        }


class CancelRideTool(Tool):
    """Ride cancellation tool"""

    def __init__(self):
        self.cancellations = []

    @property
    def name(self) -> str:
        return "cancel_ride"

    @property
    def description(self) -> str:
        return "Cancel a ride with ride ID and reason."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "ride_id": {"type": "string", "description": "Ride ID"}
                # TODO: optional 参数暂时禁用
                # "reason": {"type": "string", "description": "Cancellation reason (optional)"}
            },
            "required": ["ride_id"]
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        ride_id = kwargs.get("ride_id")
        reason = kwargs.get("reason", "Not provided")

        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        cancellation = {
            "ride_id": ride_id,
            "reason": reason,
            "cancel_time": timestamp,
            "status": "Cancelled",
            "cancellation_fee": 0
        }

        self.cancellations.append(cancellation)

        return {
            "success": True,
            "message": "Ride cancelled",
            "cancellation": cancellation
        }
