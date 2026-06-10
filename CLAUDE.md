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

# Lint
ruff check .
ruff format .

# Tests
pytest
pytest tests/path/to/test_file.py::test_name   # single test
```

## Environment

Copy `.env.example` to `.env` and set `ANTHROPIC_API_KEY`. All other variables have defaults.

To switch LLM provider later (e.g. Ollama): change `MODEL_PROVIDER` and `MODEL_NAME` in `.env` — no code changes needed (LiteLLM handles routing).

## Architecture

This system automates SDLC artifacts (requirements → DDD → Gherkin → code) using a council of LLM agents backed by a GNN-enriched knowledge graph.

### Two operating modes

- **Top-down**: Library Manager provides raw requirements → council produces DDD artifacts → Test Engineer generates Gherkin
- **Bottom-up**: Existing codebase/Gherkin uploaded → DDD Consultant infers structure → Library Manager validates

The Library Manager (human user) interacts only through the Chainlit UI. They never write to the graph directly.

### Council of agents (`src/agents/`)

Three agents, all LLM personas backed by `anthropic.AsyncAnthropic`:

| Agent | Persona | Primary graph contribution |
|---|---|---|
| `DDDConsultantAgent` | Strategic + tactical DDD architect | DDD nodes (BoundedContext, Aggregate, DomainEvent, GlossaryTerm) |
| `DeveloperAgent` | Senior software architect | Code nodes (CodeModule, CodeClass, CodeFunction) |
| `TestEngineerAgent` | BDD/Gherkin specialist | Gherkin nodes (GherkinFeature, GherkinScenario) |

All agents extend `BaseAgent` (`src/agents/base.py`). Key pattern: **lazy initialization** — `_ensure_initialized()` is called on first `invoke()`, not at construction. Agent conversation history (`_history`) persists for the session lifetime inside the `Council` object.

`AgentOutput` carries `confidence: float` (0–1). Outputs below `CONFIDENCE_THRESHOLD = 0.6` in `council.py` are flagged rather than written to the graph.

### Council orchestration (`src/orchestration/council.py`)

`Council` is **session-scoped** (one per Chainlit session, created in `src/ui/app.py`). It owns the LangGraph `StateGraph` and all three agent instances.

**LangGraph pipeline** (fixed sequence per invocation):
```
ddd_pass → developer_pass → test_engineer_pass → commit_to_graph → synthesize → END
```

- `developer_pass` is skipped (returns `None`) in `top_down` flow
- `commit_to_graph` performs conflict detection and optimistic writes; low-confidence outputs are flagged, not blocked
- `synthesize` assembles all agent outputs into a single markdown response for the UI

**Consensus protocol**: optimistic — agents write independently, conflicts surface only at `commit_to_graph`. No agent waits for another's approval. Human escalation only when the graph detects an unresolvable conflict.

### Graph layer (`src/graph/`)

**Store**: Kuzu embedded graph DB (`src/graph/store.py`). No server. Data persists to `data/kuzu/` (volume-mounted in Docker). `GraphStore` auto-initialises the full schema on first connection.

**Schema** (`src/graph/schema.py`): Three layers of nodes connected by typed edges:
```
Requirement → (FULFILLS) → BoundedContext → (CONTAINS) → Aggregate → (EMITS) → DomainEvent
                                                                    ↓ (IMPLEMENTED_BY)
                                                               CodeModule
DomainEvent → (COVERED_BY) → GherkinScenario
GlossaryTerm → (DEFINED_AS) → BoundedContext
```

DDD nodes are the **bridge layer** — the shared ontology that lets requirements, code, and tests refer to the same concepts. All agent graph writes must map to `NodeType` and `EdgeType` enums.

**GNN enrichment** (`src/graph/gnn.py`): Async background loop (default 60s interval). Reads the Kuzu graph, produces PyTorch Geometric embeddings, writes them back as node properties. Currently a skeleton — `run_pass()` is a placeholder. When implemented, embeddings improve agent retrieval quality but are never on the critical path.

### UI (`src/ui/app.py`)

Chainlit app. Session state holds the `Council` instance. Flow mode (`top_down` / `bottom_up`) is toggled by the Library Manager typing `flow: bottom_up` in chat.

## Key implementation TODOs (in priority order)

1. **`commit_to_graph`** in `council.py` — agent `graph_writes` are collected but not yet written to Kuzu
2. **Structured artifact extraction** in each agent — LLM responses need to be parsed into typed `graph_writes` (use structured output / tool use)
3. **`GNNEnrichment.run_pass()`** in `gnn.py` — Kuzu → PyG HeteroData → GraphSAGE/GAT → embeddings back to store
4. **tree-sitter code parser** — bottom-up flow needs a parser that produces `CodeModule/Class/Function` nodes from uploaded source
5. **Gherkin parser** — bottom-up flow needs `.feature` file ingestion into `GherkinFeature/Scenario` nodes

## Adding a new agent

1. Create `src/agents/your_agent.py` extending `BaseAgent`, define `name`, `persona`, implement `invoke()`
2. Add to `src/agents/__init__.py`
3. Add a lazy property to `Council`, wire a new node into `_build_graph()`
4. Define what `NodeType`/`EdgeType` it writes and add to schema if needed

## Adding Ollama support

Set in `.env`:
```
MODEL_PROVIDER=ollama
MODEL_NAME=mistral   # or phi3, llama3, etc.
```

LiteLLM is already a dependency — no code changes needed. Ensure Ollama is running at `http://localhost:11434`. Update `docker-compose.yml` to add an `ollama` service if running inside Docker.
