#!/usr/bin/env python3
"""
Back-Instruct - reverse-generate a natural multi-turn transcript from a tool chain.

Pipeline:
1. Input: tool chain + parameters
2. Call an LLM to generate a natural conversation
3. Output: a multi-turn transcript
"""

import os
import json
import random
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass

from scripts.task_gen.tool_graph import TOOL_GRAPH, SEARCH_TOOLS, BOOK_TOOLS
from scripts.task_gen.reactive.graph_sampling import SampledGraph
from scripts.task_gen.param_engine import sample_params_for_chain

# Import mock_data
from eval.tools.mock_data import (
    FLIGHTS, TRAINS, HOTELS, RENTAL_CARS, RESTAURANTS, ATTRACTIONS,
    DELIVERY_RESTAURANTS, HOME_SERVICES, MOVIES, SHOWS, SPORTS_EVENTS,
    DOCTORS, MEDICINES, COURSES, BOOKS, PARKING_LOTS, BILLS
)

# Import OpenAI
try:
    from openai import OpenAI
    HAS_OPENAI = True
except ImportError:
    HAS_OPENAI = False


# ============================================================
# Transcript parameter verification
# ============================================================

# search tool → domain keywords that must appear in transcript
_TOOL_INTENT_KEYWORDS = {
    "search_cars": ["car", "rental", "rent", "drive", "vehicle"],
    "search_hotels": ["hotel", "stay", "accommodation", "room", "lodge"],
    "search_restaurants": ["restaurant", "eat", "dinner", "lunch", "dining", "food"],
    "search_restaurants_delivery": ["delivery", "deliver", "order food", "takeout", "takeaway"],
    "search_flights": ["flight", "fly", "plane", "airline", "airport"],
    "search_trains": ["train", "rail"],
    "search_movies": ["movie", "film", "cinema"],
    "search_shows": ["show", "concert", "theater", "theatre", "performance"],
    "search_sports_events": ["sport", "game", "match", "stadium"],
    "search_attractions": ["attraction", "visit", "sightseeing", "tour", "scenic"],
    "search_doctors": ["doctor", "medical", "appointment", "clinic", "health"],
    "search_home_services": ["clean", "service", "repair", "maintenance"],
    "search_parking": ["parking", "park", "garage"],
    "search_courses": ["course", "class", "learn", "enroll", "study"],
    "search_books": ["book", "read", "library", "borrow"],
}


def verify_transcript_params(
    transcript: List[Dict],
    expected_tools: List[Dict]
) -> Tuple[bool, List[str]]:
    """
    Verify that the transcript contains every parameter value in expected_tools.

    Returns:
        (is_valid, missing_params)
    """
    # Join all transcript text
    full_text = " ".join([turn.get("text", "") for turn in transcript]).lower()

    missing = []

    for tool_call in expected_tools:
        tool = tool_call["tool"]
        params = tool_call.get("params", {})

        for param_name, param_value in params.items():
            if param_value is None:
                continue

            # Skip complex fields
            if param_name in ["items", "note", "start_time", "delivery_address", "address"]:
                continue

            # Skip entity ID parameters (users would not say these IDs out loud)
            if param_name.endswith("_id"):
                continue

            # Skip boolean parameters (LLMs do not naturally say True/False)
            if isinstance(param_value, bool):
                continue

            # Skip long digit strings such as ID numbers
            if param_name in ["id_number"]:
                continue

            # Convert to string for checking
            value_str = str(param_value).lower()

            # Skip short non-digit values (likely noise)
            if len(value_str) < 2 and not value_str.isdigit():
                continue

            # Check whether the value appears in the transcript
            found = False

            # 1. Direct match
            if value_str in full_text:
                found = True

            # 2. Numeric values: ensure it appears as a standalone digit
            elif value_str.isdigit():
                import re
                # Match standalone numbers (not surrounded by other digits)
                if re.search(rf'(?<!\d){value_str}(?!\d)', full_text):
                    found = True

            # 3. Time values: 18:00 may be spoken as 6 PM / 6pm / 6:00 PM
            elif ":" in value_str and len(value_str) == 5 and value_str[:2].isdigit():
                try:
                    hour = int(value_str.split(":")[0])
                    minute = int(value_str.split(":")[1])
                    h12 = hour if hour <= 12 else hour - 12
                    period = "am" if hour < 12 else "pm"
                    time_formats = [
                        value_str,                          # 18:00
                        f"{h12} {period}",                  # 6 pm
                        f"{h12}{period}",                   # 6pm
                        f"{h12}:00 {period}",               # 6:00 pm
                        f"{h12}:{minute:02d} {period}",     # 6:00 pm
                    ]
                    if minute == 0:
                        time_formats.append(f"{h12} o'clock")  # 6 o'clock
                    for fmt in time_formats:
                        if fmt in full_text:
                            found = True
                            break
                except:
                    pass

            # 4. Date values: 2026-03-15 may be spoken as "March 15"
            elif "-" in value_str and len(value_str) == 10:
                try:
                    from datetime import datetime
                    date_obj = datetime.strptime(value_str, "%Y-%m-%d")
                    # Try multiple date formats
                    formats = [
                        date_obj.strftime("%B %d").lower(),  # March 15
                        date_obj.strftime("%B %-d").lower() if hasattr(date_obj, 'strftime') else None,  # March 15 (no leading zero)
                        date_obj.strftime("%d %B").lower(),  # 15 March
                        date_obj.strftime("%m/%d").lower(),  # 03/15
                        f"{date_obj.day}",  # just the day
                    ]
                    for fmt in formats:
                        if fmt and fmt in full_text:
                            found = True
                            break
                except:
                    pass

            if not found:
                missing.append(f"{tool}.{param_name}={param_value}")

    # Intent check: search tools must have domain keywords in transcript
    for tool_call in expected_tools:
        tool = tool_call["tool"]
        if not tool.startswith("search_"):
            continue
        keywords = _TOOL_INTENT_KEYWORDS.get(tool)
        if not keywords:
            continue
        if not any(kw in full_text for kw in keywords):
            missing.append(f"{tool}: no intent keywords found")

    return len(missing) == 0, missing


