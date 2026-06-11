from typing import Any

import anthropic

from .base import AgentOutput, BaseAgent
from .schemas import (
    DDDOutput,
    EdgeWrite,
)

PERSONA = """You are a Domain-Driven Design consultant with deep expertise in both strategic
and tactical DDD. You adapt your approach based on what the domain model needs — starting
with strategic patterns (bounded contexts, context maps, ubiquitous language) and moving
to tactical patterns (aggregates, entities, value objects, domain events) when the strategic
model is stable enough.

Your responsibilities:
- Top-down: Extract DDD artifacts from raw requirements
- Bottom-up: Infer DDD structure from Gherkin scenarios
- Maintain and enforce the ubiquitous language glossary
- Flag semantic drift between requirements, Gherkin, and code
- Arbitrate domain language conflicts in the council

Always output structured DDD artifacts alongside your reasoning.
Confidence reflects how well the domain model is grounded in available evidence."""

_TOOL: anthropic.types.ToolParam = {
    "name": "record_ddd_artifacts",
    "description": (
        "Record the structured DDD artifacts you identified. "
        "Call this once with all bounded contexts, aggregates, domain events, "
        "and glossary terms extracted from the requirements."
    ),
    "input_schema": DDDOutput.model_json_schema(),
}


def _build_edge_writes(output: DDDOutput) -> list[dict[str, Any]]:
    edges: list[EdgeWrite] = []
    for agg in output.aggregates:
        edges.append(
            EdgeWrite(
                edge_type="CONTAINS",
                src_type="BoundedContext",
                src_id=agg.bounded_context,
                dst_type="Aggregate",
                dst_id=agg.id,
            )
        )
    for event in output.domain_events:
        edges.append(
            EdgeWrite(
                edge_type="EMITS",
                src_type="Aggregate",
                src_id=event.aggregate,
                dst_type="DomainEvent",
                dst_id=event.id,
            )
        )
    for term in output.glossary_terms:
        edges.append(
            EdgeWrite(
                edge_type="DEFINED_AS",
                src_type="GlossaryTerm",
                src_id=term.id,
                dst_type="BoundedContext",
                dst_id=term.bounded_context,
            )
        )
    return [e.model_dump() for e in edges]


class DDDConsultantAgent(BaseAgent):
    name = "ddd_consultant"
    persona = PERSONA

    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        super().__init__()
        self._client = client
        self._model = model

    async def invoke(self, message: str, context: dict[str, Any]) -> AgentOutput:
        self._ensure_initialized()

        from langchain_core.messages import AIMessage, HumanMessage

        self._history.append(HumanMessage(content=message))

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=4096,
            system=self.persona,
            messages=[{"role": "user", "content": message}],
            tools=[_TOOL],
            tool_choice={"type": "auto"},
        )

        token_usage = self._log_usage(response.usage)

        # Extract tool-use block for structured artifacts
        tool_block = next(
            (b for b in response.content if isinstance(b, anthropic.types.ToolUseBlock)),
            None,
        )
        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        text_content = text_blocks[0].text if text_blocks else ""

        graph_writes: list[dict[str, Any]] = []
        confidence = 0.8

        if tool_block:
            ddd_out = DDDOutput.model_validate(tool_block.input)
            confidence = ddd_out.confidence
            text_content = ddd_out.summary if not text_content else text_content

            for node in (
                *[bc.model_dump() for bc in ddd_out.bounded_contexts],
                *[a.model_dump() for a in ddd_out.aggregates],
                *[e.model_dump() for e in ddd_out.domain_events],
                *[g.model_dump() for g in ddd_out.glossary_terms],
            ):
                graph_writes.append({"kind": "node", **node})

            for edge in _build_edge_writes(ddd_out):
                graph_writes.append({"kind": "edge", **edge})

        self._history.append(AIMessage(content=text_content))

        return AgentOutput(
            content=text_content,
            confidence=confidence,
            graph_writes=graph_writes,
            usage=token_usage,
        )
