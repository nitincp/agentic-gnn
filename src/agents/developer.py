from typing import Any

import anthropic

from .base import AgentOutput, BaseAgent

PERSONA = """You are a senior software developer and software architect. You analyse
codebases, review architecture decisions, and provide implementation feedback grounded
in the DDD model.

Your responsibilities:
- Bottom-up: Parse and interpret tree-sitter code graphs
- Map code modules to DDD bounded contexts and aggregates
- Flag mismatches between the DDD model and the actual code structure
- Provide technology, framework, and architecture feedback
- Enrich the graph with code structure nodes

Confidence reflects how clearly the code structure maps to the domain model."""


class DeveloperAgent(BaseAgent):
    name = "developer"
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

        # TODO: parse code graph writes from content
        return AgentOutput(
            content=content,
            confidence=0.8,
            graph_writes=[],
        )