# ============================================================
# LLM call (OpenAI)
# ============================================================

def _call_llm(prompt: str, model: str = None) -> str:
    """
    Call the OpenAI LLM to generate text.

    Returns:
        The generated text content.
    """
    openai_key = os.environ.get("OPENAI_API_KEY")

    if not openai_key or not HAS_OPENAI:
        raise RuntimeError("No LLM API available. Set OPENAI_API_KEY and install openai package.")

    client = OpenAI(api_key=openai_key, base_url="https://us.api.openai.com/v1")
    response = client.chat.completions.create(
        model=model or "gpt-5.2",
        messages=[{"role": "user", "content": prompt}],
        temperature=0.7,
        timeout=60,
    )
    return response.choices[0].message.content


# ============================================================
# LLM transcript generation
# ============================================================

def generate_conversational_transcript(
    tools: List[str],
    params,  # List[Dict] or Dict[str, Dict] for backward compat
    use_llm: bool = True,
    model: str = "gpt-5.2"
) -> List[Dict]:
    """
    Generate a conversational transcript where the user reveals information gradually.

    Steps:
    1. Identify the required parameters for the first tool.
    2. Spread parameters across multiple user turns (1 parameter per turn).
    3. First turn: vague intent.
    4. Following turns: provide one parameter value at a time.

    Args:
        tools: list of tools
        params: parameters per tool
        use_llm: whether to use the LLM
        model: OpenAI model

    Returns:
        transcript with the user's gradual input only
    """
    if not use_llm:
        # Fallback: simple template
        return _generate_conversational_fallback(tools, params)

    # Collect parameters for every tool
    all_params = {}
    if isinstance(params, list):
        # New format: [{"tool": name, "params": {...}}, ...]
        for entry in params:
            tool = entry["tool"]
            for key, value in entry["params"].items():
                all_params[f"{tool}.{key}"] = value
    else:
        # Legacy format: {tool_name: params_dict}
        for tool in tools:
            tool_params_dict = params.get(tool, {})
            for key, value in tool_params_dict.items():
                all_params[f"{tool}.{key}"] = value

    # Build the description for each parameter
    param_list = []
    for i, (key, value) in enumerate(all_params.items(), 1):
        param_list.append(f"{i}. {key}: {value}")
    param_instructions = "\n".join(param_list)

    prompt = f"""Generate a natural, conversational transcript where the user gradually provides information across multiple turns. This simulates a voice assistant interaction.

## Tool Chain
The user wants to accomplish the following tasks (in order):
{', '.join(tools)}

## Parameters (ALL must appear in the transcript)
{param_instructions}

## Style Guidelines
1. **Natural spoken language**: The user is talking to a voice assistant, NOT typing commands
   - ✓ GOOD: "I'd like to see The Wandering Earth 3", "Book me a table at Chuanfu Laozao"
   - ✗ BAD: "movie_id: The Wandering Earth 3", "restaurant_id: Chuanfu Laozao"
   - NEVER expose parameter names or field names — speak naturally

2. **Gradual information**: Spread parameters across turns, 1-2 parameters per turn
   - Turn 1: Express intent vaguely
   - Following turns: Provide details one or two at a time

3. **Conversational flow**: Include natural transitions, context, follow-ups
   - "Oh and for the restaurant..." / "Actually, make that..." / "The name is..."
   - Can include brief context: "I'm planning a night out" / "We're visiting Shanghai"

4. **Self-contained**: When mentioning entities, use their names explicitly
   - ✓ "Book at the Hilton", "I want to see The Wandering Earth 3"
   - ✗ "Book that one", "the first result"

5. **No command phrases**: Avoid robotic language
   - ✗ AVOID: "Set parameter X to Y", "Update field Z"
   - ✓ USE: "for 4 people", "checking in on March 15th", "under the name Li Na"

## Output Format
Return a JSON array of user messages:
```json
[
  {{"speaker": "user", "text": "First message..."}},
  {{"speaker": "user", "text": "Second message..."}}
]
```

Generate now:"""


    try:
        content = _call_llm(prompt)

        # Parse JSON
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        else:
            json_str = content

        transcript = json.loads(json_str)

        # Filter out any assistant messages (in case the LLM emitted them by mistake)
        transcript = [turn for turn in transcript if turn.get("speaker") == "user"]

        # Strip any extra fields the LLM may have added
        for turn in transcript:
            turn.pop("contains_params", None)

        # Add timestamps (shared helper)
        from scripts.task_gen import add_timestamps
        add_timestamps(transcript)

        return transcript

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Content: {content[:500]}")
        raise RuntimeError(f"Failed to parse LLM response as JSON: {e}")
    except Exception as e:
        print(f"LLM API error: {e}")
        raise


