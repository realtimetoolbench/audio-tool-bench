"""
Task data structures.
"""
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from enum import Enum


class MessageRole(Enum):
    """Message role."""
    USER = "user"
    ASSISTANT = "assistant"
    SYSTEM = "system"


@dataclass
class TranscriptChunk:
    """A single conversation chunk."""
    role: MessageRole
    content: str
    timestamp: float  # relative time (seconds)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "role": self.role.value,
            "content": self.content,
            "timestamp": self.timestamp,
            "metadata": self.metadata
        }


@dataclass
class Task:
    """A complete test task."""
    name: str
    description: str
    chunks: List[TranscriptChunk]
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "description": self.description,
            "chunks": [chunk.to_dict() for chunk in self.chunks],
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Task":
        """Build a task from a dict. Accepts both `chunks` and `transcript` formats."""
        # Supports two formats: chunks (role/content) and transcript (speaker/text)
        if "chunks" in data:
            chunks = [
                TranscriptChunk(
                    role=MessageRole(chunk["role"]),
                    content=chunk["content"],
                    timestamp=chunk["timestamp"],
                    metadata=chunk.get("metadata", {})
                )
                for chunk in data["chunks"]
            ]
        elif "transcript" in data:
            # Convert transcript format to chunks format.
            # Unified format: {speaker, text, timestamp, metadata?}
            # Legacy format: {turn_id, content, audio_path, eval_this_turn}
            chunks = []
            for item in data["transcript"]:
                if "speaker" in item:
                    chunks.append(TranscriptChunk(
                        role=MessageRole(item["speaker"]),
                        content=item["text"],
                        timestamp=item.get("timestamp", 0.0),
                        metadata=item.get("metadata", {}),
                    ))
                elif "content" in item:
                    # Legacy proactive format (compat).
                    chunks.append(TranscriptChunk(
                        role=MessageRole.USER,
                        content=item["content"],
                        timestamp=item.get("timestamp", 0.0),
                        metadata={
                            "turn_id": item.get("turn_id"),
                            "eval_this_turn": item.get("eval_this_turn", False),
                        },
                    ))
        else:
            raise ValueError("Task must have either 'chunks' or 'transcript' field")

        return cls(
            name=data.get("name", data.get("task_id", "unknown")),
            description=data["description"],
            chunks=chunks,
            metadata=data.get("metadata", {})
        )
