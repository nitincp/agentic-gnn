# Backlog

Tracked here so any session, client, or AI assistant can pick up exactly where things left off.
Update status inline as work progresses. Format: `[ ]` todo · `[~]` in progress · `[x]` done.

---

## How to use this file

- One item per line, grouped by milestone
- Add a date and note when status changes, e.g. `[x] 2026-06-11 — done`
- For anything non-obvious, add a sub-bullet with context
- See `CLAUDE.md` for architecture, commands, and implementation guidance
- Run `python3 scripts/graph_stats.py` (app stopped) to inspect graph state after each prompt

---

## Milestone 1 — Core pipeline end-to-end ✓

Goal: a single top-down message from the Library Manager flows through all agents and writes real nodes to the graph.

- [x] 2026-06-11 **Structured agent output** — all three agents use Anthropic tool-use with typed Pydantic schemas
  - `src/agents/schemas.py` — per-agent Pydantic models: `DDDOutput`, `TestEngineerOutput`, `DeveloperOutput`
  - DDD Consultant: `BoundedContext`, `Aggregate`, `DomainEvent`, `GlossaryTerm` + edges
  - Test Engineer: `GherkinFeature`, `GherkinScenario` + `COVERED_BY` edges
  - Developer: `CodeModule`, `CodeClass`, `CodeFunction` (bottom-up only)
  - `tool_choice: required` on Test Engineer to prevent empty scenario lists
- [x] 2026-06-11 **Graph writes in `commit_to_graph`** — `_write_graph_writes()` calls `store.write_node()` / `store.write_edge()`
  - Property filter applied before write — extra relational fields (e.g. `feature_id`, `bounded_context`) stripped to Kuzu-allowed columns only
  - `GraphStore._NODE_PROPS` dict is the single source of truth for allowed columns per node type
- [x] 2026-06-11 **Conflict detection at write time** — field-level diff surfaced as council flags before overwrite
- [x] 2026-06-11 **Kuzu upsert** — `write_node` checks existence, does CREATE or field-by-field SET; `write_edge` is idempotent
- [x] 2026-06-11 **Token usage logging** — `TokenUsage` / `SessionUsage` dataclasses in `base.py`; per-agent cost table appended to every UI response; raw log via `council.usage` logger in terminal
- [x] 2026-06-11 **Smoke test** — e-commerce domain prompt confirmed: 5 BCs, 9 aggregates, 15 domain events, 11 glossary terms, 9 CONTAINS, 15 EMITS, 11 DEFINED_AS edges written to Kuzu. Conflicts correctly surfaced on second run.
- [~] **Gherkin scenarios** — features write correctly; scenarios still empty (Test Engineer fills tool call with features only)
  - Prompt tightened + `tool_choice: required` added — needs re-test

---

## Milestone 2 — SME Agent Phase A (minimal test driver)

Goal: replace manual typing with a scriptable agent that drives the council, so every subsequent milestone can be validated automatically rather than by hand.

Rationale: split from the full SME simulation (Phase B, Milestone 6) deliberately. Phase A is cheap (~1 day), has immediate payoff for Milestones 3–5, and keeps scope tight. The council never knows if input is from a human or the SME — architecture is unchanged.

- [ ] **`SMEAgent` class** — `src/agents/sme.py`
  - Takes a plain-text `domain_brief` and optional `scenario` hint (`new_feature` | `change` | `remove`)
  - Calls the Anthropic API with a Library Manager persona to generate the next requirement message
  - Stateless per call — no history, no YAML yet
- [ ] **`scripts/simulate.py`** — minimal runner
  - Instantiates `SMEAgent` + `Council`, runs N turns, prints graph delta and token cost per turn
  - Usage: `python3 scripts/simulate.py --domain "e-commerce order system" --turns 3`
- [ ] **Validate Milestone 1 end-to-end** — run simulate.py, confirm scenarios populate in Kuzu (closes the Gherkin `[~]` item)

---

## Milestone 3 — Bottom-up flow

Goal: upload a codebase or `.feature` files and have the council infer a DDD model.

- [ ] **tree-sitter code parser** — parse uploaded source files into `CodeModule`, `CodeClass`, `CodeFunction` nodes
  - Entry point: `src/graph/parsers/code.py`
  - Start with Python only (`tree-sitter-python` already a dependency)
- [ ] **Gherkin file ingestion** — parse `.feature` files into `GherkinFeature`, `GherkinScenario` nodes
  - Entry point: `src/graph/parsers/gherkin.py`
- [ ] **File upload in Chainlit UI** — allow Library Manager to attach files; route to correct parser based on extension
- [ ] **Bottom-up council pass** — Developer agent activates; DDD Consultant infers from code/Gherkin nodes
- [ ] **SME bottom-up scenario** — extend `simulate.py` to pass synthetic source to the SME, drive a bottom-up session, verify graph output

---

## Milestone 4 — GNN enrichment

Goal: background GNN pass produces node embeddings that improve agent retrieval.