def _get_required_params(tool: str) -> List[str]:
    """Return the list of required parameters for a tool (read from its schema)."""
    from scripts.task_gen.param_engine import get_tool_instance
    inst = get_tool_instance(tool)
    if inst:
        return inst.parameters.get("required", [])
    return []


# ============================================================
# LLM transcript generation (direct call)
# ============================================================

def call_gemini_for_transcript(
    tools: List[str],
    params,  # List[Dict] or Dict[str, Dict] for backward compat
    target_turns: int = None,
    model: str = "gpt-5.2",
    style: str = "conversational"
) -> List[Dict]:
    """
    Call the LLM to generate a transcript.

    Args:
        style: "direct" (imperative) or "natural" (conversational)
    """
    # Determine the target number of turns
    if target_turns is None:
        target_turns = 999

    # Build the prompt
    tool_chain_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(tools)])
    params_json = json.dumps(params, indent=2, ensure_ascii=False)

    # Pick a different prompt based on style
    if style == "direct":
        style_guidelines = """## Requirements - CRITICAL STYLE GUIDELINES
1. **Direct and imperative**: Use command-style language, NOT polite questions
   - ✓ GOOD: "Search for hotels in Beijing", "Book flight CA1234"
   - ✗ BAD: "Hi, could you help me search for hotels?", "Can you show me..."

2. **NO greetings or small talk**: Start directly with the task
   - ✗ AVOID: "Hi there", "Hello", "I'm planning a trip", "I'm staying in..."
   - ✓ START: "Search for...", "Find...", "Book...", "Show me..."

3. **High information density**: Pack multiple parameters into each turn
   - ✓ GOOD: "Search for flights from Beijing to Shanghai on March 15th, economy class"
   - ✗ BAD: Split into "I need a flight" + "From Beijing to Shanghai" + "On March 15th"

4. **Imperative verbs**: Use action verbs that match tool names
   - Use: "Search", "Book", "Find", "Reserve", "Show", "Get"
   - Avoid: "Could you", "Can you", "Would you", "Please help me"

5. Keep language concise and task-focused, like giving commands to an API"""
    else:  # natural
        style_guidelines = """## Requirements - CRITICAL STYLE GUIDELINES
1. **Natural conversation**: Use polite, conversational language
   - ✓ GOOD: "Hi, I'm looking to book a hotel in Beijing", "Could you help me find flights?"
   - Include greetings, context, and polite phrases

2. **Conversational flow**: Make it sound like a real user talking to an assistant
   - Can include: "Hi there", "I'm planning...", "I need help with..."
   - Use questions: "Can you show me...", "Could you help me..."

3. **Natural information distribution**: Spread information across turns naturally
   - It's OK to provide context first, then details
   - Example: "I'm in Beijing" → "I need a hotel" → "For 2 people, checking in tomorrow"

4. **Polite and friendly**: Use natural language patterns
   - Use: "Could you", "Can you", "I'd like to", "Please help me"
   - Include context and reasoning when natural"""

    prompt = f"""You need to generate a conversation for a voice assistant tool-calling scenario.

## Tool Chain
The user wants to accomplish the following tasks (in order):
{tool_chain_str}

## Parameters
The conversation must include ALL of these parameter values:
{params_json}

{style_guidelines}

## Common Requirements (for both styles)
1. Split information across {target_turns} turns

2. Each turn should be a user message only (no assistant responses needed)

3. Include ALL parameter values from above - don't miss any

4. CRITICAL - Transcript must be SELF-CONTAINED:
   - When booking/selecting an entity, user MUST explicitly mention identifying features
   - Examples: "Book the Hilton Hotel", "Book flight CA1234 at 8am", "Book train G1"
   - NEVER use vague references like "this one", "the first one", "that hotel"
   - The transcript must be understandable without knowing search results

5. AVOID vague time/location references - use exact times/locations from parameters

6. CRITICAL - When splitting a booking across multiple turns, use ADDITIVE phrasing:
   - ✓ GOOD: "Book hotel X for guest Y" → "Check in on March 15th for 3 nights"
   - ✗ BAD: "Book hotel X" → "Update the check-in date to March 15th" → "Set the nights to 3"
   - Words like "update", "change", "modify", "set" imply changing an existing record
   - Instead use natural phrasing: "for 3 nights", "checking in March 15th", "party of 5"

## Output Format
Return a JSON array of user messages:
```json
[
  {{"speaker": "user", "text": "First message..."}},
  {{"speaker": "user", "text": "Second message..."}}
]
```

Generate the conversation now:"""

    try:
        content = _call_llm(prompt)

        # Parse JSON
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        else:
            json_str = content

        transcript = json.loads(json_str)

        # Add timestamps (shared helper)
        from scripts.task_gen import add_timestamps
        add_timestamps(transcript)

        return transcript

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Content: {content[:500]}")
        return []
    except Exception as e:
        print(f"LLM API error: {e}")
        return []


