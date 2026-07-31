"""
Automated parameter sampling system.

Samples parameters from a tool's JSON Schema definition to avoid hard-coding.
Supports both single-tool sampling and chained tool sampling with context propagation.
"""

import random
import importlib
from typing import Dict, Any, List, Tuple
from eval.tools.mock_data import (
    HOTELS, FLIGHTS, TRAINS, RESTAURANTS, DELIVERY_RESTAURANTS,
    RENTAL_CARS, MOVIES, SHOWS, SPORTS_EVENTS, ATTRACTIONS,
    DOCTORS, HOME_SERVICES, PARKING_LOTS, COURSES, BOOKS,
    MEDICINES, DATES, TIMES, NAMES,
    BILLS, BANK_ACCOUNTS, PACKAGES, RIDE_STATUSES, BORROWED_BOOKS,
    PHONES, ID_NUMBERS, ADDRESSES, LICENSE_PLATES, LOCATIONS,
)


def get_available_cities(data_dict: Dict[str, List]) -> List[str]:
    """Return the list of available cities from a data dictionary."""
    return list(data_dict.keys())


def get_available_routes(data_dict: Dict[str, List]) -> List[tuple]:
    """Return the list of available routes from a data dictionary."""
    routes = set()
    for items in data_dict.values():
        for item in items:
            if "origin" in item and "destination" in item:
                routes.add((item["origin"], item["destination"]))
    return list(routes)


# Parameter name -> data source mapping
PARAM_DATA_SOURCES = {
    "city": lambda: random.choice(get_available_cities(HOTELS) or ["Beijing"]),
    "date": lambda: random.choice(DATES),
    "checkin_date": lambda: random.choice(DATES),
    "checkout_date": lambda: random.choice(DATES),
    "pickup_date": lambda: random.choice(DATES),
    "time": lambda: random.choice(TIMES),
    "phone": lambda: random.choice(PHONES),
    "driver_phone": lambda: random.choice(PHONES),
    "contact_phone": lambda: random.choice(PHONES),
    "passenger_name": lambda: random.choice(NAMES),
    "guest_name": lambda: random.choice(NAMES),
    "renter_name": lambda: random.choice(NAMES),
    "driver_name": lambda: random.choice(NAMES),
    "student_name": lambda: random.choice(NAMES),
    "reader_name": lambda: random.choice(NAMES),
    "patient_name": lambda: random.choice(NAMES),
    "buyer_name": lambda: random.choice(NAMES),
    "contact_name": lambda: random.choice(NAMES),
    "seat_class": lambda: random.choice(["First Class", "Second Class"]),
    "cabin_class": lambda: random.choice(["Economy", "Business", "First Class"]),
    "id_number": lambda: random.choice(ID_NUMBERS),
    "time_slot": lambda: random.choice(["morning", "afternoon"]),
    "address": lambda: random.choice(ADDRESSES),
    "license_plate": lambda: random.choice(LICENSE_PLATES),
    "start_time": lambda: f"{random.choice(DATES)} {random.choice(TIMES)}",
    "account_number": lambda: random.choice(BANK_ACCOUNTS)["account_id"],
    "tracking_number": lambda: random.choice(list(PACKAGES.keys())),
    "min_stars": lambda: random.randint(1, 5),
    "ticket_count": lambda: random.randint(1, 5),
    "seat_count": lambda: random.randint(1, 4),
    "party_size": lambda: random.randint(1, 10),
    "nights": lambda: random.randint(1, 5),
    "duration_hours": lambda: random.choice([1, 2, 3, 4, 6, 8, 12, 24]),
    "keyword": lambda: random.choice(["fever", "headache", "cold", "cough", "pain relief"]),
    "medicine_name": lambda: random.choice(MEDICINES)["name"] if MEDICINES else "Ibuprofen",
    "pickup": lambda: random.choice(LOCATIONS),
    "destination": lambda: random.choice(LOCATIONS),
    "ride_id": lambda: random.choice(list(RIDE_STATUSES.keys())),
    "bill_id": lambda: random.choice([b["bill_id"] for b in BILLS if b["status"] == "Unpaid"]),
    "book_id": lambda: random.choice(BORROWED_BOOKS)["book_id"],
}


