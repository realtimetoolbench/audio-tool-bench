"""
Trace recording and output.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
import json


@dataclass
class TraceStep:
    """Record for a single execution step."""
    step_id: int
    timestamp: float  # scenario timestamp in seconds
    input_chunk: Dict[str, Any]  # user input
    assistant_response: Optional[str] = None  # final reply
    llm_calls: List[Dict[str, Any]] = field(default_factory=list)  # all LLM calls
    tool_executions: List[Dict[str, Any]] = field(default_factory=list)  # all tool executions
    total_latency_ms: Optional[float] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "step_id": self.step_id,
            "timestamp": self.timestamp,
            "input_chunk": self.input_chunk,
            "assistant_response": self.assistant_response,
            "llm_calls": self.llm_calls,
            "tool_executions": self.tool_executions,
            "total_latency_ms": self.total_latency_ms,
            "metadata": self.metadata
        }


@dataclass
class Trace:
    """A complete execution trace."""
    task_name: str
    start_time: str
    end_time: Optional[str] = None
    steps: List[TraceStep] = field(default_factory=list)
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)  # full conversation history
    summary: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def add_step(self, step: TraceStep):
        """Append a step."""
        self.steps.append(step)

    def finalize(self):
        """Finalize the trace and compute summary stats."""
        self.end_time = datetime.now().isoformat()
        total_tool_calls = sum(len(step.tool_executions) for step in self.steps)
        total_llm_calls = sum(len(step.llm_calls) for step in self.steps)

        self.summary = {
            "total_steps": len(self.steps),
            "total_llm_calls": total_llm_calls,
            "total_tool_calls": total_tool_calls,
        }

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dict."""
        return {
            "task_name": self.task_name,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "steps": [step.to_dict() for step in self.steps],
            "conversation_history": self.conversation_history,
            "summary": self.summary,
            "metadata": self.metadata
        }

    def save_to_file(self, filepath: str):
        """Save to a JSON file."""
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)
