#!/usr/bin/env python3
"""
Graph Sampling - sample tool chains from the tool graph.

Picks a structure based on `tool_count`:
- 1 tool: a single search/standalone tool
- 2 tools: a search->book pair
- 3 tools: chain walk, or a search->book pair plus an extra tool
- 4-6 tools: parallel search->book pairs (scenario template) or a chain walk
"""

import random
from typing import List, Dict, Optional
from dataclasses import dataclass
from enum import Enum

from scripts.task_gen.tool_graph import (
    TOOL_GRAPH,
    SEARCH_TOOLS,
    BOOK_TOOLS,
    STANDALONE_TOOLS,
    EdgeType,
    CHAIN_TEMPLATES,
)


class SampleType(Enum):
    NODE = "node"
    CHAIN = "chain"
    DAG = "dag"


@dataclass
class SampledGraph:
    """Sampling result."""
    sample_type: SampleType
    tools: List[str]
    structure: Dict


# ============================================================
# Core sampling methods
# ============================================================

def _sample_node() -> SampledGraph:
    """Sample a single tool."""
    # search 70%, standalone 30%
    if random.random() < 0.7:
        tool = random.choice(SEARCH_TOOLS)
    else:
        tool = random.choice(STANDALONE_TOOLS)
    return SampledGraph(
        sample_type=SampleType.NODE,
        tools=[tool],
        structure={"type": "node"}
    )


def _sample_search_book_pair() -> SampledGraph:
    """Sample one search->book pair."""
    search = random.choice(SEARCH_TOOLS)
    book = TOOL_GRAPH.get_search_book_pair(search)

    if book:
        return SampledGraph(
            sample_type=SampleType.CHAIN,
            tools=[search, book],
            structure={"type": "search_book_pair"}
        )
    else:
        return SampledGraph(
            sample_type=SampleType.NODE,
            tools=[search],
            structure={"type": "node"}
        )


def _sample_chain_walk(length: int) -> SampledGraph:
    """
    Generate a chain by random walking the graph.

    Starts from an arbitrary tool and follows dependency edges. When the walk
    cannot continue, splice in a new search tool.
    """
    graph = TOOL_GRAPH

    # Pick the starting tool: search 75%, standalone 25%.
    # Do not start from a book tool, otherwise _ensure_valid_chain will
    # prepend a search and exceed the target length.
    if random.random() < 0.75:
        current = random.choice(SEARCH_TOOLS)
    else:
        current = random.choice(STANDALONE_TOOLS)

    chain = [current]
    visited = {current}

    while len(chain) < length:
        downstream = graph.get_downstream(current, [EdgeType.RESOURCE, EdgeType.TEMPORAL])
        available = [t for t in downstream if t not in visited]

        if not available:
            # No downstream — splice in a new search or standalone tool
            remaining_searches = [s for s in SEARCH_TOOLS if s not in visited]
            remaining_standalone = [s for s in STANDALONE_TOOLS if s not in visited]

            if remaining_searches:
                current = random.choice(remaining_searches)
            elif remaining_standalone:
                current = random.choice(remaining_standalone)
            else:
                break
        else:
            current = random.choice(available)

        chain.append(current)
        visited.add(current)

    result = SampledGraph(
        sample_type=SampleType.CHAIN,
        tools=chain,
        structure={"type": "chain", "length": len(chain)}
    )
    result = _ensure_valid_chain(result)

    # Safe truncation: if _ensure_valid_chain prepended a search and overshot
    # the target length, trim from the end and re-ensure validity.
    if len(result.tools) > length:
        result.tools = result.tools[:length]
        result = _ensure_valid_chain(result)

    return result


def _sample_from_template(tool_count: int) -> Optional[SampledGraph]:
    """
    Sample parallel search->book pairs from a scenario template.

    Picks a template with enough branches based on tool_count.
    """
    # Determine how many search->book pairs are needed
    pairs_needed = tool_count // 2
    extra = tool_count % 2

    # Find matching templates with at least pairs_needed branches
    matching = []
    for name, branches in CHAIN_TEMPLATES.items():
        if len(branches) >= pairs_needed:
            matching.append((name, branches))

    if not matching:
        return None

    # Pick a template at random
    template_name, branches = random.choice(matching)

    # Take pairs_needed branches at random
    selected_branches = random.sample(branches, pairs_needed)

    # Flatten into a tool list
    tools = []
    for branch in selected_branches:
        tools.extend(branch)

    # If an extra tool is needed (odd tool_count)
    if extra > 0:
        # Add an unused standalone tool, or an unused search tool
        used = set(tools)
        candidates = [s for s in STANDALONE_TOOLS if s not in used]
        if not candidates:
            candidates = [s for s in SEARCH_TOOLS if s not in used]
        if candidates:
            tools.append(random.choice(candidates))

    return SampledGraph(
        sample_type=SampleType.DAG,
        tools=tools,
        structure={
            "type": "dag",
            "template": template_name,
            "pairs": pairs_needed,
        }
    )