# Tool -> data source mapping (used so city sampling only picks cities with data)
TOOL_DATA_SOURCE = {
    "search_hotels": HOTELS,
    "search_restaurants": RESTAURANTS,
    "search_restaurants_delivery": DELIVERY_RESTAURANTS,
    "search_cars": RENTAL_CARS,
    "search_movies": MOVIES,
    "search_shows": SHOWS,
    "search_sports_events": SPORTS_EVENTS,
    "search_attractions": ATTRACTIONS,
    "search_doctors": DOCTORS,
    "search_home_services": HOME_SERVICES,
    "search_parking": PARKING_LOTS,
}

# Tool-specific sampling rules (only special cases configured here)
TOOL_SPECIFIC_RULES = {
    "search_flights": {
        "origin": lambda ctx: random.choice(get_available_routes(FLIGHTS) or [("Beijing", "Shanghai")])[0],
        "destination": lambda ctx: random.choice(get_available_routes(FLIGHTS) or [("Beijing", "Shanghai")])[1],
        "cabin_class": lambda ctx: "Economy",  # mock data only has economy
        "max_price": lambda ctx: random.choice([800, 1000, 1200, 1500]),  # flight price range: 720-1200
    },
    "search_trains": {
        "origin": lambda ctx: random.choice(get_available_routes(TRAINS) or [("Beijing", "Shanghai")])[0],
        "destination": lambda ctx: random.choice(get_available_routes(TRAINS) or [("Beijing", "Shanghai")])[1],
    },
    "search_books": {
        "keyword": lambda ctx: random.choice(BOOKS).get("title", "Python") if BOOKS else "Python",
        "category": lambda ctx: random.choice([b["category"] for b in BOOKS]) if BOOKS else "Computer Science",
        "author": lambda ctx: random.choice(BOOKS).get("author", "Unknown") if BOOKS else "Unknown",
    },
    "place_food_order": {
        "delivery_id": lambda ctx: ctx.get("selected_delivery", {}).get("delivery_id", "dlv_sh_001"),
        "items": lambda ctx: random.choice(
            ctx.get("selected_delivery", {}).get("menu", ["Kung Pao Chicken and Rice"])
        ),
        "delivery_address": lambda ctx: random.choice(ADDRESSES),
    },
    "book_appointment": {
        "date": lambda ctx: random.choice(
            ctx.get("selected_doctor", {}).get("available_dates", DATES)
        ),
    },
    "book_restaurant": {
        "time": lambda ctx: random.choice(["11:30", "12:00", "14:00", "18:00", "19:00", "20:00"]),
    },
    "book_movie_ticket": {
        "cinema": lambda ctx: random.choice(ctx["selected_movie"]["cinemas"]) if ctx.get("selected_movie") else "Wanda Cinema CBD",
        "showtime": lambda ctx: random.choice(ctx["selected_movie"]["showtimes"]) if ctx.get("selected_movie") else "19:00",
    },
    "book_show_ticket": {
        "seat_zone": lambda ctx: random.choice(ctx["selected_show"]["available_zones"]) if ctx.get("selected_show") else "Stand A",
    },
    "book_sports_ticket": {
        "seat_zone": lambda ctx: random.choice(ctx["selected_sports_event"]["available_zones"]) if ctx.get("selected_sports_event") else "Stand A",
    },
}


