"""
LangGraph-based council orchestrator.
Agents are lazy-initialized on first use and persist for the session lifetime.
Consensus protocol: optimistic writes, conflict detection at write time,
low-confidence outputs flagged for council review.
"""

from typing import Any, Literal
from typing_extensions import TypedDict

import anthropic
from langgraph.graph import StateGraph, END

from src.agents import DDDConsultantAgent, DeveloperAgent, TestEngineerAgent
from src.agents.base import AgentOutput
from src.graph.store import GraphStore


CONFIDENCE_THRESHOLD = 0.6


class CouncilState(TypedDict):
    message: str
    flow: Literal["top_down", "bottom_up"]
    context: dict[str, Any]
    ddd_output: AgentOutput | None
    developer_output: AgentOutput | None
    test_engineer_output: AgentOutput | None
    conflicts: list[str]
    response: str


class Council:
    """Session-scoped council. Agents lazy-init on first invoke."""

    def __init__(self, store: GraphStore, model: str = "claude-sonnet-4-6") -> None:
        self._store = store
        self._client = anthropic.AsyncAnthropic()
        self._model = model

        # Lazy-initialized agents
        self._ddd: DDDConsultantAgent | None = None
        self._developer: DeveloperAgent | None = None
        self._test_engineer: TestEngineerAgent | None = None

        self._graph = self._build_graph()

    @property
    def ddd(self) -> DDDConsultantAgent:
        if self._ddd is None:
            self._ddd = DDDConsultantAgent(self._client, self._model)
        return self._ddd

    @property
    def developer(self) -> DeveloperAgent:
        if self._developer is None:
            self._developer = DeveloperAgent(self._client, self._model)
        return self._developer

    @property
    def test_engineer(self) -> TestEngineerAgent:
        if self._test_engineer is None:
            self._test_engineer = TestEngineerAgent(self._client, self._model)
        return self._test_engineer

    def _build_graph(self) -> Any:
        builder = StateGraph(CouncilState)

        builder.add_node("ddd_pass", self._ddd_pass)
        builder.add_node("developer_pass", self._developer_pass)
        builder.add_node("test_engineer_pass", self._test_engineer_pass)
        builder.add_node("commit_to_graph", self._commit_to_graph)
        builder.add_node("synthesize", self._synthesize)

        builder.set_entry_point("ddd_pass")
        builder.add_edge("ddd_pass", "developer_pass")
        builder.add_edge("developer_pass", "test_engineer_pass")
        builder.add_edge("test_engineer_pass", "commit_to_graph")
        builder.add_edge("commit_to_graph", "synthesize")
        builder.add_edge("synthesize", END)

        return builder.compile()

    async def _ddd_pass(self, state: CouncilState) -> CouncilState:
        output = await self.ddd.invoke(state["message"], state["context"])
        return {**state, "ddd_output": output}

    async def _developer_pass(self, state: CouncilState) -> CouncilState:
        if state["flow"] == "top_down":
            return {**state, "developer_output": None}
        output = await self.developer.invoke(state["message"], state["context"])
        return {**state, "developer_output": output}

    async def _test_engineer_pass(self, state: CouncilState) -> CouncilState:
        ddd_content = state["ddd_output"].content if state["ddd_output"] else ""
        output = await self.test_engineer.invoke(
            f"DDD model:\n{ddd_content}\n\nOriginal message:\n{state['message']}",
            state["context"],
        )
        return {**state, "test_engineer_output": output}

    async def _commit_to_graph(self, state: CouncilState) -> CouncilState:
        conflicts = []
        for output in [state["ddd_output"], state["developer_output"], state["test_engineer_output"]]:
            if output is None:
                continue
            if output.confidence < CONFIDENCE_THRESHOLD:
                conflicts.append(f"Low confidence ({output.confidence:.2f}) — flagged for review")
                continue
            # TODO: write output.graph_writes to self._store
        return {**state, "conflicts": conflicts}

    async def _synthesize(self, state: CouncilState) -> CouncilState:
        parts = []
        if state["ddd_output"]:
            parts.append(f"**DDD Consultant:**\n{state['ddd_output'].content}")
        if state["developer_output"]:
            parts.append(f"**Developer:**\n{state['developer_output'].content}")
        if state["test_engineer_output"]:
            parts.append(f"**Test Engineer:**\n{state['test_engineer_output'].content}")
        if state["conflicts"]:
            parts.append(f"**Council flags:**\n" + "\n".join(state["conflicts"]))
        return {**state, "response": "\n\n---\n\n".join(parts)}

    async def invoke(
        self,
        message: str,
        flow: Literal["top_down", "bottom_up"] = "top_down",
        context: dict[str, Any] | None = None,
    ) -> str:
        initial: CouncilState = {
            "message": message,
            "flow": flow,
            "context": context or {},
            "ddd_output": None,
            "developer_output": None,
            "test_engineer_output": None,
            "conflicts": [],
            "response": "",
        }
        result = await self._graph.ainvoke(initial)
        return result["response"]
