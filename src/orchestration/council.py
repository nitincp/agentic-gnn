"""
LangGraph-based council orchestrator.
Agents are lazy-initialized on first use and persist for the session lifetime.
Consensus protocol: optimistic writes, conflict detection at write time,
low-confidence outputs flagged for council review.
"""

from typing import Any, Literal

import anthropic
from langgraph.graph import END, StateGraph
from typing_extensions import TypedDict

from src.agents import DDDConsultantAgent, DeveloperAgent, TestEngineerAgent
from src.agents.base import AgentOutput, SessionUsage
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

    def _write_graph_writes(self, graph_writes: list[dict], conflicts: list[str]) -> None:
        from src.graph.schema import EdgeType, NodeType

        for write in graph_writes:
            kind = write.get("kind")
            try:
                if kind == "node":
                    node_type_str = write.get("node_type")
                    node_type = NodeType(node_type_str)
                    raw_props = {k: v for k, v in write.items() if k not in ("kind", "node_type")}
                    # Filter to only columns that exist in the Kuzu schema
                    allowed = self._store._NODE_PROPS.get(node_type)
                    props = (
                        {k: v for k, v in raw_props.items() if k in allowed}
                        if allowed
                        else raw_props
                    )

                    # Conflict detection: check each prop individually
                    for key, new_val in props.items():
                        if key == "id":
                            continue
                        rows = self._store.query(
                            f"MATCH (n:{node_type} {{id: $id}}) RETURN n.{key}",
                            {"id": props["id"]},
                        )
                        if rows and rows[0][0] != new_val and rows[0][0] is not None:
                            conflicts.append(
                                f"Conflict on {node_type} '{props['id']}' "
                                f"field '{key}': '{rows[0][0]}' → '{new_val}'"
                            )
                    self._store.write_node(node_type, props)

                elif kind == "edge":
                    self._store.write_edge(
                        edge_type=EdgeType(write["edge_type"]),
                        src_type=NodeType(write["src_type"]),
                        src_id=write["src_id"],
                        dst_type=NodeType(write["dst_type"]),
                        dst_id=write["dst_id"],
                    )
            except Exception as exc:
                kind_label = write.get("node_type") or write.get("edge_type")
                conflicts.append(f"Write error ({kind_label}): {exc}")

    async def _commit_to_graph(self, state: CouncilState) -> CouncilState:
        conflicts: list[str] = []
        outputs = [state["ddd_output"], state["developer_output"], state["test_engineer_output"]]
        for output in outputs:
            if output is None:
                continue
            if output.confidence < CONFIDENCE_THRESHOLD:
                conflicts.append(f"Low confidence ({output.confidence:.2f}) — skipped graph write")
                continue
            self._write_graph_writes(output.graph_writes, conflicts)
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
            parts.append("**Council flags:**\n" + "\n".join(state["conflicts"]))

        # Cost footer
        session = SessionUsage()
        outputs = [state["ddd_output"], state["developer_output"], state["test_engineer_output"]]
        for output in outputs:
            if output and output.usage:
                session.add(output.usage)
        if session.turns:
            parts.append(f"**Token usage (this turn):**\n{session.summary()}")

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
