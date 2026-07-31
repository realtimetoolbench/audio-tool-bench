#!/usr/bin/env python3
"""
Tool Graph - defines dependencies among tools.

Edge types:
- resource: B requires an ID returned by A (e.g. book_hotel needs the hotel_id from search_hotels)
- temporal: B depends on A's context but does not use its return value directly
  (e.g. searching restaurants based on the chosen hotel's location)
- alternative: A and B are functionally similar and interchangeable (e.g. flights vs. trains)
"""

from typing import List, Dict, Optional, Set, Tuple
from dataclasses import dataclass
from enum import Enum


class EdgeType(Enum):
    RESOURCE = "resource"      # B requires A's ID
    TEMPORAL = "temporal"      # B depends on A's context
    ALTERNATIVE = "alternative"  # A/B are interchangeable


@dataclass
class Edge:
    from_tool: str
    to_tool: str
    edge_type: EdgeType
    field: str = ""       # field name passed through (used for resource edges)
    reason: str = ""      # reason for dependency (used for temporal edges)


# ============================================================
# Tool list (grouped by category)
# ============================================================

# Search tools (return lists containing IDs)
SEARCH_TOOLS = [
    "search_hotels",
    "search_flights",
    "search_trains",
    "search_restaurants",
    "search_restaurants_delivery",
    "search_movies",
    "search_shows",
    "search_attractions",
    "search_sports_events",
    "search_cars",
    "search_doctors",
    "search_home_services",
    "search_courses",
    "search_books",
    "search_parking",
]

# Book tools (require an ID, perform the booking)
BOOK_TOOLS = [
    "book_hotel",
    "book_flight",
    "book_train",
    "book_restaurant",
    "place_food_order",
    "book_movie_ticket",
    "book_show_ticket",
    "book_attraction_ticket",
    "book_sports_ticket",
    "book_car",
    "book_appointment",
    "book_home_service",
    "enroll_course",
    "reserve_book",
    "reserve_parking_spot",
]

# Standalone tools (do not depend on other tools)
STANDALONE_TOOLS = [
    # Ride-hailing
    "request_ride",
    "check_ride_status",
    "cancel_ride",
    # Financial
    "check_balance",
    "transfer_money",
    "get_transaction_history",
    "pay_bill",
    "list_bills",
    # Other
    "search_medicine",
    "track_package",
    "renew_book",
]

# All tools
ALL_TOOLS = SEARCH_TOOLS + BOOK_TOOLS + STANDALONE_TOOLS


# ============================================================
# Read / Write classification (independent of the search->book dependency graph)
#
# Used by the proactive scorer to distinguish act_read vs. act_write, and by
# generate_tasks.py when writing the tool_universe.{read,write}_tools fields.
#
# Classification rule: by action semantics. None of the mock tools truly mutate
# persistent state; we classify by "user intent" instead.
#   read  = query / list / track / check
#   write = create / cancel / transfer / pay / renew
#
# Important: do NOT use prefix-based heuristics (e.g. startswith "check_") —
# they would miss semantically-read tools like search_medicine or track_package
# whose prefixes aren't on the allow list.
# ============================================================

READ_TOOLS = SEARCH_TOOLS + [
    "check_ride_status",
    "check_balance",
    "get_transaction_history",
    "list_bills",
    "search_medicine",   # medicine lookup (no book pair, so listed as STANDALONE, but semantically a read)
    "track_package",     # check package status
]

WRITE_TOOLS = BOOK_TOOLS + [
    "request_ride",      # create a new ride record
    "cancel_ride",       # change ride state
    "pay_bill",          # deduct funds + change bill status
    "transfer_money",    # money transfer
    "renew_book",        # change loan duration
]

# Self-check: must cover every tool with no overlap (so adding a tool later cannot silently miss classification)
assert set(READ_TOOLS) | set(WRITE_TOOLS) == set(ALL_TOOLS), \
    f"READ/WRITE does not cover all tools, missing: {set(ALL_TOOLS) - set(READ_TOOLS) - set(WRITE_TOOLS)}"