BACK_INSTRUCT_PROMPT = """You need to generate a direct, task-oriented conversation for a voice assistant tool-calling scenario.

## Tool Chain
The user wants to accomplish the following tasks (in order):
{tool_chain}

## Parameters
The conversation must include ALL of these parameter values:
{params_json}

## Requirements - CRITICAL STYLE GUIDELINES
1. **Direct and imperative**: Use command-style language, NOT polite questions
   - ✓ GOOD: "Search for hotels in Beijing", "Book flight CA1234"
   - ✗ BAD: "Hi, could you help me search for hotels?", "Can you show me..."

2. **NO greetings or small talk**: Start directly with the task
   - ✗ AVOID: "Hi there", "Hello", "I'm planning a trip", "I'm staying in..."
   - ✓ START: "Search for...", "Find...", "Book...", "Show me..."

3. **High information density**: Pack multiple parameters into each turn
   - ✓ GOOD: "Search for flights from Beijing to Shanghai on March 15th, economy class"
   - ✗ BAD: Split into "I need a flight" + "From Beijing to Shanghai" + "On March 15th"

4. **Imperative verbs**: Use action verbs that match tool names
   - Use: "Search", "Book", "Find", "Reserve", "Show", "Get"
   - Avoid: "Could you", "Can you", "Would you", "Please help me"

5. Split information across {target_turns} turns, but keep each turn information-dense

6. Each turn should be a user message only (no assistant responses needed)

7. Include ALL parameter values from above - don't miss any

8. CRITICAL - Transcript must be SELF-CONTAINED:
   - When booking/selecting an entity, user MUST explicitly mention identifying features
   - Examples: "Book the Hilton Hotel", "Book flight CA1234 at 8am", "Book train G1"
   - NEVER use vague references like "this one", "the first one", "that hotel"
   - The transcript must be understandable without knowing search results

9. AVOID vague time/location references - use exact times/locations from parameters

10. Keep language concise and task-focused, like giving commands to an API

11. CRITICAL - When splitting a booking across multiple turns, use ADDITIVE phrasing:
   - ✓ GOOD: "Book hotel X for guest Y" → "Check in on March 15th for 3 nights"
   - ✗ BAD: "Book hotel X for guest Y" → "Update the check-in date to March 15th" → "Set the nights to 3"
   - Words like "update", "change", "modify", "set" imply changing an existing record
   - Use natural additive phrasing: "for 3 nights", "checking in March 15th", "party of 5"

## Output Format
Return a JSON array of user messages:
```json
[
  {{"speaker": "user", "text": "First message..."}},
  {{"speaker": "user", "text": "Second message..."}},
  ...
]
```

Generate the conversation now:"""


def call_llm_for_transcript(
    tools: List[str],
    params: Dict[str, Dict],
    target_turns: int = None,
    model: str = "gpt-4o-mini"
) -> List[Dict]:
    """
    Call the LLM to generate a transcript.

    Args:
        tools: tool list
        params: parameters per tool
        target_turns: target number of turns
        model: model name
    """
    if not HAS_OPENAI:
        raise RuntimeError("OpenAI package not installed")

    api_key = os.environ.get("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY not set")

    client = OpenAI(api_key=api_key)

    # Determine the target number of turns
    if target_turns is None:
        target_turns = len(tools) + random.randint(1, 3)

    # Build the prompt
    tool_chain_str = "\n".join([f"{i+1}. {t}" for i, t in enumerate(tools)])
    params_json = json.dumps(params, indent=2, ensure_ascii=False)

    prompt = BACK_INSTRUCT_PROMPT.format(
        tool_chain=tool_chain_str,
        params_json=params_json,
        target_turns=target_turns
    )

    # Call the LLM
    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": "You are a helpful assistant that generates natural conversation data."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.7,
        max_tokens=2000,
    )

    content = response.choices[0].message.content

    # Parse JSON
    try:
        # Try to extract the JSON section
        if "```json" in content:
            json_str = content.split("```json")[1].split("```")[0]
        elif "```" in content:
            json_str = content.split("```")[1].split("```")[0]
        else:
            json_str = content

        transcript = json.loads(json_str)

        # Add timestamps (shared helper)
        from scripts.task_gen import add_timestamps
        add_timestamps(transcript)

        return transcript

    except json.JSONDecodeError as e:
        print(f"JSON parse error: {e}")
        print(f"Content: {content}")
        return []


