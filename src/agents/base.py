import logging
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from langchain_core.messages import BaseMessage, SystemMessage
from pydantic import BaseModel

_usage_log = logging.getLogger("council.usage")
logging.basicConfig(format="%(asctime)s %(name)s %(message)s", level=logging.INFO)

# Sonnet pricing per million tokens (update if model changes)
_PRICE_INPUT = 3.00
_PRICE_OUTPUT = 15.00
_PRICE_CACHE_READ = 0.30
_PRICE_CACHE_WRITE = 3.75


@dataclass
class TokenUsage:
    agent: str
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    @property
    def cost_usd(self) -> float:
        return (
            self.input_tokens * _PRICE_INPUT
            + self.output_tokens * _PRICE_OUTPUT
            + self.cache_read_tokens * _PRICE_CACHE_READ
            + self.cache_write_tokens * _PRICE_CACHE_WRITE
        ) / 1_000_000


@dataclass
class SessionUsage:
    turns: list[TokenUsage] = field(default_factory=list)

    def add(self, usage: TokenUsage) -> None:
        self.turns.append(usage)

    @property
    def total_cost_usd(self) -> float:
        return sum(t.cost_usd for t in self.turns)

    @property
    def total_input(self) -> int:
        return sum(t.input_tokens for t in self.turns)

    @property
    def total_output(self) -> int:
        return sum(t.output_tokens for t in self.turns)

    def summary(self) -> str:
        lines = [
            f"`{'Agent':<20} {'In':>6} {'Out':>6} {'$':>7}`",
        ]
        for t in self.turns:
            lines.append(  # noqa: E501
                f"`{t.agent:<20} {t.input_tokens:>6} {t.output_tokens:>6} ${t.cost_usd:>6.4f}`"
            )
        total_line = f"`{'TOTAL':<20} {self.total_input:>6} {self.total_output:>6} ${self.total_cost_usd:>6.4f}`"  # noqa: E501
        lines.append(total_line)
        return "\n".join(lines)


class AgentOutput(BaseModel):
    content: str
    confidence: float  # 0.0 - 1.0
    graph_writes: list[dict[str, Any]] = []
    requires_council: bool = False
    usage: TokenUsage | None = None

    class Config:
        arbitrary_types_allowed = True


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

    def _log_usage(self, usage: Any) -> TokenUsage:
        tu = TokenUsage(
            agent=self.name,
            input_tokens=getattr(usage, "input_tokens", 0),
            output_tokens=getattr(usage, "output_tokens", 0),
            cache_read_tokens=getattr(usage, "cache_read_input_tokens", 0),
            cache_write_tokens=getattr(usage, "cache_creation_input_tokens", 0),
        )
        _usage_log.info(
            "[%s] in=%d out=%d cache_r=%d cache_w=%d cost=$%.4f",
            tu.agent,
            tu.input_tokens,
            tu.output_tokens,
            tu.cache_read_tokens,
            tu.cache_write_tokens,
            tu.cost_usd,
        )
        return tu

    @abstractmethod
    async def invoke(self, message: str, context: dict[str, Any]) -> AgentOutput:
        """Process a message with graph context, return structured output."""
        ...

    def reset(self) -> None:
        self._initialized = False
        self._history = []