assert set(READ_TOOLS).isdisjoint(set(WRITE_TOOLS)), \
    f"READ/WRITE tool overlap: {set(READ_TOOLS) & set(WRITE_TOOLS)}"


# ============================================================
# Resource dependency edges (search -> book)
# ============================================================

# search -> book lookup (built lazily from RESOURCE_EDGES)
_SEARCH_TO_BOOK = None

def get_book_tool(search_tool: str) -> Optional[str]:
    """Look up the book tool corresponding to a search tool; return None if there is none."""
    global _SEARCH_TO_BOOK
    if _SEARCH_TO_BOOK is None:
        _SEARCH_TO_BOOK = {e.from_tool: e.to_tool for e in RESOURCE_EDGES}
    return _SEARCH_TO_BOOK.get(search_tool)


RESOURCE_EDGES = [
    Edge("search_hotels", "book_hotel", EdgeType.RESOURCE, field="hotel_id"),
    Edge("search_flights", "book_flight", EdgeType.RESOURCE, field="flight_id"),
    Edge("search_trains", "book_train", EdgeType.RESOURCE, field="train_id"),
    Edge("search_restaurants", "book_restaurant", EdgeType.RESOURCE, field="restaurant_id"),
    Edge("search_restaurants_delivery", "place_food_order", EdgeType.RESOURCE, field="delivery_id"),
    Edge("search_movies", "book_movie_ticket", EdgeType.RESOURCE, field="movie_id"),
    Edge("search_shows", "book_show_ticket", EdgeType.RESOURCE, field="show_id"),
    Edge("search_attractions", "book_attraction_ticket", EdgeType.RESOURCE, field="attraction_id"),
    Edge("search_sports_events", "book_sports_ticket", EdgeType.RESOURCE, field="event_id"),
    Edge("search_cars", "book_car", EdgeType.RESOURCE, field="car_id"),
    Edge("search_doctors", "book_appointment", EdgeType.RESOURCE, field="doctor_id"),
    Edge("search_home_services", "book_home_service", EdgeType.RESOURCE, field="service_id"),
    Edge("search_courses", "enroll_course", EdgeType.RESOURCE, field="course_id"),
    Edge("search_books", "reserve_book", EdgeType.RESOURCE, field="book_id"),
    Edge("search_parking", "reserve_parking_spot", EdgeType.RESOURCE, field="parking_id"),
]


# ============================================================
# Temporal dependency edges (typical tool combinations)
# ============================================================

TEMPORAL_EDGES = [
    # Travel scenario: book transportation first, then hotel
    Edge("book_flight", "book_hotel", EdgeType.TEMPORAL, reason="check-in time determined by flight time"),
    Edge("book_train", "book_hotel", EdgeType.TEMPORAL, reason="check-in time determined by train time"),

    # Hotel + restaurant: find nearby restaurant after booking a hotel
    Edge("book_hotel", "search_restaurants", EdgeType.TEMPORAL, reason="find a restaurant near the hotel"),
    Edge("book_hotel", "search_attractions", EdgeType.TEMPORAL, reason="find attractions near the hotel"),

    # Movie / show + meal
    Edge("book_movie_ticket", "search_restaurants", EdgeType.TEMPORAL, reason="eat before or after the movie"),
    Edge("book_show_ticket", "search_restaurants", EdgeType.TEMPORAL, reason="eat before or after the show"),

    # Car rental + parking
    Edge("book_car", "search_parking", EdgeType.TEMPORAL, reason="find a parking spot after renting a car"),

    # Doctor visit + medicine
    Edge("book_appointment", "search_medicine", EdgeType.TEMPORAL, reason="buy medicine after the visit"),
]


# ============================================================
# Alternative edges (functionally similar tools)
# ============================================================

ALTERNATIVE_EDGES = [
    # Interchangeable transport modes
    Edge("search_flights", "search_trains", EdgeType.ALTERNATIVE),
    Edge("search_trains", "search_flights", EdgeType.ALTERNATIVE),

    # Dine-in vs. delivery
    Edge("search_restaurants", "search_restaurants_delivery", EdgeType.ALTERNATIVE),
    Edge("search_restaurants_delivery", "search_restaurants", EdgeType.ALTERNATIVE),
]


