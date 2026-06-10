# Agentic GNN

Council-based SDLC automation. A trio of LLM agents — DDD Consultant, Developer, Test Engineer — share a GNN-enriched knowledge graph to automate the translation between business requirements, domain models, Gherkin tests, and code.

## What it does

**Top-down** (greenfield): Library Manager describes requirements in natural language → DDD Consultant extracts bounded contexts, aggregates, domain events → Test Engineer generates Gherkin scenarios.

**Bottom-up** (legacy): Upload a codebase or existing Gherkin files → DDD Consultant infers the domain model → Library Manager validates it → Test Engineer updates Gherkin to match.

In both flows, all artifacts are stored in a knowledge graph. A background GNN pass enriches the graph with learned embeddings, improving how agents retrieve and reason over prior context across sessions.

## Setup

**Prerequisites**: Python 3.10+, Docker, an Anthropic API key.

```bash
git clone <repo>
cd agentic-gnn
cp .env.example .env
# edit .env — set ANTHROPIC_API_KEY
```

**Run in devcontainer** (recommended):
```
Open in VSCode → "Reopen in Container"
# postCreateCommand runs pip install -e ".[dev]" automatically
chainlit run src/ui/app.py --port 8000
```

**Run locally**:
```bash
pip install -e ".[dev]"
chainlit run src/ui/app.py --port 8000
```

Open `http://localhost:8000`.

## Architecture

```
Library Manager (Chainlit UI)
        │
        ▼
Council (LangGraph)
  ├── DDD Consultant   → BoundedContext, Aggregate, DomainEvent, GlossaryTerm nodes
  ├── Developer        → CodeModule, CodeClass, CodeFunction nodes  [bottom-up only]
  └── Test Engineer    → GherkinFeature, GherkinScenario nodes
        │
        ▼
GraphStore (Kuzu embedded)
        │
        ▼
GNN Enrichment (PyTorch Geometric, async background)
```

### Graph ontology

DDD artifacts are the bridge layer between requirements, code, and tests:

```
Requirement
    └─FULFILLS─► BoundedContext ─CONTAINS─► Aggregate ─EMITS─► DomainEvent
                                                         │            │
                                               IMPLEMENTED_BY    COVERED_BY
                                                         │            │
                                                    CodeModule   GherkinScenario
GlossaryTerm ─DEFINED_AS─► BoundedContext
```

### Consensus protocol

Agents write to the graph optimistically. Outputs below a confidence threshold (0.6) are flagged for Library Manager review rather than written. No agent blocks another. Human escalation only for unresolvable graph conflicts.

### Agent lifecycle

Agents are lazy-initialized on first use within a session and persist for the session lifetime (conversation history retained). The graph store persists across sessions — agents re-hydrate context from Kuzu on restart.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required |
| `MODEL_PROVIDER` | `anthropic` | `anthropic` or `ollama` |
| `MODEL_NAME` | `claude-sonnet-4-6` | Model identifier |
| `KUZU_DB_PATH` | `data/kuzu` | Graph store path |
| `GNN_ENRICHMENT_ENABLED` | `true` | Background GNN pass on/off |

## Current state

The council pipeline, graph schema, and UI are wired end-to-end. The following are scaffolded but not yet implemented:

- Agent → graph writes (structured artifact extraction from LLM output)
- GNN enrichment pass (PyG pipeline)
- tree-sitter code parser for bottom-up flow
- Gherkin file ingestion for bottom-up flow

See `CLAUDE.md` for implementation guidance.

## Roadmap

- [ ] Structured graph writes from agent outputs
- [ ] GNN enrichment (GraphSAGE embeddings)
- [ ] tree-sitter bottom-up code ingestion
- [ ] Gherkin file upload and parsing
- [ ] Ollama local model support
- [ ] Ray actor migration for true concurrency
