#!/usr/bin/env python3
"""
Dual-Layer Verification - validates generated tasks.

Layers:
1. Rule Checker: format, parameter completeness, ID chain, mock-data consistency.
2. Model Checker: uses GPT-4o to verify task completability (optional).
"""

import os
import json
from typing import Dict, List, Tuple, Any, Optional

from scripts.task_gen.tool_graph import TOOL_GRAPH, SEARCH_TOOLS, BOOK_TOOLS

# Import mock_data for verification
from eval.tools.mock_data import (
    FLIGHTS, TRAINS, HOTELS, RENTAL_CARS, RESTAURANTS, ATTRACTIONS,
    DELIVERY_RESTAURANTS, HOME_SERVICES, MOVIES, SHOWS, SPORTS_EVENTS,
    DOCTORS, MEDICINES, COURSES, BOOKS, PARKING_LOTS, BILLS
)


# ============================================================
# Tool parameter definitions
# ============================================================

# Dynamically fetch a tool's required parameters from its schema
def _build_tool_required_params() -> Dict[str, list]:
    """Build the required-parameter table dynamically from each tool's schema."""
    from scripts.task_gen.param_engine import get_tool_instance, TOOL_MODULE_MAP
    result = {}
    for tool_name in TOOL_MODULE_MAP:
        inst = get_tool_instance(tool_name)
        if inst:
            result[tool_name] = inst.parameters.get("required", [])
        else:
            result[tool_name] = []
    return result

TOOL_REQUIRED_PARAMS = _build_tool_required_params()


# ============================================================
# Rule Checker
# ============================================================

def check_json_format(task: Dict) -> Tuple[bool, str]:
    """Check JSON format."""
    required_fields = ["task_id", "transcript", "expected_tools"]

    for field in required_fields:
        if field not in task:
            return False, f"missing required field: {field}"

    if not isinstance(task["transcript"], list):
        return False, "transcript must be a list"

    if not isinstance(task["expected_tools"], list):
        return False, "expected_tools must be a list"

    if len(task["transcript"]) == 0:
        return False, "transcript cannot be empty"

    # tool_cancel: expected_tools is intentionally empty (user cancelled everything)
    if len(task["expected_tools"]) == 0 and task.get("interruption_type") != "tool_cancel":
        return False, "expected_tools cannot be empty"

    return True, "passed"


def check_param_completeness(task: Dict) -> Tuple[bool, str]:
    """Check parameter completeness."""
    for exp in task.get("expected_tools", []):
        tool = exp.get("tool", "")
        params = exp.get("params", {})

        if tool not in TOOL_REQUIRED_PARAMS:
            return False, f"unknown tool: {tool}"

        required = TOOL_REQUIRED_PARAMS[tool]
        for r in required:
            if r not in params:
                return False, f"{tool} missing required parameter: {r}"
            if params[r] is None or params[r] == "":
                return False, f"{tool} parameter {r} is empty"

    return True, "passed"


def check_id_chain(task: Dict) -> Tuple[bool, str]:
    """Check the ID chain (every book tool must be preceded by its matching search tool)."""
    expected_tools = task.get("expected_tools", [])
    tool_names = [exp.get("tool", "") for exp in expected_tools]

    # Check each book tool
    for i, tool in enumerate(tool_names):
        if tool in BOOK_TOOLS:
            # Find the matching search tool
            search_tool, _ = TOOL_GRAPH.get_resource_dependency(tool)

            if search_tool:
                # Verify the search tool appears earlier in the chain
                if search_tool not in tool_names[:i]:
                    return False, f"{tool} missing prerequisite {search_tool}"

    return True, "passed"