def sample_param_value(param_name: str, param_schema: Dict, tool_name: str, context: Dict[str, Any]) -> Any:
    """Sample a value for a single parameter."""
    # 1. Check tool-specific rules
    if tool_name in TOOL_SPECIFIC_RULES:
        tool_rules = TOOL_SPECIFIC_RULES[tool_name]
        if param_name in tool_rules:
            return tool_rules[param_name](context)

    # 2. city parameter: pick from the tool's own data source (ensures data exists)
    if param_name == "city" and tool_name in TOOL_DATA_SOURCE:
        cities = get_available_cities(TOOL_DATA_SOURCE[tool_name])
        return random.choice(cities) if cities else "Beijing"

    # 3. Check the generic parameter mapping
    if param_name in PARAM_DATA_SOURCES:
        return PARAM_DATA_SOURCES[param_name]()

    # 3. Check for an enum in the schema
    if "enum" in param_schema:
        return random.choice(param_schema["enum"])

    # 4. Produce a default based on parameter type
    param_type = param_schema.get("type", "string")

    if param_type == "string":
        # ID parameters: fetch from context
        if param_name.endswith("_id"):
            # param_name -> context key mapping (handles naming mismatches)
            ID_TO_CONTEXT_KEY = {
                "event_id": "selected_sports_event",
                "delivery_id": "selected_delivery",
            }
            if param_name in ID_TO_CONTEXT_KEY:
                context_key = ID_TO_CONTEXT_KEY[param_name]
            else:
                entity_type = param_name.replace("_id", "")
                context_key = f"selected_{entity_type}"
            if context_key in context:
                entity = context[context_key]
                return entity.get(param_name, None)
            return None
        # Parameters containing "name" use a person name (excluding non-person fields)
        if "name" in param_name and param_name not in ["show_name", "movie_name", "medicine_name", "hospital"]:
            return random.choice(NAMES)
        # Return None for string parameters we cannot infer (skip)
        return None

    elif param_type == "integer":
        return random.randint(1, 10)

    elif param_type == "number":
        return round(random.uniform(100, 1000), 2)

    elif param_type == "boolean":
        return random.choice([True, False])

    return None