# ============================================================
# Proactive style support
# ============================================================

PROACTIVE_STYLES = {
    # v7 official styles
    "proactive_strong":    "strong",
    "proactive_ambiguous": "ambiguous",  # v7: replaces the old "medium" and covers the hedged-to-tentative spectrum
    "proactive_negative":  "negative",   # v7: renamed (formerly "proactive_weak", which was actually negative)
    # legacy aliases (kept for backward compatibility with old generation commands)
    "proactive_medium":    "ambiguous",
    "proactive_weak":      "negative",
    "conversational":      "reactive",
}

_PROACTIVE_FEW_SHOT = """
## Few-shot examples

### Example 1: STRONG — narrative self-report (no execution authorization)
The user reports their own confirmed plans naturally with all parameters surfaced.
NEVER includes execution verbs like "go ahead", "book it", "reserve it".
```json
{
  "turns": [
    {"content": "Tomorrow I'm flying out of Beijing for that Shanghai client meeting on March 20th. Name's under John for the travel.", "phase": "search"},
    {"content": "I'm staying at the Hilton near the Bund, three nights, checking in the 20th, two of us.", "phase": "search"},
    {"content": "And dinner that Friday at the Sichuan place in Xintiandi, March 21st around 7 PM, four of us, Lisa's name, 138-1234-5678.", "phase": "search"}
  ],
  "signals": ["I'm flying out", "I'm staying at the Hilton", "checking in the 20th", "Lisa's name"],
  "ambiguity_notes": "Strong — user narrates their own confirmed plans. All parameters surface naturally. No request to AI, no authorization verbs."
}
```

### Example 2: AMBIGUOUS — overall hedging frame, parameters embedded as details
The user thinks out loud about plans they're considering but haven't decided.
Overall hedge frame ("Been thinking about...") + parameters embed naturally.
Ends with hesitation marker ("Not sure if I'll actually do this").
```json
{
  "turns": [
    {"content": "Work's been crazy. Been kind of thinking about a Shanghai trip next week, maybe the 20th if I can swing it. Probably under John's name.", "phase": "search"},
    {"content": "Maybe stay near the Bund — Hilton-ish for like 3 nights, the 20th through 22nd-ish, two of us I guess.", "phase": "search"},
    {"content": "And dinner one of those nights at that Sichuan place in Xintiandi, the 21st, 4 of us around 7, under Lisa, 138-1234-5678. Not sure if I'll actually pull this off.", "phase": "search"}
  ],
  "signals": ["kind of thinking about", "if I can swing it", "Probably", "Maybe", "Hilton-ish", "I guess", "Not sure if I'll actually"],
  "ambiguity_notes": "Ambiguous — overall hedged frame, parameters as natural details, ends with hesitation marker."
}
```

### Example 3: NEGATIVE — past tense reminiscence (no current intent)
The user recounts past events / third-party plans / hypothetical scenarios.
ALL dates in the past (2024 or 2025), past tense throughout.
NEVER expresses current first-person intent.
```json
{
  "turns": [
    {"content": "Last March I had this last-minute Shanghai trip — flew out of Beijing on the 20th, my boss had me running everywhere. John handled the booking.", "phase": "none"},
    {"content": "Stayed at the Hilton near the Bund, three nights, two of us — colleague set the whole thing up.", "phase": "none"},
    {"content": "Had dinner at the Sichuan place in Xintiandi on the 21st, 4 of us around 7 PM, Lisa's reservation, her number was 138-1234-5678. Good times.", "phase": "none"}
  ],
  "signals": [],
  "ambiguity_notes": "Negative — past tense (2025), all bookings already done by others. No current action implied."
}
```

CRITICAL: NEVER use these execution verbs in any example or generated transcript:
"go ahead", "do it", "book it", "lock in", "reserve it", "let's do it", "please book",
"帮我", "请帮", "下单", "预订"
"""