def check_mock_data_consistency(task: Dict) -> Tuple[bool, str]:
    """Check that parameter values exist in mock_data (covers all IDs)."""
    for exp in task.get("expected_tools", []):
        tool = exp.get("tool", "")
        params = exp.get("params", {})

        # Check hotel ID
        if tool == "book_hotel" and "hotel_id" in params:
            hotel_id = params["hotel_id"]
            found = False
            for city_hotels in HOTELS.values():
                for h in city_hotels:
                    if h.get("hotel_id") == hotel_id:
                        found = True
                        break
            if not found:
                return False, f"hotel ID {hotel_id} not in mock_data"

        # Check flight ID
        if tool == "book_flight" and "flight_id" in params:
            flight_id = params["flight_id"]
            found = False
            for route_flights in FLIGHTS.values():
                for f in route_flights:
                    if f.get("flight_id") == flight_id:
                        found = True
                        break
            if not found:
                return False, f"flight ID {flight_id} not in mock_data"

        # Check train ID
        if tool == "book_train" and "train_id" in params:
            train_id = params["train_id"]
            found = False
            for route_trains in TRAINS.values():
                for t in route_trains:
                    if t.get("train_id") == train_id:
                        found = True
                        break
            if not found:
                return False, f"train ID {train_id} not in mock_data"

        # Check restaurant ID
        if tool == "book_restaurant" and "restaurant_id" in params:
            restaurant_id = params["restaurant_id"]
            found = False
            for city_restaurants in RESTAURANTS.values():
                for r in city_restaurants:
                    if r.get("restaurant_id") == restaurant_id:
                        found = True
                        break
            if not found:
                return False, f"restaurant ID {restaurant_id} not in mock_data"

        # Check delivery restaurant ID
        if tool == "place_food_order" and "delivery_id" in params:
            delivery_id = params["delivery_id"]
            found = False
            for city_restaurants in DELIVERY_RESTAURANTS.values():
                for r in city_restaurants:
                    if r.get("delivery_id") == delivery_id:
                        found = True
                        break
            if not found:
                return False, f"delivery restaurant ID {delivery_id} not in mock_data"

        # Check movie ID
        if tool == "book_movie_ticket" and "movie_id" in params:
            movie_id = params["movie_id"]
            found = False
            for city_movies in MOVIES.values():
                for m in city_movies:
                    if m["movie_id"] == movie_id:
                        found = True
                        break
            if not found:
                return False, f"movie ID {movie_id} not in mock_data"

        # Check show ID
        if tool == "book_show_ticket" and "show_id" in params:
            show_id = params["show_id"]
            found = False
            for city_shows in SHOWS.values():
                for s in city_shows:
                    if s["show_id"] == show_id:
                        found = True
                        break
            if not found:
                return False, f"show ID {show_id} not in mock_data"

        # Check attraction ID
        if tool == "book_attraction_ticket" and "attraction_id" in params:
            attraction_id = params["attraction_id"]
            found = False
            for city_attractions in ATTRACTIONS.values():
                for a in city_attractions:
                    if a.get("attraction_id") == attraction_id:
                        found = True
                        break
            if not found:
                return False, f"attraction ID {attraction_id} not in mock_data"

        # Check rental car ID
        if tool == "book_car" and "car_id" in params:
            car_id = params["car_id"]
            found = False
            for city_cars in RENTAL_CARS.values():
                for c in city_cars:
                    if c.get("car_id") == car_id:
                        found = True
                        break
            if not found:
                return False, f"rental car ID {car_id} not in mock_data"

        # Check doctor ID
        if tool == "book_appointment" and "doctor_id" in params:
            doctor_id = params["doctor_id"]
            found = False
            for city_doctors in DOCTORS.values():
                for d in city_doctors:
                    if d["doctor_id"] == doctor_id:
                        found = True
                        break
            if not found:
                return False, f"doctor ID {doctor_id} not in mock_data"

        # Check home-service ID
        if tool == "book_home_service" and "service_id" in params:
            service_id = params["service_id"]
            found = False
            for city_services in HOME_SERVICES.values():
                for s in city_services:
                    if s.get("service_id") == service_id:
                        found = True
                        break
            if not found:
                return False, f"home-service ID {service_id} not in mock_data"

        # Check parking lot ID
        if tool == "reserve_parking_spot" and "parking_id" in params:
            parking_id = params["parking_id"]
            found = False
            for city_parkings in PARKING_LOTS.values():
                for p in city_parkings:
                    if p.get("parking_id") == parking_id:
                        found = True
                        break
            if not found:
                return False, f"parking lot ID {parking_id} not in mock_data"

        # Check course ID
        if tool == "enroll_course" and "course_id" in params:
            course_id = params["course_id"]
            found = any(c["course_id"] == course_id for c in COURSES)
            if not found:
                return False, f"course ID {course_id} not in mock_data"

        # Check book ID
        if tool == "reserve_book" and "book_id" in params:
            book_id = params["book_id"]
            found = any(b["book_id"] == book_id for b in BOOKS)
            if not found:
                return False, f"book ID {book_id} not in mock_data"

    return True, "passed"


