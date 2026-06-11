# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Install dependencies (dev tools, no GNN)
pip install -e ".[dev]"

# Install with GNN support (heavy — PyTorch + PyG)
pip install -e ".[dev,gnn]"

# Run the app
chainlit run src/ui/app.py --port 8000

# Inspect graph state (stop the app first — Kuzu single-connection)
python3 scripts/graph_stats.py

# Lint
ruff check .
ruff format .

# Tests
pytest
pytest tests/path/to/test_file.py::test_name   # single test
```

## Environment

Secrets live in `/secrets/secrets.env` (mounted read-only from `~/.secrets` on the host).
On container create, `bootstrap-secrets.sh` wires them into `~/.bashrc` and `~/.profile`.
`src/ui/app.py` also calls `load_dotenv("/secrets/secrets.env")` as a Chainlit-process fallback.

**Never put `ANTHROPIC_API_KEY` in `.env`** — `.env` is for non-sensitive config only.

`.env` variables:
```
MODEL_PROVIDER=anthropic
MODEL_NAME=claude-sonnet-4-6
KUZU_DB_PATH=data/kuzu
GNN_ENRICHMENT_ENABLED=true
```

To switch LLM provider (e.g. Ollama): set `MODEL_PROVIDER=ollama` and `MODEL_NAME=mistral` in `.env`.
Also update `_PRICE_*` constants in `src/agents/base.py` to match the new model's pricing.

## Architecture

This system automates SDLC artifacts (requirements → DDD → Gherkin → code) using a council of LLM agents backed by a knowledge graph (Kuzu). A GNN enrichment pass (Milestone 3, not yet implemented) will add embedding-based retrieval on top.

### Two operating modes

- **Top-down**: Library Manager types requirements → DDD Consultant models the domain → Test Engineer generates Gherkin → graph written
- **Bottom-up**: Uploaded codebase/Gherkin → Developer parses code → DDD Consultant infers structure → Library Manager validates

The Library Manager (human user or SME Agent in simulation mode) interacts only through the Chainlit UI. They never write to the graph directly.

### Council of agents (`src/agents/`)

| Agent | File | Persona | Owns |
|---|---|---|---|
| `DDDConsultantAgent` | `ddd_consultant.py` | Strategic + tactical DDD architect | `BoundedContext`, `Aggregate`, `DomainEvent`, `GlossaryTerm` + `CONTAINS`, `EMITS`, `DEFINED_AS` edges |
| `TestEngineerAgent` | `test_engineer.py` | BDD/Gherkin specialist | `GherkinFeature`, `GherkinScenario` + `COVERED_BY` edges |
| `DeveloperAgent` | `developer.py` | Senior software architect | `CodeModule`, `CodeClass`, `CodeFunction` (bottom-up only — skipped in top-down) |

All agents extend `BaseAgent` (`base.py`). Key patterns:
- **Lazy init** — `_ensure_initialized()` on first `invoke()`, not at construction
- **Anthropic tool-use** — each agent defines a `_TOOL: anthropic.types.ToolParam` with the Pydantic schema as `input_schema`; the LLM is forced to call it via `tool_choice`
- **`tool_choice: required`** on agents that must return structured output (Test Engineer uses `{"type": "tool", "name": "..."}` to prevent empty lists)
- **Token accounting** — `_log_usage()` returns a `TokenUsage` dataclass; stored on `AgentOutput.usage`; `SessionUsage.summary()` produces the cost table shown in the UI

### Output schemas (`src/agents/schemas.py`)

Pydantic models that double as Anthropic tool input schemas (via `model_json_schema()`):

| Schema | Agent | Contains |
|---|---|---|
| `DDDOutput` | DDD Consultant | `bounded_contexts`, `aggregates`, `domain_events`, `glossary_terms`, `confidence`, `summary` |
| `TestEngineerOutput` | Test Engineer | `features`, `scenarios`, `confidence`, `summary` |
| `DeveloperOutput` | Developer | `modules`, `classes`, `functions`, `confidence`, `summary` |

Relational fields on node models (e.g. `AggregateWrite.bounded_context`, `GherkinScenarioWrite.feature_id`) are used only for edge construction — they are stripped before `write_node()` by `GraphStore._NODE_PROPS`.

### Council orchestration (`src/orchestration/council.py`)

`Council` is **session-scoped** (one per Chainlit session). Owns the LangGraph `StateGraph` and all three agent instances.

**LangGraph pipeline** (fixed sequence per invocation):
```
ddd_pass → developer_pass → test_engineer_pass → commit_to_graph → synthesize → END
```

- `developer_pass` returns `None` in `top_down` flow (agent skipped entirely)
- `_write_graph_writes()` filters props to `_NODE_PROPS` allowed columns before write/conflict-check
- Conflict detection: per-field diff against existing Kuzu node — surfaced as council flag, write proceeds (optimistic)
- `synthesize` appends a token cost table to the UI response

**Consensus protocol**: optimistic — agents write independently, conflicts surface at `commit_to_graph` only. No agent waits for another's approval.

### Graph layer (`src/graph/`)

**Store** (`store.py`): Kuzu embedded graph DB. No server. Data at `data/kuzu`. Single-connection — stop the app before running scripts.

`write_node()` — upsert: checks existence, then CREATE (positional params) or field-by-field SET. Filters to `_NODE_PROPS[node_type]` before write.
`write_edge()` — idempotent: checks existence before CREATE.
`query()` — raw Cypher, returns `list[list[Any]]`.

**Schema** (`schema.py`): Three layers connected by typed edges:
```
Requirement → (FULFILLS) → BoundedContext → (CONTAINS) → Aggregate → (EMITS) → DomainEvent
                                                                   ↓ (IMPLEMENTED_BY)
                                                              CodeModule
