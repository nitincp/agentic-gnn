from abc import ABC, abstractmethod
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage
from pydantic import BaseModel


class AgentOutput(BaseModel):
    content: str
    confidence: float  # 0.0 - 1.0
    graph_writes: list[dict[str, Any]] = []
    requires_council: bool = False


class BaseAgent(ABC):
    """Base class for all council agents. Lazy-initialized on first invoke."""

    name: str
    persona: str

    def __init__(self) -> None:
        self._initialized = False
        self._history: list[BaseMessage] = []

    def _ensure_initialized(self) -> None:
        if not self._initialized:
            self._history = [SystemMessage(content=self.persona)]
            self._initialized = True

    @abstractmethod
    async def invoke(self, message: str, context: dict[str, Any]) -> AgentOutput:
        """Process a message with graph context, return structured output."""
        ...

    def reset(self) -> None:
        self._initialized = False
        self._history = []