# ============================================================
# Tool graph class
# ============================================================

class ToolGraph:
    """Tool dependency graph."""

    def __init__(self):
        self.nodes = set(ALL_TOOLS)
        self.edges: List[Edge] = RESOURCE_EDGES + TEMPORAL_EDGES + ALTERNATIVE_EDGES

        # Build adjacency lists
        self._build_adjacency()

    def _build_adjacency(self):
        """Build the adjacency lists."""
        # Outgoing edges: from_tool -> [to_tools]
        self.outgoing: Dict[str, List[Edge]] = {tool: [] for tool in self.nodes}
        # Incoming edges: to_tool -> [from_tools]
        self.incoming: Dict[str, List[Edge]] = {tool: [] for tool in self.nodes}

        for edge in self.edges:
            if edge.from_tool in self.nodes and edge.to_tool in self.nodes:
                self.outgoing[edge.from_tool].append(edge)
                self.incoming[edge.to_tool].append(edge)

    def get_downstream(self, tool: str, edge_types: List[EdgeType] = None) -> List[str]:
        """Return downstream tools (tools that can follow `tool`)."""
        if edge_types is None:
            edge_types = [EdgeType.RESOURCE, EdgeType.TEMPORAL]

        result = []
        for edge in self.outgoing.get(tool, []):
            if edge.edge_type in edge_types:
                result.append(edge.to_tool)
        return result

    def get_upstream(self, tool: str, edge_types: List[EdgeType] = None) -> List[str]:
        """Return upstream tools (tools that must come before `tool`)."""
        if edge_types is None:
            edge_types = [EdgeType.RESOURCE, EdgeType.TEMPORAL]

        result = []
        for edge in self.incoming.get(tool, []):
            if edge.edge_type in edge_types:
                result.append(edge.from_tool)
        return result

    def get_resource_dependency(self, book_tool: str) -> Tuple[str, str]:
        """Return the resource dependency of a book tool (search_tool, field)."""
        for edge in self.incoming.get(book_tool, []):
            if edge.edge_type == EdgeType.RESOURCE:
                return edge.from_tool, edge.field
        return None, None

    def get_alternatives(self, tool: str) -> List[str]:
        """Return tools that can replace `tool`."""
        result = []
        for edge in self.outgoing.get(tool, []):
            if edge.edge_type == EdgeType.ALTERNATIVE:
                result.append(edge.to_tool)
        return result

    def get_search_book_pair(self, search_tool: str) -> str:
        """Return the book tool corresponding to a search tool."""
        for edge in self.outgoing.get(search_tool, []):
            if edge.edge_type == EdgeType.RESOURCE:
                return edge.to_tool
        return None

    def is_search_tool(self, tool: str) -> bool:
        """Return True if `tool` is a search tool."""
        return tool in SEARCH_TOOLS

    def is_book_tool(self, tool: str) -> bool:
        """Return True if `tool` is a book tool."""
        return tool in BOOK_TOOLS

    def is_standalone_tool(self, tool: str) -> bool:
        """Return True if `tool` is a standalone tool."""
        return tool in STANDALONE_TOOLS


# ============================================================
# Tool chain templates (common tool combinations)
# ============================================================

# Predefined tool chain templates, used for DAG sampling
CHAIN_TEMPLATES = {
    # Business trip: flight + hotel + restaurant
    "business_trip": [
        ["search_flights", "book_flight"],
        ["search_hotels", "book_hotel"],
        ["search_restaurants", "book_restaurant"],
    ],

    # Travel: train + hotel + attractions
    "travel": [
        ["search_trains", "book_train"],
        ["search_hotels", "book_hotel"],
        ["search_attractions", "book_attraction_ticket"],
    ],

    # Date night: movie + restaurant
    "date": [
        ["search_movies", "book_movie_ticket"],
        ["search_restaurants", "book_restaurant"],
    ],

    # Show + restaurant
    "entertainment": [
        ["search_shows", "book_show_ticket"],
        ["search_restaurants", "book_restaurant"],
    ],

    # Car rental + parking
    "driving": [
        ["search_cars", "book_car"],
        ["search_parking", "reserve_parking_spot"],
    ],

    # Doctor visit + medicine
    "healthcare": [
        ["search_doctors", "book_appointment"],
        ["search_medicine"],
    ],

    # Sports event: buy ticket + pre/post-game meal
    "sports_event": [
        ["search_sports_events", "book_sports_ticket"],
        ["search_restaurants", "book_restaurant"],
    ],

    # Home services: search + book + pay
    "home_service": [
        ["search_home_services", "book_home_service"],
        ["pay_bill"],
    ],
}


