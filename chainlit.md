# Senatus

**Council of deliberation for SDLC automation.**

A trio of LLM agents — DDD Consultant, Developer, Test Engineer — deliberate over your requirements and write structured artifacts to a knowledge graph.

## How to use

**Top-down** (greenfield): Describe your domain or requirements in natural language. The council will produce bounded contexts, aggregates, domain events, glossary terms, and Gherkin scenarios.

**Bottom-up** (existing codebase): Type `flow: bottom_up` then describe your system, or upload source files. The council infers the DDD model from the code.

**Switch modes** at any time:
```
flow: bottom_up
flow: top_down
```

Each response includes a token usage table so you can track cost per turn.
