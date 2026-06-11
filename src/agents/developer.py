from typing import Any

import anthropic

from .base import AgentOutput, BaseAgent
from .schemas import DeveloperOutput

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

_TOOL: anthropic.types.ToolParam = {
    "name": "record_code_artifacts",
    "description": (
        "Record the structured code artifacts you identified. "
        "Call this once with all modules, classes, and functions."
    ),
    "input_schema": DeveloperOutput.model_json_schema(),
}


class DeveloperAgent(BaseAgent):
    name = "developer"
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

        tool_block = next(
            (b for b in response.content if isinstance(b, anthropic.types.ToolUseBlock)),
            None,
        )
        text_blocks = [b for b in response.content if isinstance(b, anthropic.types.TextBlock)]
        text_content = text_blocks[0].text if text_blocks else ""

        graph_writes: list[dict[str, Any]] = []
        confidence = 0.8

        if tool_block:
            dev_out = DeveloperOutput.model_validate(tool_block.input)
            confidence = dev_out.confidence
            text_content = dev_out.summary if not text_content else text_content

            for node in (
                *[m.model_dump() for m in dev_out.modules],
                *[c.model_dump() for c in dev_out.classes],
                *[f.model_dump() for f in dev_out.functions],
            ):
                graph_writes.append({"kind": "node", **node})

        self._history.append(AIMessage(content=text_content))

        return AgentOutput(
            content=text_content,
            confidence=confidence,
            graph_writes=graph_writes,
            usage=token_usage,
        )
