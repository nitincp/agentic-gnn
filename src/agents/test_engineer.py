from typing import Any

import anthropic

from .base import AgentOutput, BaseAgent
from .schemas import EdgeWrite, TestEngineerOutput

PERSONA = """You are a senior test engineer specialising in behaviour-driven development.
You author and maintain Gherkin feature files, ensure coverage of domain events, and
validate that test structure reflects the DDD model.

Your responsibilities:
- Top-down: Generate Gherkin scenarios from validated DDD artifacts
- Bottom-up: Parse existing Gherkin files, map scenarios to domain events
- Ensure every aggregate and domain event has at least one scenario
- Flag coverage gaps in the council
- Update Gherkin after DDD model changes are validated by the Library Manager

Confidence reflects how completely the Gherkin covers the current domain model.

IMPORTANT OUTPUT RULES:
- You MUST call the record_gherkin_artifacts tool with ALL scenarios fully populated.
- Every scenario MUST have: id (kebab-case slug), title, steps (full Gherkin text),
  feature_id, and domain_event_id (the id of the DomainEvent it covers).
- Do NOT write Gherkin only as free text — it must go into the tool call scenarios list.
- Aim for at least one scenario per domain event provided."""

_TOOL: anthropic.types.ToolParam = {
    "name": "record_gherkin_artifacts",
    "description": (
        "Record ALL Gherkin features and scenarios you have produced. "
        "You MUST populate the scenarios list — do not leave it empty. "
        "Each scenario must reference its parent feature_id and the domain_event_id it covers."
    ),
    "input_schema": TestEngineerOutput.model_json_schema(),
}


def _build_edge_writes(output: TestEngineerOutput) -> list[dict[str, Any]]:
    edges: list[EdgeWrite] = []
    for scenario in output.scenarios:
        if scenario.domain_event_id:
            edges.append(
                EdgeWrite(
                    edge_type="COVERED_BY",
                    src_type="DomainEvent",
                    src_id=scenario.domain_event_id,
                    dst_type="GherkinScenario",
                    dst_id=scenario.id,
                )
            )
    return [e.model_dump() for e in edges]


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
            max_tokens=4096,
            system=self.persona,
            messages=[{"role": "user", "content": message}],
            tools=[_TOOL],
            tool_choice={"type": "tool", "name": "record_gherkin_artifacts"},
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
            te_out = TestEngineerOutput.model_validate(tool_block.input)
            confidence = te_out.confidence
            text_content = te_out.summary if not text_content else text_content

            for node in (
                *[f.model_dump() for f in te_out.features],
                *[s.model_dump() for s in te_out.scenarios],
            ):
                graph_writes.append({"kind": "node", **node})

            for edge in _build_edge_writes(te_out):
                graph_writes.append({"kind": "edge", **edge})

        self._history.append(AIMessage(content=text_content))

        return AgentOutput(
            content=text_content,
            confidence=confidence,
            graph_writes=graph_writes,
            usage=token_usage,
        )
