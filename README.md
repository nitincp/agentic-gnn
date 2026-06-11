# Senatus — Council of Deliberation for SDLC Automation

A council of LLM agents that automates SDLC artifact generation (requirements → DDD model → Gherkin tests → code structure) and stores everything in a knowledge graph. A GNN enrichment pass (in progress) adds embedding-based retrieval on top.

## What it does

**Top-down** (greenfield): Library Manager describes requirements in natural language → DDD Consultant extracts bounded contexts, aggregates, domain events, glossary terms → Test Engineer generates Gherkin scenarios → all written to graph.

**Bottom-up** (legacy/existing code): Upload a codebase or `.feature` files → Developer parses code structure → DDD Consultant infers the domain model → Library Manager validates → Test Engineer updates Gherkin.

Every artifact is stored in a Kuzu knowledge graph with typed nodes and edges. Agents write optimistically — conflicts are surfaced to the Library Manager rather than silently overwritten.

## Current state

Milestone 1 complete. The full top-down pipeline is working:
- Agents use Anthropic tool-use with typed Pydantic schemas to produce structured graph writes
- Kuzu graph receives real nodes and edges on every message (upsert, idempotent edges)
- Field-level conflict detection flags semantic drift between runs
- Per-turn token cost table shown in the UI after every response

Active work: Milestone 2 — minimal SME Agent to automate pipeline validation, then bottom-up parsers.

## Setup

**Prerequisites**: Python 3.10, an Anthropic API key.

**Devcontainer** (recommended — handles all deps):
```bash
# Open in VSCode → "Reopen in Container"
# postCreateCommand installs deps automatically
chainlit run src/ui/app.py --port 8000
```

**Local**:
```bash
pip install -e ".[dev]"
chainlit run src/ui/app.py --port 8000
```

**API key**: store in `~/.secrets/secrets.env` as `ANTHROPIC_API_KEY=sk-ant-...`. The devcontainer mounts this read-only and sources it on startup. See `CLAUDE.md` for the full secrets pattern.

Open `http://localhost:8000` (or the VS Code forwarded port URL).

## Architecture

```
Library Manager / SME Agent (Chainlit UI or simulate.py)
        │
        ▼
Council (LangGraph — fixed pipeline per turn)
  ├── DDD Consultant   → BoundedContext, Aggregate, DomainEvent, GlossaryTerm
  ├── Developer        → CodeModule, CodeClass, CodeFunction  [bottom-up only]
  └── Test Engineer    → GherkinFeature, GherkinScenario
        │
        ▼
_commit_to_graph (conflict detection + optimistic write)
        │
        ▼
GraphStore (Kuzu embedded — data/kuzu)
        │
        ▼
GNN Enrichment (PyTorch Geometric, async background — Milestone 4)
```

### Graph ontology

DDD artifacts are the bridge layer — the shared ontology between requirements, code, and tests:

```
Requirement
    └─FULFILLS─► BoundedContext ─CONTAINS─► Aggregate ─EMITS─► DomainEvent
                      │                          │                   │
               DEFINED_AS ◄─ GlossaryTerm  IMPLEMENTED_BY      COVERED_BY
                                                 │                   │
                                            CodeModule        GherkinScenario
```

### Agent output pipeline

Each agent owns a set of node types and produces typed writes via Anthropic tool-use:

| Agent | Schema | Nodes written | Edges written |
|---|---|---|---|
| DDD Consultant | `DDDOutput` | BoundedContext, Aggregate, DomainEvent, GlossaryTerm | CONTAINS, EMITS, DEFINED_AS |
| Test Engineer | `TestEngineerOutput` | GherkinFeature, GherkinScenario | COVERED_BY |
| Developer | `DeveloperOutput` | CodeModule, CodeClass, CodeFunction | — |

### Consensus protocol

Agents write independently — no agent blocks on another's output. Outputs below confidence threshold (0.6) are flagged, not written. Field-level conflicts between new and existing nodes are surfaced as council flags in the UI response. Human (or SME Agent) decides how to resolve.

## Configuration

| Variable | Default | Description |
|---|---|---|
| `ANTHROPIC_API_KEY` | — | Required. Store in `~/.secrets/secrets.env`. |
| `MODEL_NAME` | `claude-sonnet-4-6` | Anthropic model ID |
| `KUZU_DB_PATH` | `data/kuzu` | Graph store path |
| `GNN_ENRICHMENT_ENABLED` | `true` | Background GNN pass on/off |

## Useful commands

```bash
# Inspect graph after a session (stop app first — Kuzu single-connection)
python3 scripts/graph_stats.py

# Lint
ruff check . && ruff format .

# Run automated simulation (Milestone 2, in progress)
python3 scripts/simulate.py --domain "e-commerce order system" --turns 3
```

## Roadmap

| Milestone | Goal | Status |
|---|---|---|
| 1 — Core pipeline | Top-down message → agents → graph writes | ✅ Done |
| 2 — SME Agent Phase A | Minimal script driver to automate pipeline validation | 🔄 Next |
| 3 — Bottom-up flow | tree-sitter + Gherkin parsers, file upload | Planned |
| 4 — GNN enrichment | GraphSAGE embeddings, agent retrieval by similarity | Planned |
| 5 — Robustness | Session persistence, confidence calibration, tests | Planned |
| 6 — Model flexibility | Ollama integration, per-agent model config | Planned |
| 7 — SME Agent Phase B | Full persona library, multi-domain simulation, benchmarks | Planned |

See `BACKLOG.md` for detailed task tracking and `CLAUDE.md` for implementation guidance.
