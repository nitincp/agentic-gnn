"""
GNN enrichment pass — runs asynchronously in the background.
Reads the current graph from Kuzu, produces node embeddings,
and writes them back for agent retrieval.
"""

import asyncio
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .store import GraphStore


class GNNEnrichment:
    """Async background GNN enrichment pass over the GraphStore."""

    def __init__(self, store: "GraphStore") -> None:
        self._store = store
        self._running = False

    async def run_pass(self) -> None:
        """Single enrichment pass: graph → PyG → embeddings → store."""
        # TODO: implement full GNN pipeline
        # 1. Export graph from Kuzu to PyG HeteroData
        # 2. Run GNN forward pass (GraphSAGE or GAT)
        # 3. Write embeddings back as node properties
        await asyncio.sleep(0)  # placeholder

    async def start_background(self, interval_seconds: int = 60) -> None:
        """Run enrichment passes on a background loop."""
        self._running = True
        while self._running:
            await self.run_pass()
            await asyncio.sleep(interval_seconds)

    def stop(self) -> None:
        self._running = False
