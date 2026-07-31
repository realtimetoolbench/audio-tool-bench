"""
Food delivery tools
"""
from typing import Dict, Any
import time

from .base import Tool
from .mock_data import DELIVERY_RESTAURANTS


class DeliveryRestaurantSearchTool(Tool):
    """Food delivery restaurant search tool"""

    def __init__(self):
        self.restaurants = DELIVERY_RESTAURANTS

    @property
    def name(self) -> str:
        return "search_restaurants_delivery"

    @property
    def description(self) -> str:
        return "Search for restaurants that offer food delivery service."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "city": {"type": "string", "description": "City name"}
                # TODO: optional 参数暂时禁用
                # "cuisine": {"type": "string", "description": "Cuisine type (Fast Food, Hotpot, Sichuan, etc.)"},
                # "max_delivery_time": {"type": "integer", "description": "Maximum delivery time in minutes"},
                # "max_delivery_fee": {"type": "number", "description": "Maximum delivery fee"}
            },
            "required": ["city"]
        }

    def execute(self, city: str, cuisine: str = None, max_delivery_time: int = None, max_delivery_fee: int = None, **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            results = self.restaurants.get(city, []).copy()

            if cuisine:
                results = [r for r in results if cuisine.lower() in r["cuisine"].lower()]
            if max_delivery_time:
                results = [r for r in results if r["delivery_time"] <= max_delivery_time]
            if max_delivery_fee:
                results = [r for r in results if r["delivery_fee"] <= max_delivery_fee]

            output = f"Found {len(results)} delivery restaurants in {city}:\n\n" if results else f"No delivery restaurants found in {city}."
            for i, r in enumerate(results, 1):
                output += f"{i}. {r['name']} (ID: {r['delivery_id']})\n"
                output += f"   Cuisine: {r['cuisine']} | Rating: {r['rating']}/5.0\n"
                output += f"   Delivery time: {r['delivery_time']} min | Delivery fee: ¥{r['delivery_fee']}\n"
                output += f"   Min order: ¥{r['min_order']}\n\n"

            return {"success": True, "output": output, "raw_output": results, "error": None,
                    "latency_ms": (time.time() - start_time) * 1000}
        except Exception as e:
            return {"success": False, "output": f"Search failed: {str(e)}", "raw_output": None,
                    "error": str(e), "latency_ms": (time.time() - start_time) * 1000}


class PlaceFoodOrderTool(Tool):
    """Food order placement tool"""

    def __init__(self):
        self.orders = []
        self.order_counter = 90001

    @property
    def name(self) -> str:
        return "place_food_order"

    @property
    def description(self) -> str:
        return "Place a food delivery order."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "delivery_id": {"type": "string", "description": "Restaurant delivery ID (from search_restaurants_delivery)"},
                "items": {"type": "string", "description": "Order items (comma-separated)"},
                "delivery_address": {"type": "string", "description": "Delivery address"},
                "phone": {"type": "string", "description": "Contact phone"}
                # TODO: optional 参数暂时禁用
                # "note": {"type": "string", "description": "Special instructions (optional)"}
            },
            "required": ["delivery_id", "items", "delivery_address", "phone"]
        }

    def execute(self, delivery_id: str, items: str, delivery_address: str, phone: str = "", note: str = "", **kwargs) -> Dict[str, Any]:
        start_time = time.time()
        try:
            order_id = f"FD{self.order_counter}"
            self.order_counter += 1

            item_list = [item.strip() for item in items.split(",")]
            total_price = len(item_list) * 25 + 5

            order = {
                "order_id": order_id, "delivery_id": delivery_id,
                "items": item_list, "delivery_address": delivery_address,
                "phone": phone, "note": note, "total_price": total_price,
                "status": "Placed", "estimated_time": 35
            }
            self.orders.append(order)

            output = f"Food order placed!\n\nOrder ID: {order_id}\nRestaurant ID: {delivery_id}\n"
            output += f"Items: {', '.join(item_list)}\nDelivery address: {delivery_address}\n"
            output += f"Phone: {phone}\n"
            if note:
                output += f"Note: {note}\n"
            output += f"Total: ¥{total_price}\nEstimated delivery: {order['estimated_time']} min\nStatus: {order['status']}\n"

            return {"success": True, "output": output, "raw_output": order, "error": None,
                    "latency_ms": (time.time() - start_time) * 1000}
        except Exception as e:
            return {"success": False, "output": f"Order failed: {str(e)}", "raw_output": None,
                    "error": str(e), "latency_ms": (time.time() - start_time) * 1000}