def _build_reactive_prompt(
    tool_params: List[Dict],
    target_turns: int,
) -> str:
    """Build simple reactive prompt — based on original conversational prompt, aligned on density/format."""
    tools = [tp["tool"] for tp in tool_params]

    # Flat param list (same as original reactive)
    param_list = []
    for tp in tool_params:
        for k, v in tp["params"].items():
            param_list.append(f"  {tp['tool']}.{k}: {v}")
    param_instructions = "\n".join(param_list)

    return f"""Generate a natural, conversational transcript where the user gives clear commands to a voice assistant.

## Tool Chain
The user wants to accomplish the following tasks (in order):
{', '.join(tools)}

## Parameters (ALL must appear in the transcript)
{param_instructions}

## Style Guidelines
1. **Natural spoken language**: Talk to a voice assistant naturally
   - ✓ GOOD: "I'd like to see The Wandering Earth 3", "Book me a table at Chuanfu Laozao"
   - ✗ BAD: "movie_id: The Wandering Earth 3", "restaurant_id: Chuanfu Laozao"
   - NEVER expose parameter names or field names — speak naturally

2. **Direct and clear**: The user knows what they want
   - Use action verbs: "Search for", "Book", "Find", "Reserve"
   - NO greetings or small talk — start directly with the task
   - Complete one task before moving to the next

3. **Spread parameters across turns**: At most 3 new parameters per turn
   - "Oh and for the restaurant..." / "The name is..." / "Phone number is..."

4. **Self-contained**: When mentioning entities, use their names explicitly
   - ✓ "Book at the Hilton", "I want to see The Wandering Earth 3"
   - ✗ "Book that one", "the first result"

5. **Additive phrasing**: Don't say "update" or "change"
   - ✓ "for 3 nights", "checking in March 15th", "under the name Li Na"
   - ✗ "Update the check-in date to March 15th", "Set the nights to 3"

## Output Format
Return a JSON object:
```json
{{
  "turns": [
    {{"content": "User message...", "contains_params": ["tool.param=value"], "phase": "search"}},
    {{"content": "User message...", "contains_params": ["tool.param=value"], "phase": "book"}}
  ]
}}
```

Rules:
1. Generate exactly {target_turns} user turns
2. ALL parameter values must appear naturally
3. Each turn: at most 3 new parameter values
4. Mark phase: "search" or "book" based on which tool the turn's parameters belong to
5. Search parameters must appear in EARLIER turns than book parameters
6. contains_params: use "tool_name.param_name=value" format

Generate now:"""


def _build_proactive_prompt(
    tool_params: List[Dict],
    intent_strength: str,
    target_turns: int,
) -> str:
    """Build proactive conversation generation prompt."""
    search_section = []
    book_section = []
    all_param_checklist = []

    for tp in tool_params:
        tool = tp["tool"]
        params = tp["params"]
        is_book = tool in BOOK_TOOLS

        if is_book:
            pj = json.dumps(params, indent=2, ensure_ascii=False)
            book_section.append(f"Book Tool: {tool}\nUser-specified parameters:\n{pj}")
            for k, v in params.items():
                label = f"{tool}.{k}={v}"
                if not any(f".{k}={v}" in p for p in all_param_checklist):
                    all_param_checklist.append(label)
        else:
            pj = json.dumps(params, indent=2, ensure_ascii=False)
            search_section.append(f"Tool: {tool}\nParameters:\n{pj}")
            for k, v in params.items():
                all_param_checklist.append(f"{tool}.{k}={v}")

    tools_text = "\n\n".join(search_section + book_section)
    checklist = "\n".join(f"  - {p}" for p in all_param_checklist)
    tool_names = ", ".join(tp["tool"] for tp in tool_params if tp["tool"] not in BOOK_TOOLS)
    n_books = sum(1 for tp in tool_params if tp["tool"] in BOOK_TOOLS)

    if intent_strength == "strong":
        style_guide = """## Intent Strength: STRONG
The user reports their own plans naturally — like thinking out loud or recounting upcoming events to a friend.
All parameters surface naturally as part of the narrative.

- Style: narrative self-statement, NOT a request to AI
- Each turn can mention multiple parameters as natural details
- Tense: present or future tense (current plans, upcoming events)
- The transcript ends mid-thought or transitions to next topic
- NEVER use execution verbs: "go ahead", "do it", "book it", "reserve it", "lock in", "let's do it",
  "please book", "search for", "find me", "I need you to", "帮我", "请帮", "下单", "预订"
- Phrasing examples: "Tomorrow I'm flying...", "I'm staying at...", "We're getting dinner at..."
- The user has decided and is reporting; they have NOT asked the AI to do anything"""
    elif intent_strength == "ambiguous":
        style_guide = """## Intent Strength: AMBIGUOUS
The user thinks out loud about plans they're considering but haven't decided.

- Use overall hedging frame: "Been thinking about...", "Maybe I'll...", "Kind of considering..."
- Parameters embed as natural details inside the hedged narrative
  (do NOT hedge every single parameter individually — that sounds unnatural)
- End with a hesitation marker: "Not sure if I'll actually do this", "We'll see", "Probably won't pull this off"
- NEVER use execution verbs (no "go ahead", "book it", "reserve it", etc.)
- Style: tentative planning, considering options, still on the fence
- Tense: present/future, but with hedge modals ("maybe", "might", "probably")"""
    else:  # negative
        style_guide = """## Intent Strength: NEGATIVE
The user recounts past events, third-party plans, or hypothetical scenarios — NO current intent.
The AI should NOT call any tools.

- Spread parameter values across turns in non-actionable contexts
- Use: past tense throughout ("Last year I went...", "We stayed at..."), or quote others ("My friend booked..."),
  or hypotheticals ("If I had time, I'd..."), or already-completed actions
- ALL parameter values should appear but context must make it clear NO help is needed
- CRITICAL: All dates are in 2024 or 2025 (the past). User is recounting past events, NOT planning future ones
- NEVER express current first-person intent
- Frame everything as already done: "I went to...", "We stayed at...", "My friend booked..."
- Do NOT include any booking confirmation turns"""

    # v7: proactive tasks never inject a booking confirmation.
    # The old logic `if n_books > 0 and intent_strength != "weak"` forced strong/medium
    # to inject execution commands like "yeah go ahead" / "reserve it" — this was the
    # root cause of v2 data containing execution verbs 100% of the time.
    # Tasks containing execution commands are by definition reactive, not proactive.
    book_inst = ""

    prompt = f"""You need to generate a multi-turn casual conversation for a proactive voice assistant benchmark.

## Task
Generate a {target_turns}-turn conversation where the user gradually reveals information related to: {tool_names}.
Each turn is a user message (assistant responses are implied — do NOT generate them).

## Tools and Parameters
{tools_text}

## Parameter Checklist (ALL must appear across the turns)
{checklist}

{style_guide}
{book_inst}

## Multi-tool Note
Shared parameters (like city) only need to be mentioned once.
Do NOT list needs one by one — weave everything into a natural story.

{_PROACTIVE_FEW_SHOT}

## Output Format
Return a JSON object:
```json
{{
  "turns": [
    {{"content": "User message...", "contains_params": ["tool_name.param=value"], "phase": "search"}},
    {{"content": "Confirmation...", "contains_params": [], "phase": "book_confirm"}}
  ],
  "signals": ["key phrases indicating intent"],
  "ambiguity_notes": "Brief note on intent level"
}}
```

Rules:
1. Generate exactly {target_turns} user turns
2. ALL parameter values must appear naturally
3. Each turn: at most 3 new parameter values
4. English, casual spoken style
5. No command phrases: "search for", "find me", "I need you to", "can you look up"
6. Mark phase: "search", "book_confirm", or "none" (negative)
7. CRITICAL: Search parameters (city, origin, destination) must appear in EARLIER turns than book parameters (entity name, buyer_name, etc.). Never put search and book info in the same turn.
8. contains_params MUST use "tool_name.param_name=value" format (e.g. "search_hotels.city=Shanghai", "book_hotel.guest_name=Li Na"). Every param from the checklist must appear in exactly one turn.

Generate the conversation now:"""

    return prompt


