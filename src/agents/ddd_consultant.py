from typing import Any

import anthropic

from .base import AgentOutput, BaseAgent

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


class DDDConsultantAgent(BaseAgent):
    name = "ddd_consultant"
    persona = PERSONA

    def __init__(self, client: anthropic.AsyncAnthropic, model: str) -> None:
        super().__init__()
        self._client = client
        self._model = model

    async def invoke(self, message: str, context: dict[str, Any]) -> AgentOutput:
        self._ensure_initialized()

        from langchain_core.messages import HumanMessage, AIMessage

        self._history.append(HumanMessage(content=message))

        response = await self._client.messages.create(
            model=self._model,
            max_tokens=2048,
            system=self.persona,
            messages=[{"role": "user", "content": message}],
        )

        content = response.content[0].text
        self._history.append(AIMessage(content=content))

        # TODO: parse structured DDD artifacts from content for graph writes
        return AgentOutput(
            content=content,
            confidence=0.8,
            graph_writes=[],
        )