- [ ] **Kuzu → PyG export** — read heterogeneous graph from Kuzu, convert to `torch_geometric.data.HeteroData`
- [ ] **GNN model** — implement GraphSAGE or GAT over the hetero graph in `gnn.py:run_pass()`
- [ ] **Embeddings → Kuzu** — write learned embeddings back as node properties
- [ ] **Agent retrieval uses embeddings** — agents query by embedding similarity, not just keyword match
- [ ] **Install gnn extra** — `pip install -e ".[gnn]"` and confirm torch + pyg install cleanly in the container
- [ ] **SME validation** — run simulate.py before and after GNN pass; confirm retrieval quality improves across turns
- Note: GNN is purely additive — never on the critical path. Agents work without it.

---

## Milestone 5 — Robustness

- [ ] **Session persistence across restarts** — agents re-hydrate from Kuzu on container restart; confirm no state loss
- [ ] **Confidence calibration** — hardcoded `0.8` in all agents; replace with real scoring derived from LLM response
- [ ] **Error handling** — Anthropic API failures, Kuzu write errors, low-confidence escalation path
- [ ] **Tests** — at least one test per agent, one for `GraphStore`, one for `Council.invoke()`

---

## Milestone 6 — Model flexibility

- [ ] **Ollama integration** — add Ollama service to `docker-compose.yml`, smoke test with `mistral` or `phi3`
  - LiteLLM is already a dependency; only env vars need to change
  - Risk: tool-use reliability with smaller models is unproven — validate before depending on it
  - Use `simulate.py` to compare graph output quality between models
- [ ] **Model config per agent** — allow different agents to use different models (e.g. smaller model for Test Engineer)
  - Update `_PRICE_*` constants in `src/agents/base.py` when switching models

---

## Milestone 7 — SME Agent Phase B (full simulation)

Goal: full persona-driven multi-domain simulation for stress testing, regression, and demo purposes.

Builds on Phase A (Milestone 2). Council is stable by this point — SME failures are clearly input-quality issues, not council bugs.

- [ ] **Persona library** — `src/agents/personas/` — YAML files per role (`library_manager.yaml`, `fintech_pm.yaml`, `healthcare_admin.yaml`)
  - Schema: `role`, `domain`, `priorities`, `communication_style`, `sample_requests`
- [ ] **Full scenario types in SMEAgent:**
  - Change request on existing aggregate/event
  - Removal / deprecation of a feature
  - Conflicting requirement (tests conflict detection)
- [ ] **Multi-turn conversation history** — SME accumulates prior council responses to simulate realistic back-and-forth
- [ ] **Wire into Chainlit** — optional `sme: <domain>` command starts a live simulation session observable in the UI
- [ ] **Benchmark suite** — fixed set of domains + scenarios; compare graph quality metrics across builds

---

## Decisions log

| Date | Decision | Reason |
|---|---|---|
| 2026-06-11 | LangGraph over Ray for agent orchestration | Old laptop constraint; Ray is too heavy for prototype. Migrate later. |
| 2026-06-11 | Kuzu embedded over Neo4j | Zero infra, no server. Migrate to Neo4j if hosted deployment needed. |
| 2026-06-11 | Single DDD Consultant agent (not split strategic/tactical) | Agent decides when to switch modes; avoids second council seat and coordination overhead. |
| 2026-06-11 | torch moved to optional `[gnn]` extra | Prevents OOM on first `pip install` on old laptop. Install separately when ready for Milestone 3. |
| 2026-06-11 | Plain pip over uv | Python is on host; uv adds friction without benefit for a single fixed environment. |
| 2026-06-11 | Optimistic consensus (no blocking) | Least resistance protocol. Agents write independently; conflicts surface at commit time only. |
| 2026-06-11 | Anthropic SDK direct over LiteLLM for now | LiteLLM listed as dependency but not wired — direct SDK gives cleaner tool-use API. Switch to LiteLLM when adding Ollama (Milestone 5). |
| 2026-06-11 | `tool_choice: required` on Test Engineer | `auto` caused empty scenario lists — model wrote Gherkin as free text and called tool with empty arrays. Forced tool call fixes this. |
| 2026-06-11 | Kuzu single-connection constraint | Kuzu embedded DB allows only one open connection. Cannot run `graph_stats.py` while app is running. Stop the app first. |
| 2026-06-11 | Secrets in `/secrets/secrets.env`, sourced via `bootstrap-secrets.sh` | Centralized secrets outside all projects. `.devcontainer/bootstrap-secrets.sh` is the only per-project file needed. `app.py` also calls `load_dotenv("/secrets/secrets.env")` as a fallback for the Chainlit process. |
| 2026-06-11 | SME Agent is a separate agent class, not a UI persona | SME acts as the Library Manager in automated flows. Keeps council architecture unchanged — council never knows if input came from human or SME. |
| 2026-06-11 | SME Agent split into Phase A (M2) and Phase B (M7) | Phase A (minimal script driver) unblocks automated validation for all subsequent milestones cheaply. Phase B (persona library, full simulation) waits until council is stable so SME failures are clearly input-quality issues not council bugs. |
| 2026-06-11 | Stay on `claude-sonnet-4-6` for now | Structured tool-use with schema-forced output needs a capable model. Token cost table in UI makes spend visible. |
