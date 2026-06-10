import asyncio
import os
from typing import Literal

import chainlit as cl
from dotenv import load_dotenv

from src.graph.store import GraphStore
from src.graph.gnn import GNNEnrichment
from src.orchestration.council import Council

load_dotenv()


def get_council() -> Council:
    """Return session-scoped council, creating it on first access."""
    council = cl.user_session.get("council")
    if council is None:
        store = GraphStore()
        council = Council(store=store, model=os.getenv("MODEL_NAME", "claude-sonnet-4-6"))
        cl.user_session.set("council", council)

        # Start GNN enrichment in background if enabled
        if os.getenv("GNN_ENRICHMENT_ENABLED", "true").lower() == "true":
            gnn = GNNEnrichment(store)
            asyncio.create_task(gnn.start_background(interval_seconds=60))
            cl.user_session.set("gnn", gnn)

    return council


@cl.on_chat_start
async def on_start() -> None:
    get_council()
    await cl.Message(
        content=(
            "Welcome. I'm your Library Management System assistant.\n\n"
            "Tell me about your requirements, or upload a codebase/Gherkin files "
            "to start bottom-up analysis.\n\n"
            "Type `flow: bottom_up` at any point to switch modes."
        )
    ).send()


@cl.on_message
async def on_message(message: cl.Message) -> None:
    council = get_council()

    # Simple flow detection from message prefix
    flow: Literal["top_down", "bottom_up"] = cl.user_session.get("flow", "top_down")
    content = message.content.strip()

    if content.lower().startswith("flow:"):
        new_flow = content.split(":", 1)[1].strip().lower()
        if new_flow in ("top_down", "bottom_up"):
            cl.user_session.set("flow", new_flow)
            await cl.Message(content=f"Switched to `{new_flow}` mode.").send()
            return
        flow = flow  # keep current if invalid

    async with cl.Step(name="Council deliberating...") as step:
        response = await council.invoke(message=content, flow=flow)
        step.output = "Done"

    await cl.Message(content=response).send()
