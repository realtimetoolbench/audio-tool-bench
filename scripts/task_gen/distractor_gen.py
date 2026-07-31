#!/usr/bin/env python3
"""
v7: Auto-generate distractor tools for proactive negative tasks.

Distractor = tools that could be falsely triggered by entities in the
transcript. Used to measure false-positive rate when the expected
decision is `wait` (negative band).

Algorithm — 3-layer expansion:
  L1: sampled tools themselves (their entities surface in the transcript)
  L2: same-category siblings (same domain → easy to confuse)
  L3: resource-pair tools (search↔book dependencies)
"""

from typing import List, Set
import sys
from pathlib import Path

# Allow running as a script (file at scripts/task_gen/distractor_gen.py → repo root = parents[2])
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.task_gen.tool_graph import (
    TOOL_GRAPH,
    TOOL_TO_CATEGORY,
    RESOURCE_EDGES,
    get_tool_category,
)


def auto_distractor_tools(
    sampled_tools: List[str],
    max_distractors: int = 8,
) -> List[str]:
    """Generate distractor tools deterministically from sampled tools.

    Args:
        sampled_tools: tools whose entities appear in the negative transcript.
        max_distractors: cap on output size (default 8).

    Returns:
        Sorted list of distractor tool names. Includes sampled_tools themselves.
    """
    distractors: Set[str] = set(sampled_tools)

    # L2: same-category siblings
    for tool in list(sampled_tools):
        category = get_tool_category(tool)
        if category and category != "other":
            siblings = [t for t, c in TOOL_TO_CATEGORY.items() if c == category]
            distractors.update(siblings)

    # L3: resource-pair tools (search↔book dependencies)
    for tool in list(sampled_tools):
        # downstream: tool → its dependents (e.g. search → book)
        distractors.update(TOOL_GRAPH.get_downstream(tool))
        # upstream: tool ← its predecessors (e.g. book → search)
        for edge in RESOURCE_EDGES:
            if edge.to_tool == tool:
                distractors.add(edge.from_tool)

    return sorted(distractors)[:max_distractors]


if __name__ == "__main__":
    cases = [
        ["search_movies", "book_movie_ticket"],
        ["search_flights", "book_flight", "search_hotels"],
        ["check_balance"],
        ["search_restaurants", "book_restaurant", "search_movies", "book_movie_ticket"],
        ["search_doctors", "book_appointment"],
    ]
    for case in cases:
        distractors = auto_distractor_tools(case)
        print(f"\nInput ({len(case)}): {case}")
        print(f"Distractors ({len(distractors)}): {distractors}")
