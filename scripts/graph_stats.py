#!/usr/bin/env python3
"""
Run this after each successful prompt to inspect the graph state.
Usage: python3 scripts/graph_stats.py
Stop the Chainlit app first (Kuzu allows only one connection).
"""

from src.graph.schema import NodeType
from src.graph.store import GraphStore

s = GraphStore()

NODE_TYPES = [
    NodeType.BOUNDED_CONTEXT,
    NodeType.AGGREGATE,
    NodeType.DOMAIN_EVENT,
    NodeType.GLOSSARY_TERM,
    NodeType.GHERKIN_FEATURE,
    NodeType.GHERKIN_SCENARIO,
    NodeType.CODE_MODULE,
    NodeType.CODE_CLASS,
    NodeType.CODE_FUNCTION,
    NodeType.REQUIREMENT,
]

EDGE_QUERIES = {
    "CONTAINS  (BC→Agg)": "MATCH (:BoundedContext)-[r:CONTAINS]->(:Aggregate) RETURN count(r)",  # noqa: E501
    "EMITS     (Agg→Event)": "MATCH (:Aggregate)-[r:EMITS]->(:DomainEvent) RETURN count(r)",
    "DEFINED_AS(Term→BC)": "MATCH (:GlossaryTerm)-[r:DEFINED_AS]->(:BoundedContext) RETURN count(r)",  # noqa: E501
    "COVERED_BY(Event→Scen)": "MATCH (:DomainEvent)-[r:COVERED_BY]->(:GherkinScenario) RETURN count(r)",  # noqa: E501
    "FULFILLS  (Req→BC)": "MATCH (:Requirement)-[r:FULFILLS]->(:BoundedContext) RETURN count(r)",  # noqa: E501
    "IMPL_BY   (Agg→Module)": "MATCH (:Aggregate)-[r:IMPLEMENTED_BY]->(:CodeModule) RETURN count(r)",  # noqa: E501
}

# --- Node counts ---
print("=" * 50)
print("NODE COUNTS")
print("=" * 50)
total_nodes = 0
for nt in NODE_TYPES:
    rows = s.query(f"MATCH (n:{nt}) RETURN count(n)")
    count = rows[0][0] if rows else 0
    if count > 0:
        print(f"  {nt.value:<22} {count:>4}")
        total_nodes += count
print(f"  {'TOTAL':<22} {total_nodes:>4}")

# --- Edge counts ---
print()
print("=" * 50)
print("EDGE COUNTS")
print("=" * 50)
total_edges = 0
for label, q in EDGE_QUERIES.items():
    rows = s.query(q)
    count = rows[0][0] if rows else 0
    if count > 0:
        print(f"  {label:<28} {count:>4}")
        total_edges += count
print(f"  {'TOTAL':<28} {total_edges:>4}")

# --- DDD layer detail ---
print()
print("=" * 50)
print("DDD LAYER")
print("=" * 50)
for row in s.query("MATCH (bc:BoundedContext) RETURN bc.id, bc.name"):
    aggs = s.query(
        "MATCH (bc:BoundedContext {id: $id})-[:CONTAINS]->(a:Aggregate) RETURN a.name",
        {"id": row[0]},
    )
    events = s.query(
        "MATCH (bc:BoundedContext {id: $id})-[:CONTAINS]->(a:Aggregate)-[:EMITS]->(e:DomainEvent) RETURN e.name",  # noqa: E501
        {"id": row[0]},
    )
    agg_names = ", ".join(r[0] for r in aggs) or "—"
    event_names = ", ".join(r[0] for r in events) or "—"
    print(f"  BC: {row[1]}")
    print(f"    Aggregates:    {agg_names}")
    print(f"    Domain Events: {event_names}")

# --- Gherkin coverage ---
print()
print("=" * 50)
print("GHERKIN COVERAGE")
print("=" * 50)
total_events = s.query("MATCH (n:DomainEvent) RETURN count(n)")
covered = s.query("MATCH (:DomainEvent)-[:COVERED_BY]->(:GherkinScenario) RETURN count(DISTINCT 0)")
features = s.query("MATCH (n:GherkinFeature) RETURN count(n)")
scenarios = s.query("MATCH (n:GherkinScenario) RETURN count(n)")
n_events = total_events[0][0] if total_events else 0
n_covered = covered[0][0] if covered else 0
n_features = features[0][0] if features else 0
n_scenarios = scenarios[0][0] if scenarios else 0
print(f"  Features:  {n_features}")
print(f"  Scenarios: {n_scenarios}")
print(f"  Events covered: {n_covered}/{n_events}")

s.close()
