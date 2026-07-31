"""
Task Generation Pipeline

Sample tasks across the feature space to surface new failure modes.
"""

import hashlib
import json
import random
from typing import List, Dict


def transcript_hash(transcript: List[Dict]) -> str:
    """Compute a short hash of the transcript content for detecting data-version changes.

    Only the user turns' text is hashed; volatile fields like timestamps are ignored.
    """
    user_texts = [t.get("text", "") for t in transcript if t.get("speaker") == "user"]
    content = json.dumps(user_texts, ensure_ascii=False)
    return hashlib.sha256(content.encode()).hexdigest()[:12]


def add_timestamps(transcript: List[Dict], text_key: str = "text") -> List[Dict]:
    """Add simulated timestamps to each turn of the transcript.

    Estimates speech duration from text length and adds a random pause.
    Shared logic used by both proactive and reactive generation.

    Args:
        transcript: [{text_key: "...", ...}, ...]
        text_key: name of the text field ("text" for reactive, "content" for proactive internals)

    Returns:
        The transcript, mutated in place.
    """
    timestamp = 0.0
    for turn in transcript:
        turn["timestamp"] = timestamp
        text_len = len(turn.get(text_key, ""))
        timestamp += 2.0 + text_len * 0.05 + random.uniform(0.5, 1.5)
    return transcript