def check_search_execution(task: Dict) -> Tuple[bool, str]:
    """AST verification: actually execute search tools, verify non-empty result and that the book ID appears in the search result."""
    from scripts.task_gen.param_engine import get_tool_instance

    expected_tools = task.get("expected_tools", [])
    search_results_cache = {}  # index -> (tool_name, [results])

    # 1. Execute every search tool and verify a non-empty result
    for i, exp in enumerate(expected_tools):
        tool_name = exp.get("tool", "")
        params = exp.get("params", {})

        if not tool_name.startswith("search_"):
            continue

        inst = get_tool_instance(tool_name)
        if not inst:
            continue

        try:
            result = inst.execute(**params)
            raw = result.get("raw_output")
            # Fallback: older tools don't return raw_output (e.g. search_books/courses/medicine/parking/home_services/bills)
            # Infer from success flag + data fields instead
            if raw is None:
                if result.get("success") is False:
                    return False, f"{tool_name}({params}) execution failed: {result.get('error')}"
                # Pick the first non-empty list-typed business field
                _META_KEYS = {"success", "error", "count", "output", "latency_ms", "available_cities"}
                for k, v in result.items():
                    if k in _META_KEYS:
                        continue
                    if isinstance(v, list) and v:
                        raw = v
                        break
                # If no list field is present, fall back to using `count`
                if raw is None:
                    count = result.get("count", 0)
                    raw = [result] * count if count > 0 else []
            if not raw:
                return False, f"{tool_name}({params}) returned an empty result"
            search_results_cache[i] = (tool_name, raw)
        except Exception as e:
            return False, f"{tool_name} raised an exception: {e}"

    # 2. Verify each book tool's ID appears in the corresponding search result
    for i, exp in enumerate(expected_tools):
        tool_name = exp.get("tool", "")
        params = exp.get("params", {})

        if tool_name not in BOOK_TOOLS:
            continue

        # Locate the matching search tool
        dep = TOOL_GRAPH.get_resource_dependency(tool_name)
        if not dep:
            continue
        search_tool = dep[0]

        # Locate the search result
        search_results = None
        for j in range(i - 1, -1, -1):
            if j in search_results_cache:
                cached_name, cached_results = search_results_cache[j]
                if cached_name == search_tool:
                    search_results = cached_results
                    break

        if not search_results:
            continue

        # Verify each _id parameter appears in the search result
        for param_name, param_value in params.items():
            if param_name.endswith("_id") and param_value:
                found = any(
                    r.get(param_name) == param_value
                    for r in search_results
                )
                if not found:
                    valid_ids = [r.get(param_name) for r in search_results if r.get(param_name)]
                    return False, f"{tool_name}.{param_name}='{param_value}' not in {search_tool} results (valid: {valid_ids[:5]})"

    return True, "passed"


def check_date_logic(task: Dict) -> Tuple[bool, str]:
    """Check date logic."""
    for exp in task.get("expected_tools", []):
        tool = exp.get("tool", "")
        params = exp.get("params", {})

        # book_hotel now uses `nights` instead of `check_out`
        if tool == "book_hotel":
            nights = params.get("nights", 0)
            if nights is not None and nights <= 0:
                return False, f"book_hotel: nights ({nights}) must be greater than 0"

        # book_car now uses `days` instead of `return_date`
        if tool == "book_car":
            days = params.get("days", 0)
            if days is not None and days <= 0:
                return False, f"book_car: days ({days}) must be greater than 0"

    return True, "passed"


def rule_check(task: Dict) -> Tuple[bool, str]:
    """
    Rule check (runs every individual check).

    Returns:
        (passed, reason)
    """
    checks = [
        ("JSON format", check_json_format),
        ("Parameter completeness", check_param_completeness),
        ("ID chain", check_id_chain),
        ("Mock data consistency", check_mock_data_consistency),
        ("Date logic", check_date_logic),
        ("Search execution", check_search_execution),
    ]

    for check_name, check_func in checks:
        ok, reason = check_func(task)
        if not ok:
            return False, f"[{check_name}] {reason}"

    return True, "passed all rule checks"


# ============================================================
# Model Checker (optional)
# ============================================================

def model_check(task: Dict, model: str = "gpt-4o-mini") -> Tuple[bool, str]:
    """
    Use an LLM to verify task completability.

    Asks the model to read the transcript and predict the tool calls.
    """
    try:
        from openai import OpenAI
    except ImportError:
        return True, "skipped (OpenAI not installed)"

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        return True, "skipped (no API key)"

    client = OpenAI(api_key=api_key)

    # Build the prompt
    transcript_text = "\n".join([
        f"[{turn.get('speaker', 'user')}] {turn.get('text', '')}"
        for turn in task.get("transcript", [])
    ])

    expected_tools = [exp.get("tool") for exp in task.get("expected_tools", [])]

    prompt = f"""Based on the following conversation, what tools should be called?

Conversation:
{transcript_text}

Available tools: {', '.join(SEARCH_TOOLS + BOOK_TOOLS)}

List the tools that should be called (in order), one per line.
Only output tool names, nothing else."""

    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant that analyzes conversations and identifies required tool calls."},
                {"role": "user", "content": prompt}
            ],
            temperature=0,
            max_tokens=500,
        )

        content = response.choices[0].message.content.strip()
        predicted_tools = [line.strip() for line in content.split("\n") if line.strip()]

        # Compare the predicted tools against the expected tools
        if set(predicted_tools) == set(expected_tools):
            return True, "tools match"
        else:
            return False, f"tools do not match: expected {expected_tools}, predicted {predicted_tools}"

    except Exception as e:
        return True, f"skipped (API error: {e})"


# ============================================================
# Batch validation
# ============================================================

