"""
Shopping and retail tools
"""
from typing import Dict, Any
import random
import string
from datetime import datetime

from .base import Tool
from .mock_data import PRODUCTS, SHOPPING_ORDERS


def _find_product(product_id: str):
    for product in PRODUCTS:
        if product["product_id"] == product_id:
            return product
    return None


class ProductSearchTool(Tool):
    @property
    def name(self) -> str:
        return "search_products"

    @property
    def description(self) -> str:
        return "Search retail products by keyword, category, brand, and price."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "keyword": {"type": "string", "description": "Product keyword"},
                "category": {"type": "string", "description": "Product category"},
                "max_price": {"type": "number", "description": "Maximum price"},
            },
            "required": [],
        }

    def execute(self, **kwargs) -> Dict[str, Any]:
        keyword = (kwargs.get("keyword") or "").lower()
        category = kwargs.get("category")
        max_price = kwargs.get("max_price")
        results = PRODUCTS.copy()
        if keyword:
            results = [p for p in results if keyword in p["name"].lower() or keyword in p["brand"].lower()]
        if category:
            results = [p for p in results if p["category"].lower() == category.lower()]
        if max_price is not None:
            results = [p for p in results if p["price"] <= max_price]
        return {"success": True, "count": len(results), "products": results}


class ProductDetailsTool(Tool):
    @property
    def name(self) -> str:
        return "get_product_details"

    @property
    def description(self) -> str:
        return "Get product details by product ID."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID from search_products"}
            },
            "required": ["product_id"],
        }

    def execute(self, product_id: str, **kwargs) -> Dict[str, Any]:
        product = _find_product(product_id)
        if not product:
            return {"success": False, "error": f"Product not found: {product_id}"}
        return {"success": True, "product": product}


class PlaceRetailOrderTool(Tool):
    def __init__(self):
        self.orders = {}

    @property
    def name(self) -> str:
        return "place_order"

    @property
    def description(self) -> str:
        return "Place a retail order for a product."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID from search_products"},
                "quantity": {"type": "integer", "description": "Quantity to order"},
                "shipping_address": {"type": "string", "description": "Shipping address"},
                "recipient_name": {"type": "string", "description": "Recipient name"},
                "phone": {"type": "string", "description": "Recipient phone number"},
            },
            "required": ["product_id", "quantity", "shipping_address", "recipient_name", "phone"],
        }

    def execute(self, product_id: str, quantity: int, shipping_address: str, recipient_name: str, phone: str, **kwargs) -> Dict[str, Any]:
        product = _find_product(product_id)
        if not product:
            return {"success": False, "error": f"Product not found: {product_id}"}
        order_id = "ord_" + "".join(random.choices(string.digits, k=6))
        order = {
            "order_id": order_id,
            "product_id": product_id,
            "product_name": product["name"],
            "quantity": quantity,
            "total_price": round(product["price"] * quantity, 2),
            "shipping_address": shipping_address,
            "recipient_name": recipient_name,
            "phone": phone,
            "status": "Placed",
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        }
        self.orders[order_id] = order
        return {"success": True, "message": "Order placed", "order": order}


class TrackRetailOrderTool(Tool):
    @property
    def name(self) -> str:
        return "track_order"

    @property
    def description(self) -> str:
        return "Track a retail order by order ID."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "order_id": {"type": "string", "description": "Retail order ID"}
            },
            "required": ["order_id"],
        }

    def execute(self, order_id: str, **kwargs) -> Dict[str, Any]:
        order = SHOPPING_ORDERS.get(order_id)
        if not order:
            return {"success": False, "error": f"Order not found: {order_id}"}
        return {"success": True, "order": order}


class CheckReturnPolicyTool(Tool):
    @property
    def name(self) -> str:
        return "check_return_policy"

    @property
    def description(self) -> str:
        return "Check return policy for a product."

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "product_id": {"type": "string", "description": "Product ID"}
            },
            "required": ["product_id"],
        }

    def execute(self, product_id: str, **kwargs) -> Dict[str, Any]:
        product = _find_product(product_id)
        if not product:
            return {"success": False, "error": f"Product not found: {product_id}"}
        return {
            "success": True,
            "product_id": product_id,
            "product_name": product["name"],
            "return_policy": product["return_policy"],
        }
