# Backlog

Tracked here so any session, client, or AI assistant can pick up exactly where things left off.
Update status inline as work progresses. Format: `[ ]` todo · `[~]` in progress · `[x]` done.

---

## How to use this file

- One item per line, grouped by milestone
- Add a date and note when status changes, e.g. `[x] 2026-06-11 — done`
- For anything non-obvious, add a sub-bullet with context
- See `CLAUDE.md` for architecture, commands, and implementation guidance

---

## Milestone 1 — Core pipeline end-to-end

Goal: a single top-down message from the Library Manager flows through all agents and writes real nodes to the graph.

- [ ] **Structured agent output** — replace free-text LLM responses with tool-use / structured output so agents produce typed `graph_writes`
  - Each agent needs a defined output schema (Pydantic models per node type it owns)
  - DDD Consultant owns: `BoundedContext`, `Aggregate`, `DomainEvent`, `GlossaryTerm`
  - Test Engineer owns: `GherkinFeature`, `GherkinScenario`
  - Developer owns: `CodeModule`, `CodeClass`, `CodeFunction`
- [ ] **Graph writes in `commit_to_graph`** — `council.py:_commit_to_graph()` collects outputs but never calls `store.write_node()` / `store.write_edge()`
- [ ] **Conflict detection at write time** — when a new node contradicts an existing one, surface it as a council flag rather than silently overwriting
- [ ] **Smoke test** — send one message via Chainlit UI, confirm nodes appear in Kuzu

---

## Milestone 2 — Bottom-up flow

Goal: upload a codebase or `.feature` files and have the council infer a DDD model.

- [ ] **tree-sitter code parser** — parse uploaded source files into `CodeModule`, `CodeClass`, `CodeFunction` nodes
  - Entry point: `src/graph/parsers/code.py`
  - Start with Python only (`tree-sitter-python` already a dependency)
- [ ] **Gherkin file ingestion** — parse `.feature` files into `GherkinFeature`, `GherkinScenario` nodes
  - Entry point: `src/graph/parsers/gherkin.py`
- [ ] **File upload in Chainlit UI** — allow Library Manager to attach files; route to correct parser based on extension
- [ ] **Bottom-up council pass** — confirm Developer agent activates and DDD Consultant infers from code/Gherkin nodes correctly

---

## Milestone 3 — GNN enrichment

Goal: background GNN pass produces node embeddings that improve agent retrieval.

- [ ] **Kuzu → PyG export** — read heterogeneous graph from Kuzu, convert to `torch_geometric.data.HeteroData`
- [ ] **GNN model** — implement GraphSAGE or GAT over the hetero graph in `gnn.py:run_pass()`
- [ ] **Embeddings → Kuzu** — write learned embeddings back as node properties
- [ ] **Agent retrieval uses embeddings** — agents query by embedding similarity, not just keyword match
- [ ] **Install gnn extra** — `pip install -e ".[gnn]"` and confirm torch + pyg install cleanly in the container

---

## Milestone 4 — Robustness

- [ ] **Session persistence across restarts** — agents re-hydrate from Kuzu on container restart; confirm no state loss
- [ ] **Confidence calibration** — current hardcoded `0.8` in all agents; replace with real scoring from LLM response metadata
- [ ] **Error handling** — Anthropic API failures, Kuzu write errors, low-confidence escalation path
- [ ] **Tests** — at least one test per agent, one for `GraphStore`, one for `Council.invoke()`

---

## Milestone 5 — Model flexibility

- [ ] **Ollama integration** — add Ollama service to `docker-compose.yml`, smoke test with `mistral` or `phi3`
  - LiteLLM is already a dependency; only env vars need to change
- [ ] **Model config per agent** — allow different agents to use different models (e.g. smaller model for Test Engineer)

---

## Decisions log

Record non-obvious decisions here so future sessions don't re-litigate them.

| Date | Decision | Reason |
|---|---|---|
| 2026-06-11 | LangGraph over Ray for agent orchestration | Old laptop constraint; Ray is too heavy for prototype. Migrate later. |
| 2026-06-11 | Kuzu embedded over Neo4j | Zero infra, no server. Migrate to Neo4j if hosted deployment needed. |
| 2026-06-11 | Single DDD Consultant agent (not split strategic/tactical) | Agent decides when to switch modes; avoids second council seat and coordination overhead. |
| 2026-06-11 | torch moved to optional `[gnn]` extra | Prevents OOM on first `pip install` on old laptop. Install separately when ready for Milestone 3. |
| 2026-06-11 | Plain pip over uv | Python is on host; uv adds friction without benefit for a single fixed environment. |
| 2026-06-11 | Optimistic consensus (no blocking) | Least resistance protocol. Agents write independently; conflicts surface at commit time only. |