def sample_params_for_tool_auto(tool_instance, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Automatically sample parameters for a tool based on its JSON Schema."""
    context = context or {}
    params = {}

    tool_name = tool_instance.name
    schema = tool_instance.parameters

    properties = schema.get("properties", {})
    required = schema.get("required", [])

    # Sample all required parameters
    for param_name in required:
        if param_name in properties:
            param_schema = properties[param_name]
            value = sample_param_value(param_name, param_schema, tool_name, context)
            if value is not None:
                params[param_name] = value

    # TODO: optional parameters are not sampled yet — focus on getting required ones right first
    # optional_params = [p for p in properties.keys() if p not in required]
    # for param_name in optional_params:
    #     param_schema = properties[param_name]
    #     value = sample_param_value(param_name, param_schema, tool_name, context)
    #     if value is not None:
    #         params[param_name] = value

    return params


# ============================================================
# Tool instance loading
# ============================================================

# Tool name -> (module, class name) mapping
TOOL_MODULE_MAP = {
    "search_hotels": ("eval.tools.hotel_tools", "HotelSearchTool"),
    "book_hotel": ("eval.tools.hotel_tools", "BookHotelTool"),
    "search_flights": ("eval.tools.flight_tools", "FlightSearchTool"),
    "book_flight": ("eval.tools.flight_tools", "BookFlightTool"),
    "search_trains": ("eval.tools.train_ticket_tools", "TrainSearchTool"),
    "book_train": ("eval.tools.train_ticket_tools", "BookTrainTool"),
    "search_restaurants": ("eval.tools.restaurant_tools", "RestaurantSearchTool"),
    "book_restaurant": ("eval.tools.restaurant_tools", "MakeReservationTool"),
    "search_restaurants_delivery": ("eval.tools.food_delivery_tools", "DeliveryRestaurantSearchTool"),
    "place_food_order": ("eval.tools.food_delivery_tools", "PlaceFoodOrderTool"),
    "search_cars": ("eval.tools.car_rental_tools", "CarRentalTool"),
    "book_car": ("eval.tools.car_rental_tools", "BookCarTool"),
    "search_attractions": ("eval.tools.attraction_ticket_tools", "AttractionSearchTool"),
    "book_attraction_ticket": ("eval.tools.attraction_ticket_tools", "BookAttractionTicketTool"),
    "search_movies": ("eval.tools.movie_ticket_tools", "MovieSearchTool"),
    "book_movie_ticket": ("eval.tools.movie_ticket_tools", "BookMovieTicketTool"),
    "search_shows": ("eval.tools.show_ticket_tools", "ShowSearchTool"),
    "book_show_ticket": ("eval.tools.show_ticket_tools", "BookShowTicketTool"),
    "search_sports_events": ("eval.tools.sports_ticket_tools", "SportsEventSearchTool"),
    "book_sports_ticket": ("eval.tools.sports_ticket_tools", "BookSportsTicketTool"),
    "search_doctors": ("eval.tools.doctor_appointment_tools", "DoctorSearchTool"),
    "book_appointment": ("eval.tools.doctor_appointment_tools", "BookAppointmentTool"),
    "search_home_services": ("eval.tools.home_service_tools", "HomeServiceSearchTool"),
    "book_home_service": ("eval.tools.home_service_tools", "BookCleaningServiceTool"),
    "search_parking": ("eval.tools.parking_tools", "SearchParkingTool"),
    "reserve_parking_spot": ("eval.tools.parking_tools", "ReserveParkingSpotTool"),
    "search_courses": ("eval.tools.course_enrollment_tools", "CourseSearchTool"),
    "enroll_course": ("eval.tools.course_enrollment_tools", "EnrollCourseTool"),
    "search_books": ("eval.tools.library_tools", "BookSearchTool"),
    "reserve_book": ("eval.tools.library_tools", "ReserveBookTool"),
    "check_balance": ("eval.tools.bank_account_tools", "CheckBalanceTool"),
    "get_transaction_history": ("eval.tools.bank_account_tools", "GetTransactionHistoryTool"),
    "request_ride": ("eval.tools.ride_hailing_tools", "RequestRideTool"),
    "check_ride_status": ("eval.tools.ride_hailing_tools", "CheckRideStatusTool"),
    "cancel_ride": ("eval.tools.ride_hailing_tools", "CancelRideTool"),
    "transfer_money": ("eval.tools.money_transfer_tools", "TransferMoneyTool"),
    "pay_bill": ("eval.tools.bill_payment_tools", "PayBillTool"),
    "list_bills": ("eval.tools.bill_payment_tools", "ListBillsTool"),
    "search_medicine": ("eval.tools.medicine_search_tools", "MedicineSearchTool"),
    "track_package": ("eval.tools.package_tracking_tools", "TrackPackageTool"),
    "renew_book": ("eval.tools.library_tools", "RenewBookTool"),
}


def get_tool_instance(tool_name: str):
    """Dynamically obtain a tool instance."""
    if tool_name not in TOOL_MODULE_MAP:
        return None

    module_name, class_name = TOOL_MODULE_MAP[tool_name]

    try:
        module = importlib.import_module(module_name)
        tool_class = getattr(module, class_name)
        return tool_class()
    except (ImportError, AttributeError) as e:
        print(f"Warning: Failed to load tool {tool_name}: {e}")
        return None


# ============================================================
# Chained parameter sampling (with context propagation)
# ============================================================

def sample_params_for_tool(tool: str, context: Dict[str, Any] = None) -> Dict[str, Any]:
    """Sample parameters for a single tool."""
    context = context or {}
    tool_instance = get_tool_instance(tool)
    if not tool_instance:
        return {}
    return sample_params_for_tool_auto(tool_instance, context)


def sample_params_for_chain(tools: List[str]) -> Tuple[List[Dict], List[Dict]]:
    """
    Sample parameters for an entire tool chain.

    Key idea: simulate search results so that the matching book tool can consume them.

    Returns:
        (transcript_params, expected_tools) — two lists parallel to `tools`
        - transcript_params: [{"tool": name, "params": {IDs replaced with names}}, ...] — used in the transcript
        - expected_tools: [{"tool": name, "params": {real IDs}}, ...] — used for evaluation
    """
    transcript_params = []
    expected_tools = []
    context = {}

    for tool in tools:
        params = sample_params_for_tool(tool, context)
        expected_tools.append({
            "tool": tool,
            "params": params.copy()
        })
        _update_context_after_search(tool, params, context)

        # Replace IDs with human-readable names (for transcript use)
        readable_params = {}
        for param_name, value in params.items():
            if param_name in _ID_TO_READABLE and value:
                ctx_key, name_field = _ID_TO_READABLE[param_name]
                entity = context.get(ctx_key)
                if entity:
                    readable = entity.get(name_field)
                    if readable:
                        readable_params[param_name] = readable
                        continue
            readable_params[param_name] = value

        # Supplementary info: pass airline name for book_flight
        if tool == "book_flight" and "selected_flight" in context:
            airline = context["selected_flight"].get("airline")
            if airline:
                readable_params["_airline"] = airline

        transcript_params.append({
            "tool": tool,
            "params": readable_params
        })

    return transcript_params, expected_tools


# ID parameter -> (context key, human-readable field name)
_ID_TO_READABLE = {
    "hotel_id":       ("selected_hotel",        "name"),
    "restaurant_id":  ("selected_restaurant",   "name"),
    "movie_id":       ("selected_movie",        "name"),
    "show_id":        ("selected_show",          "name"),
    "event_id":       ("selected_sports_event",  "name"),
    "attraction_id":  ("selected_attraction",    "name"),
    "doctor_id":      ("selected_doctor",        "name"),
    "service_id":     ("selected_home_service",  "name"),
    "parking_id":     ("selected_parking",       "name"),
    "car_id":         ("selected_car",           "model"),
    "course_id":      ("selected_course",        "name"),
    "book_id":        ("selected_book",          "title"),
    "delivery_id":    ("selected_delivery",      "name"),
    "flight_id":      ("selected_flight",        "flight_no"),
    "train_id":       ("selected_train",         "train_no"),
}


def _update_context_after_search(tool: str, params: Dict, context: Dict):
    """Simulate context updates after a search tool runs."""
    # search tool -> (data source, context key)
    CITY_BASED_SEARCH = {
        "search_hotels": (HOTELS, "selected_hotel"),
        "search_restaurants": (RESTAURANTS, "selected_restaurant"),
        "search_restaurants_delivery": (DELIVERY_RESTAURANTS, "selected_delivery"),
        "search_cars": (RENTAL_CARS, "selected_car"),
        "search_movies": (MOVIES, "selected_movie"),
        "search_shows": (SHOWS, "selected_show"),
        "search_sports_events": (SPORTS_EVENTS, "selected_sports_event"),
        "search_attractions": (ATTRACTIONS, "selected_attraction"),
        "search_doctors": (DOCTORS, "selected_doctor"),
        "search_home_services": (HOME_SERVICES, "selected_home_service"),
        "search_parking": (PARKING_LOTS, "selected_parking"),
    }

    if tool in CITY_BASED_SEARCH:
        data_source, context_key = CITY_BASED_SEARCH[tool]
        city = params.get("city", "Beijing")
        items = data_source.get(city, [])
        if items:
            context[context_key] = random.choice(items)
            context["city"] = city

    elif tool == "search_flights":
        origin = params.get("origin")
        destination = params.get("destination")
        if origin and destination:
            flights = FLIGHTS.get((origin, destination), [])
            if flights:
                context["selected_flight"] = random.choice(flights)

    elif tool == "search_trains":
        origin = params.get("origin")
        destination = params.get("destination")
        if origin and destination:
            trains = TRAINS.get((origin, destination), [])
            if trains:
                context["selected_train"] = random.choice(trains)

    elif tool == "search_courses":
        if COURSES:
            context["selected_course"] = random.choice(COURSES)

    elif tool == "search_books":
        available_books = [b for b in BOOKS if b.get("available_copies", 0) > 0]
        if available_books:
            context["selected_book"] = random.choice(available_books)