DomainEvent → (COVERED_BY) → GherkinScenario
GlossaryTerm → (DEFINED_AS) → BoundedContext
```

**GNN enrichment** (`gnn.py`): Async background loop (60s interval). `run_pass()` is a placeholder — not yet implemented (Milestone 3). Never on the critical path.

### UI (`src/ui/app.py`)

Chainlit app. Session state holds the `Council` instance. Flow toggled by typing `flow: bottom_up` in chat.
Loads `/secrets/secrets.env` then `.env` on startup (`.env` can override non-sensitive defaults).

## Key implementation TODOs (in priority order)

1. **Gherkin scenarios** — Test Engineer produces `GherkinFeature` nodes but `scenarios` list is still empty; `tool_choice: required` + tightened prompt added, needs re-test
2. **tree-sitter code parser** — `src/graph/parsers/code.py` — bottom-up flow needs Python source → `CodeModule/Class/Function` nodes
3. **Gherkin file parser** — `src/graph/parsers/gherkin.py` — `.feature` file ingestion
4. **`GNNEnrichment.run_pass()`** — Kuzu → PyG HeteroData → GraphSAGE/GAT → embeddings back to store
5. **SME Agent** — `src/agents/sme.py` — simulated Library Manager for automated pipeline testing

## Adding a new agent

1. Define output schema in `src/agents/schemas.py` (Pydantic model with all node fields)
2. Create `src/agents/your_agent.py` extending `BaseAgent`
   - Define `name`, `persona`, `_TOOL: anthropic.types.ToolParam`
   - Call `self._log_usage(response.usage)` after the API call; attach result to `AgentOutput.usage`
   - Set `tool_choice={"type": "tool", "name": "..."}` if empty lists are a risk
3. Add to `src/agents/__init__.py`
4. Add a lazy property to `Council`, wire a new node into `_build_graph()`
5. Add allowed node props to `GraphStore._NODE_PROPS`
6. Add node/edge table entries to `GraphStore._init_schema()`

## Secrets and env setup

Centralized secrets pattern — works across all devcontainer projects:

```
~/.secrets/secrets.env          # on host machine (never committed)
  ↓ mounted read-only as
/secrets/secrets.env            # inside container
  ↓ sourced by
.devcontainer/bootstrap-secrets.sh   # per-project, copies sourcing line to ~/.bashrc + ~/.profile
```

`postCreateCommand` in `devcontainer.json`:
```json
"postCreateCommand": "bash .devcontainer/bootstrap-secrets.sh && python3.10 -m pip install -e '/workspace/.[dev]'"
```

Copy `bootstrap-secrets.sh` to any new project's `.devcontainer/` — no other changes needed.