def _sample_random_pairs(tool_count: int) -> SampledGraph:
    """
    Splice random search->book pairs together (no template).

    Fallback when no template fits.
    """
    pairs_needed = tool_count // 2
    extra = tool_count % 2

    # Pick pairs_needed distinct search->book pairs at random
    available_searches = list(SEARCH_TOOLS)
    random.shuffle(available_searches)

    tools = []
    used = set()

    for search in available_searches:
        if len(tools) // 2 >= pairs_needed:
            break
        book = TOOL_GRAPH.get_search_book_pair(search)
        if book and search not in used:
            tools.extend([search, book])
            used.add(search)
            used.add(book)

    # Fill in the extra tool
    if extra > 0:
        candidates = [s for s in STANDALONE_TOOLS if s not in used]
        if not candidates:
            candidates = [s for s in SEARCH_TOOLS if s not in used]
        if candidates:
            tools.append(random.choice(candidates))

    return SampledGraph(
        sample_type=SampleType.DAG,
        tools=tools,
        structure={"type": "random_pairs", "pairs": pairs_needed}
    )


# ============================================================
# Main sampling entry point
# ============================================================

def sample(tool_count: int = None) -> SampledGraph:
    """
    Main sampling entry point — picks a structure based on tool_count.

    Args:
        tool_count: target tool count (1-8)

    Returns:
        SampledGraph
    """
    if tool_count is None:
        tool_count = random.choice([2, 2, 3, 3, 3, 4])

    if tool_count == 1:
        return _sample_node()

    elif tool_count == 2:
        return _sample_search_book_pair()

    elif tool_count == 3:
        # 50% chain walk, 50% template/pairs + extra
        if random.random() < 0.5:
            return _sample_chain_walk(length=3)
        else:
            result = _sample_from_template(3)
            if result and len(result.tools) >= 3:
                return result
            return _sample_chain_walk(length=3)

    else:  # 4-6
        # 70% parallel pairs (DAG), 30% chain walk
        if random.random() < 0.7:
            result = _sample_from_template(tool_count)
            if result and len(result.tools) >= tool_count:
                return result
            # No template fits, splice random pairs
            return _sample_random_pairs(tool_count)
        else:
            return _sample_chain_walk(length=tool_count)


# ============================================================
# Tool chain validation
# ============================================================

def _ensure_valid_chain(sampled: SampledGraph) -> SampledGraph:
    """Ensure the chain is valid: every book tool is preceded by its matching search tool."""
    tools = sampled.tools
    graph = TOOL_GRAPH

    new_tools = []
    search_in_chain = set()

    for tool in tools:
        if graph.is_search_tool(tool):
            new_tools.append(tool)
            search_in_chain.add(tool)

        elif graph.is_book_tool(tool):
            required_search, _ = graph.get_resource_dependency(tool)
            if required_search and required_search not in search_in_chain:
                new_tools.append(required_search)
                search_in_chain.add(required_search)
            new_tools.append(tool)

        else:
            new_tools.append(tool)

    sampled.tools = new_tools
    return sampled


# ============================================================
# Tests
# ============================================================

if __name__ == "__main__":
    print("=" * 60)
    print("Graph Sampling tests")
    print("=" * 60)

    for tc in range(1, 7):
        print(f"\n--- tool_count={tc} (10 samples) ---")
        type_counts = {"node": 0, "chain": 0, "dag": 0}
        for i in range(10):
            s = sample(tool_count=tc)
            st = s.sample_type.value
            type_counts[st] = type_counts.get(st, 0) + 1
            print(f"  {i+1}. [{st:5s}] {s.tools}")

        print(f"  Structure distribution: {type_counts}")

    print(f"\n--- Bulk sampling statistics (200 samples, tool_count 2-6 uniform) ---")
    all_type_counts = {}
    all_length_counts = {}
    for _ in range(200):
        tc = random.randint(2, 6)
        s = sample(tool_count=tc)
        t = s.sample_type.value
        all_type_counts[t] = all_type_counts.get(t, 0) + 1
        l = len(s.tools)
        all_length_counts[l] = all_length_counts.get(l, 0) + 1

    print("  Structure distribution:")
    for t, c in sorted(all_type_counts.items()):
        print(f"    {t}: {c}")
    print("  Actual tool count distribution:")
    for l, c in sorted(all_length_counts.items()):
        print(f"    {l} tools: {c}")
