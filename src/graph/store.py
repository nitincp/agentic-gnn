import os
from pathlib import Path
from typing import Any

import kuzu

from .schema import EdgeType, NodeType


class GraphStore:
    """Kuzu-backed graph store. Embedded, no server required."""

    def __init__(self, db_path: str | None = None) -> None:
        path = db_path or os.getenv("KUZU_DB_PATH", "data/kuzu")
        Path(path).parent.mkdir(parents=True, exist_ok=True)
        self._db = kuzu.Database(path)
        self._conn = kuzu.Connection(self._db)
        self._init_schema()

    def _init_schema(self) -> None:
        node_schemas = {
            NodeType.REQUIREMENT: "id STRING, title STRING, body STRING, source STRING",
            NodeType.BOUNDED_CONTEXT: "id STRING, name STRING, description STRING",
            NodeType.AGGREGATE: "id STRING, name STRING, bounded_context STRING",
            NodeType.ENTITY: "id STRING, name STRING, aggregate STRING",
            NodeType.VALUE_OBJECT: "id STRING, name STRING, aggregate STRING",
            NodeType.DOMAIN_EVENT: "id STRING, name STRING, aggregate STRING",
            NodeType.GLOSSARY_TERM: "id STRING, term STRING, definition STRING",
            NodeType.GHERKIN_FEATURE: "id STRING, title STRING, file_path STRING",
            NodeType.GHERKIN_SCENARIO: "id STRING, title STRING, steps STRING",
            NodeType.CODE_MODULE: "id STRING, path STRING, language STRING",
            NodeType.CODE_CLASS: "id STRING, name STRING, module STRING",
            NodeType.CODE_FUNCTION: "id STRING, name STRING, module STRING",
        }

        edge_schemas = {
            EdgeType.FULFILLS: (NodeType.REQUIREMENT, NodeType.BOUNDED_CONTEXT),
            EdgeType.CONTAINS: (NodeType.BOUNDED_CONTEXT, NodeType.AGGREGATE),
            EdgeType.EMITS: (NodeType.AGGREGATE, NodeType.DOMAIN_EVENT),
            EdgeType.MAPS_TO: (NodeType.BOUNDED_CONTEXT, NodeType.BOUNDED_CONTEXT),
            EdgeType.IMPLEMENTED_BY: (NodeType.AGGREGATE, NodeType.CODE_MODULE),
            EdgeType.COVERED_BY: (NodeType.DOMAIN_EVENT, NodeType.GHERKIN_SCENARIO),
            EdgeType.DEFINED_AS: (NodeType.GLOSSARY_TERM, NodeType.BOUNDED_CONTEXT),
        }

        for node_type, props in node_schemas.items():
            try:
                self._conn.execute(
                    f"CREATE NODE TABLE IF NOT EXISTS {node_type} ({props}, PRIMARY KEY (id))"
                )
            except Exception:
                pass  # table already exists

        for edge_type, (src, dst) in edge_schemas.items():
            try:
                self._conn.execute(
                    f"CREATE REL TABLE IF NOT EXISTS {edge_type} (FROM {src} TO {dst})"
                )
            except Exception:
                pass  # table already exists

    # Allowed node properties per type — guards against extra relational fields
    _NODE_PROPS: dict[str, set[str]] = {
        NodeType.REQUIREMENT: {"id", "title", "body", "source"},
        NodeType.BOUNDED_CONTEXT: {"id", "name", "description"},
        NodeType.AGGREGATE: {"id", "name", "bounded_context"},
        NodeType.ENTITY: {"id", "name", "aggregate"},
        NodeType.VALUE_OBJECT: {"id", "name", "aggregate"},
        NodeType.DOMAIN_EVENT: {"id", "name", "aggregate"},
        NodeType.GLOSSARY_TERM: {"id", "term", "definition"},
        NodeType.GHERKIN_FEATURE: {"id", "title", "file_path"},
        NodeType.GHERKIN_SCENARIO: {"id", "title", "steps"},
        NodeType.CODE_MODULE: {"id", "path", "language"},
        NodeType.CODE_CLASS: {"id", "name", "module"},
        NodeType.CODE_FUNCTION: {"id", "name", "module"},
    }

    def _run(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[Any]:
        result = self._conn.execute(cypher, parameters=parameters or {})
        assert isinstance(result, kuzu.QueryResult)
        return result.get_all()

    def write_node(self, node_type: NodeType, properties: dict[str, Any]) -> None:
        allowed = self._NODE_PROPS.get(node_type)
        if allowed:
            properties = {k: v for k, v in properties.items() if k in allowed}
        node_id = properties["id"]
        exists = self._run(
            f"MATCH (n:{node_type} {{id: $id}}) RETURN count(n)",
            {"id": node_id},
        )
        if exists and exists[0][0] > 0:
            for key, val in properties.items():
                if key == "id":
                    continue
                self._run(
                    f"MATCH (n:{node_type} {{id: $id}}) SET n.{key} = $val",
                    {"id": node_id, "val": val},
                )
        else:
            # Kuzu named params don't work inside inline node literals — use positional
            keys = list(properties.keys())
            cols = ", ".join(f"{k}: ${i + 1}" for i, k in enumerate(keys))
            params = {str(i + 1): properties[k] for i, k in enumerate(keys)}
            self._run(f"CREATE (:{node_type} {{{cols}}})", params)

    def write_edge(
        self,
        edge_type: EdgeType,
        src_type: NodeType,
        src_id: str,
        dst_type: NodeType,
        dst_id: str,
    ) -> None:
        exists = self._run(
            f"MATCH (a:{src_type} {{id: $src_id}})-[r:{edge_type}]->(b:{dst_type} {{id: $dst_id}})"
            " RETURN count(r)",
            {"src_id": src_id, "dst_id": dst_id},
        )
        if exists and exists[0][0] > 0:
            return
        self._run(
            f"MATCH (a:{src_type} {{id: $src_id}}), (b:{dst_type} {{id: $dst_id}})"
            f" CREATE (a)-[:{edge_type}]->(b)",
            {"src_id": src_id, "dst_id": dst_id},
        )

    def query(self, cypher: str, parameters: dict[str, Any] | None = None) -> list[Any]:
        return self._run(cypher, parameters)

    def close(self) -> None:
        self._conn.close()