# Global instance
TOOL_GRAPH = ToolGraph()


# ============================================================
# Tool-category mapping (shared between proactive and reactive)
# ============================================================

def _build_tool_to_category():
    """Build the tool-category mapping dynamically from tool_graph.

    Uses the search->book resource dependency to keep a search tool and its
    matching book tool in the same category.
    """
    # search tool keyword -> category
    SEARCH_CATEGORY_RULES = [
        (['doctor'], 'healthcare'),
        (['course', 'books'], 'education'),
        (['parking'], 'transportation'),
        (['movie', 'show', 'sports'], 'entertainment'),
        (['delivery', 'home_service'], 'life_services'),
        (['hotel', 'flight', 'train', 'restaurant', 'car', 'attraction'], 'travel_booking'),
    ]

    # standalone tool keyword -> category
    STANDALONE_CATEGORY_RULES = [
        (['medicine'], 'healthcare'),
        (['balance', 'transfer', 'transaction', 'bill'], 'financial'),
        (['renew_book'], 'education'),
        (['ride'], 'transportation'),
        (['package'], 'life_services'),
    ]

    result = {}

    # 1. Categorize search tools first
    for tool in SEARCH_TOOLS:
        for keywords, category in SEARCH_CATEGORY_RULES:
            if any(kw in tool for kw in keywords):
                result[tool] = category
                break

    # 2. Book tools inherit their corresponding search tool's category
    for tool in BOOK_TOOLS:
        search_tool, _ = TOOL_GRAPH.get_resource_dependency(tool)
        if search_tool and search_tool in result:
            result[tool] = result[search_tool]

    # 3. Categorize standalone tools separately
    for tool in STANDALONE_TOOLS:
        for keywords, category in STANDALONE_CATEGORY_RULES:
            if any(kw in tool for kw in keywords):
                result[tool] = category
                break

    return result


TOOL_TO_CATEGORY = _build_tool_to_category()


def get_tool_category(tool: str) -> str:
    """Return the category for a given tool."""
    return TOOL_TO_CATEGORY.get(tool, "other")


# ============================================================
# Tests
# ============================================================

if __name__ == "__main__":
    graph = TOOL_GRAPH

    print("=" * 60)
    print("Tool Graph statistics")
    print("=" * 60)
    print(f"Nodes: {len(graph.nodes)}")
    print(f"Edges: {len(graph.edges)}")
    print(f"  - Resource: {len(RESOURCE_EDGES)}")
    print(f"  - Temporal: {len(TEMPORAL_EDGES)}")
    print(f"  - Alternative: {len(ALTERNATIVE_EDGES)}")

    print("\n" + "=" * 60)
    print("Search -> Book mapping")
    print("=" * 60)
    for search in SEARCH_TOOLS:
        book = graph.get_search_book_pair(search)
        if book:
            _, field = graph.get_resource_dependency(book)
            print(f"  {search} -> {book} (field: {field})")

    print("\n" + "=" * 60)
    print("Temporal dependencies")
    print("=" * 60)
    for edge in TEMPORAL_EDGES:
        print(f"  {edge.from_tool} -> {edge.to_tool}")
        print(f"    reason: {edge.reason}")

    print("\n" + "=" * 60)
    print("Downstream tools (samples)")
    print("=" * 60)
    for tool in ["search_hotels", "book_hotel", "book_flight"]:
        downstream = graph.get_downstream(tool)
        print(f"  {tool} -> {downstream}")
