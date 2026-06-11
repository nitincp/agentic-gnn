"""
Pydantic models for agent-produced graph write payloads.

Each agent owns a subset of node/edge types. These models are used both as
Pydantic validators and as Anthropic tool input schemas (via model_json_schema()).
"""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# DDD Consultant — BoundedContext, Aggregate, DomainEvent, GlossaryTerm
# ---------------------------------------------------------------------------


class BoundedContextWrite(BaseModel):
    node_type: Literal["BoundedContext"] = "BoundedContext"
    id: str = Field(description="Unique slug, e.g. 'order-management'")
    name: str
    description: str


class AggregateWrite(BaseModel):
    node_type: Literal["Aggregate"] = "Aggregate"
    id: str = Field(description="Unique slug, e.g. 'order'")
    name: str
    bounded_context: str = Field(description="id of the parent BoundedContext")


class DomainEventWrite(BaseModel):
    node_type: Literal["DomainEvent"] = "DomainEvent"
    id: str = Field(description="Unique slug, e.g. 'order-placed'")
    name: str
    aggregate: str = Field(description="id of the emitting Aggregate")


class GlossaryTermWrite(BaseModel):
    node_type: Literal["GlossaryTerm"] = "GlossaryTerm"
    id: str = Field(description="Unique slug, e.g. 'ubiquitous-language-order'")
    term: str
    definition: str
    bounded_context: str = Field(description="id of the related BoundedContext")


class DDDOutput(BaseModel):
    """Top-level tool-use response from the DDD Consultant."""

    summary: str = Field(description="Brief plain-text explanation of the DDD model produced")
    confidence: float = Field(ge=0.0, le=1.0, description="How well-grounded this model is")
    bounded_contexts: list[BoundedContextWrite] = []
    aggregates: list[AggregateWrite] = []
    domain_events: list[DomainEventWrite] = []
    glossary_terms: list[GlossaryTermWrite] = []


# ---------------------------------------------------------------------------
# Test Engineer — GherkinFeature, GherkinScenario
# ---------------------------------------------------------------------------


class GherkinFeatureWrite(BaseModel):
    node_type: Literal["GherkinFeature"] = "GherkinFeature"
    id: str = Field(description="Unique slug, e.g. 'feature-order-placement'")
    title: str
    file_path: str = Field(
        default="", description="Logical file path, e.g. 'features/order.feature'"
    )


class GherkinScenarioWrite(BaseModel):
    node_type: Literal["GherkinScenario"] = "GherkinScenario"
    id: str = Field(description="Unique slug, e.g. 'scenario-place-order-success'")
    title: str
    steps: str = Field(description="Full Gherkin steps block as a single string")
    feature_id: str = Field(description="id of the parent GherkinFeature")
    domain_event_id: str = Field(
        default="", description="id of the DomainEvent this scenario covers (if known)"
    )


class TestEngineerOutput(BaseModel):
    """Top-level tool-use response from the Test Engineer."""

    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    features: list[GherkinFeatureWrite] = []
    scenarios: list[GherkinScenarioWrite] = []


# ---------------------------------------------------------------------------
# Developer — CodeModule, CodeClass, CodeFunction
# (used in bottom-up flow only; top-down skips this agent)
# ---------------------------------------------------------------------------


class CodeModuleWrite(BaseModel):
    node_type: Literal["CodeModule"] = "CodeModule"
    id: str = Field(description="Unique slug, e.g. 'module-order-service'")
    path: str
    language: str


class CodeClassWrite(BaseModel):
    node_type: Literal["CodeClass"] = "CodeClass"
    id: str = Field(description="Unique slug, e.g. 'class-order'")
    name: str
    module: str = Field(description="id of the parent CodeModule")


class CodeFunctionWrite(BaseModel):
    node_type: Literal["CodeFunction"] = "CodeFunction"
    id: str = Field(description="Unique slug, e.g. 'fn-place-order'")
    name: str
    module: str = Field(description="id of the containing CodeModule")


class DeveloperOutput(BaseModel):
    """Top-level tool-use response from the Developer agent."""

    summary: str
    confidence: float = Field(ge=0.0, le=1.0)
    modules: list[CodeModuleWrite] = []
    classes: list[CodeClassWrite] = []
    functions: list[CodeFunctionWrite] = []


# ---------------------------------------------------------------------------
# Edge writes — emitted alongside node writes
# ---------------------------------------------------------------------------


class EdgeWrite(BaseModel):
    edge_type: str = Field(description="EdgeType enum value, e.g. 'CONTAINS'")
    src_type: str = Field(description="NodeType of source node")
    src_id: str
    dst_type: str = Field(description="NodeType of destination node")
    dst_id: str


NodeWrite = Annotated[
    Union[
        BoundedContextWrite,
        AggregateWrite,
        DomainEventWrite,
        GlossaryTermWrite,
        GherkinFeatureWrite,
        GherkinScenarioWrite,
        CodeModuleWrite,
        CodeClassWrite,
        CodeFunctionWrite,
    ],
    Field(discriminator="node_type"),
]
