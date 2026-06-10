from typing import Any

import anthropic

from .base import AgentOutput, BaseAgent

PERSONA = """You are a senior test engineer specialising in behaviour-driven development.
You author and maintain Gherkin feature files, ensure coverage of domain events, and
validate that test structure reflects the DDD model.

Your responsibilities:
- Top-down: Generate Gherkin scenarios from validated DDD artifacts
- Bottom-up: Parse existing Gherkin files, map scenarios to domain events
- Ensure every aggregate and domain event has at least one scenario
- Flag coverage gaps in the council
- Update Gherkin after DDD model changes are validated by the Library Manager

Confidence reflects how completely the Gherkin covers the current domain model."""


class TestEngineerAgent(BaseAgent):
    name = "test_engineer"
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
            max_tokens=2048,
            system=self.persona,
            messages=[{"role": "user", "content": message}],
        )

        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        content = text_blocks[0].text if text_blocks else ""
        self._history.append(AIMessage(content=content))

        # TODO: parse Gherkin node writes from content
        return AgentOutput(
            content=content,
            confidence=0.8,
            graph_writes=[],
        )