def validate_task(task: Dict, use_model_check: bool = False) -> Tuple[bool, str]:
    """
    Validate a single task.

    Args:
        task: task data
        use_model_check: whether to run the Model Checker

    Returns:
        (passed, reason)
    """
    # Rule Check
    ok, reason = rule_check(task)
    if not ok:
        return False, f"Rule Check: {reason}"

    # Model Check (optional)
    if use_model_check:
        ok, reason = model_check(task)
        if not ok:
            return False, f"Model Check: {reason}"

    return True, "validation passed"


def validate_batch(
    tasks: List[Dict],
    use_model_check: bool = False
) -> Tuple[List[Dict], List[Tuple[str, str]]]:
    """
    Validate a batch of tasks.

    Args:
        tasks: list of tasks
        use_model_check: whether to run the Model Checker

    Returns:
        (list of passing tasks, [(task_id, failure reason), ...])
    """
    valid_tasks = []
    failed = []

    for task in tasks:
        task_id = task.get("task_id", "unknown")
        ok, reason = validate_task(task, use_model_check)

        if ok:
            valid_tasks.append(task)
        else:
            failed.append((task_id, reason))

    return valid_tasks, failed


# ============================================================
# Tests
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Verification tests")
    print("=" * 60)

    # Test case 1: a valid task
    valid_task = {
        "task_id": "test_001",
        "transcript": [
            {"speaker": "user", "text": "Find hotels in Beijing"},
            {"speaker": "user", "text": "Book hotel_bj_001, check in March 15, 2 nights"},
            {"speaker": "user", "text": "My name is Zhang Wei"},
        ],
        "expected_tools": [
            {"tool": "search_hotels", "params": {"city": "Beijing"}},
            {
                "tool": "book_hotel",
                "params": {
                    "hotel_id": "hotel_bj_001",
                    "checkin_date": "2026-03-15",
                    "nights": 2,
                    "guest_name": "Zhang Wei"
                }
            }
        ]
    }

    print("\n--- Valid task test ---")
    ok, reason = rule_check(valid_task)
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    print(f"Reason: {reason}")

    # Test case 2: missing parameters
    invalid_task_1 = {
        "task_id": "test_002",
        "transcript": [{"speaker": "user", "text": "Book a hotel"}],
        "expected_tools": [
            {"tool": "book_hotel", "params": {"hotel_id": "hotel_bj_001"}}  # missing other params
        ]
    }

    print("\n--- Missing parameters test ---")
    ok, reason = rule_check(invalid_task_1)
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    print(f"Reason: {reason}")

    # Test case 3: broken ID chain
    invalid_task_2 = {
        "task_id": "test_003",
        "transcript": [{"speaker": "user", "text": "Book a hotel"}],
        "expected_tools": [
            {
                "tool": "book_hotel",  # no preceding search_hotels
                "params": {
                    "hotel_id": "hotel_bj_001",
                    "checkin_date": "2026-03-15",
                    "nights": 2,
                    "guest_name": "Zhang Wei"
                }
            }
        ]
    }

    print("\n--- Broken ID chain test ---")
    ok, reason = rule_check(invalid_task_2)
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    print(f"Reason: {reason}")

    # Test case 4: invalid date logic (nights <= 0)
    invalid_task_3 = {
        "task_id": "test_004",
        "transcript": [
            {"speaker": "user", "text": "Find hotels in Beijing"},
            {"speaker": "user", "text": "Book it"},
        ],
        "expected_tools": [
            {"tool": "search_hotels", "params": {"city": "Beijing"}},
            {
                "tool": "book_hotel",
                "params": {
                    "hotel_id": "hotel_bj_001",
                    "checkin_date": "2026-03-20",
                    "nights": 0,  # invalid nights value
                    "guest_name": "Zhang Wei"
                }
            }
        ]
    }

    print("\n--- Date logic error test ---")
    ok, reason = rule_check(invalid_task_3)
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    print(f"Reason: {reason}")

    # Test case 5: mock_data inconsistency
    invalid_task_4 = {
        "task_id": "test_005",
        "transcript": [
            {"speaker": "user", "text": "Find hotels in Beijing"},
            {"speaker": "user", "text": "Book fake hotel"},
        ],
        "expected_tools": [
            {"tool": "search_hotels", "params": {"city": "Beijing"}},
            {
                "tool": "book_hotel",
                "params": {
                    "hotel_id": "fake_hotel_id_not_exist",  # not in mock_data
                    "checkin_date": "2026-03-15",
                    "nights": 2,
                    "guest_name": "Zhang Wei"
                }
            }
        ]
    }

    print("\n--- Mock data inconsistency test ---")
    ok, reason = rule_check(invalid_task_4)
    print(f"Result: {'PASS' if ok else 'FAIL'}")
    print(f"Reason: {reason}")