def _generate_proactive_transcript(
    tool_params: List[Dict],
    expected_tools: List[Dict],
    intent_strength: str,
    model: str = "gpt-5.2",
    max_retries: int = 3,
    verify_params: bool = True,
) -> Tuple[Optional[List[Dict]], Optional[Dict]]:
    """
    Generate transcript with unified prompt (reactive + proactive).

    Returns:
        (transcript, intent_meta) or (None, None) on failure
    """
    from scripts.task_gen import add_timestamps

    is_reactive = (intent_strength == "reactive")

    # Calculate target turns
    n_params = sum(
        len([k for k, v in tp["params"].items() if v is not None])
        for tp in tool_params
    )
    n_books = sum(1 for tp in tool_params if tp["tool"] in BOOK_TOOLS)
    # +1: reactive needs room for search/book boundaries; proactive for book_confirm
    target_turns = max(3, (n_params + 2) // 3 + 1)

    # Negative tasks: replace 2026 dates with 2025 (past events)
    if intent_strength == "negative":
        import copy
        tool_params = copy.deepcopy(tool_params)
        for tp in tool_params:
            for k, v in tp["params"].items():
                if isinstance(v, str) and "2026-" in v:
                    tp["params"][k] = v.replace("2026-", "2025-")

    if is_reactive:
        prompt = _build_reactive_prompt(tool_params, target_turns)
    else:
        prompt = _build_proactive_prompt(tool_params, intent_strength, target_turns)

    # Proactive forbids command phrases; reactive allows them
    # v7: expanded the forbidden execution-verb list to cover every verb from the v2 bug
    forbidden = [] if is_reactive else [
        # search-style imperatives
        "search for", "find me", "i need you to",
        "can you look up", "please find", "please search",
        # v7: booking-style execution verbs (root cause of the v2 bug)
        "go ahead", "do it", "book it", "lock in",
        "reserve it", "let's do it", "please book",
        "帮我", "请帮", "下单", "预订",
    ]

    for attempt in range(max_retries):
        try:
            content = _call_llm(prompt, model)

            if "```json" in content:
                json_str = content.split("```json")[1].split("```")[0]
            elif "```" in content:
                json_str = content.split("```")[1].split("```")[0]
            else:
                json_str = content

            result = json.loads(json_str)

            if "turns" not in result or not result["turns"]:
                print(f"  Attempt {attempt+1}: missing turns")
                continue

            turns = result["turns"]

            if not all(isinstance(t, dict) and t.get("content", "").strip() for t in turns):
                print(f"  Attempt {attempt+1}: empty content in turns")
                continue

            if len(turns) < 2:
                print(f"  Attempt {attempt+1}: too few turns ({len(turns)})")
                continue

            # Command phrase check (proactive only)
            if forbidden:
                all_text = " ".join(t["content"] for t in turns).lower()
                if any(f in all_text for f in forbidden):
                    print(f"  Attempt {attempt+1}: contains command phrases, retrying")
                    continue

            # v7: all proactive variants skip the book_confirm check — never explicitly
            # authorizing execution is precisely what makes a task proactive.
            # The old logic `not in ("weak", "reactive")` forced strong/medium to have a
            # book_confirm turn (paired with the now-removed book_inst injection); part of the v2 bug.
            # Reactive also does not need it: the reactive prompt uses phase=book, not book_confirm.
            pass  # No book_confirm requirement

            # No overloaded turns (LLM annotation is approximate; compute_contains_params rewrites later)
            if any(len(t.get("contains_params", [])) > 5 for t in turns):
                print(f"  Attempt {attempt+1}: overloaded turn")
                continue

            # Convert to standard transcript format
            transcript = []
            for turn in turns:
                entry = {"speaker": "user", "text": turn["content"]}
                metadata = {}
                if turn.get("phase"):
                    metadata["phase"] = turn["phase"]
                if turn.get("contains_params"):
                    metadata["contains_params"] = turn["contains_params"]
                if metadata:
                    entry["metadata"] = metadata
                transcript.append(entry)

            add_timestamps(transcript)

            # Verify params
            if verify_params:
                is_valid, missing = verify_transcript_params(transcript, expected_tools)
                if not is_valid:
                    print(f"  Attempt {attempt+1}: Missing params: {missing[:3]}...")
                    continue

            intent_meta = {
                "strength": intent_strength,
                "signals": result.get("signals", []),
                "ambiguity_notes": result.get("ambiguity_notes"),
            }

            return transcript, intent_meta

        except json.JSONDecodeError as e:
            print(f"  Attempt {attempt+1}: JSON parse error: {e}")
        except Exception as e:
            print(f"  Attempt {attempt+1}: LLM error: {e}")

    return None, None


# ============================================================
# Main entry point
# ============================================================

def back_instruct(
    sampled_graph: SampledGraph,
    use_llm: bool = True,
    model: str = "gpt-5.2",
    max_retries: int = 3,
    verify_params: bool = True,
    style: str = "conversational",
) -> Tuple[List[Dict], List[Dict], Optional[Dict]]:
    """
    Produce a transcript and expected_tools from a sampled tool graph.

    Args:
        sampled_graph: sampling result
        use_llm: whether to use the LLM
        model: OpenAI model (default gpt-5.2)
        max_retries: maximum retries when validation fails
        verify_params: whether to verify that every parameter appears in the transcript
        style: "direct", "natural", "conversational", or "proactive_strong/medium/weak"

    Returns:
        (transcript, expected_tools, intent_meta)
        - intent_meta is None for reactive styles, a dict for proactive styles
    """
    tools = sampled_graph.tools

    # 1. Sample parameters
    tool_params, expected_tools = sample_params_for_chain(tools)

    # 2. Unified generation (reactive + proactive)
    if style in PROACTIVE_STYLES:
        if not use_llm:
            raise RuntimeError("Task generation requires LLM (use --use-llm and set OPENAI_API_KEY)")
        intent_strength = PROACTIVE_STYLES[style]
        transcript, intent_meta = _generate_proactive_transcript(
            tool_params, expected_tools, intent_strength, model, max_retries, verify_params
        )
        if transcript is None:
            raise RuntimeError(f"Failed to generate transcript after {max_retries} attempts")
        return transcript, expected_tools, intent_meta

    raise RuntimeError(f"Unknown style: {style}. Use conversational/proactive_strong/proactive_medium/proactive_weak")


# ============================================================
# Tests
# ============================================================

if __name__ == "__main__":
    from scripts.task_gen.reactive.graph_sampling import sample

    print("=" * 60)
    print("Transcript Generator tests")
    print("=" * 60)

    # Parameter sampling test
    print("\n--- Parameter sampling test ---")
    tools = ["search_hotels", "book_hotel", "search_restaurants", "book_restaurant"]
    tool_params, expected_tools = sample_params_for_chain(tools)

    print(f"Tools: {tools}")
    print(f"\nExpected Tools:")
    for et in expected_tools:
        print(f"  {et['tool']}: {json.dumps(et['params'], ensure_ascii=False)}")

    # Run the full pipeline (requires OPENAI_API_KEY)
    if os.environ.get("OPENAI_API_KEY"):
        print("\n--- LLM transcript generation ---")
        sampled = sample(sample_type="chain", tool_count=3)
        print(f"Sampled tools: {sampled.tools}")

        transcript, expected, _ = back_instruct(sampled, use_llm=True)
        print(f"\nTranscript ({len(transcript)} turns):")
        for turn in transcript:
            print(f"  [{turn['timestamp']:.1f}s] {turn['text']}")

        print(f"\nExpected Tools:")
        for et in expected:
            print(f"  {et['tool']}: {json.dumps(et['params'], ensure_ascii=False)}")
    else:
        print("\n(skipping LLM test, OPENAI_API_KEY not set)")
