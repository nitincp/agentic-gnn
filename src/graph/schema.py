from enum import Enum


class NodeType(str, Enum):
    # Requirements layer
    REQUIREMENT = "Requirement"
    # DDD layer (bridge between requirements and code)
    BOUNDED_CONTEXT = "BoundedContext"
    AGGREGATE = "Aggregate"
    ENTITY = "Entity"
    VALUE_OBJECT = "ValueObject"
    DOMAIN_EVENT = "DomainEvent"
    GLOSSARY_TERM = "GlossaryTerm"
    # Test layer
    GHERKIN_FEATURE = "GherkinFeature"
    GHERKIN_SCENARIO = "GherkinScenario"
    # Code layer
    CODE_MODULE = "CodeModule"
    CODE_CLASS = "CodeClass"
    CODE_FUNCTION = "CodeFunction"


class EdgeType(str, Enum):
    # Requirements → DDD
    FULFILLS = "FULFILLS"
    # DDD internal
    CONTAINS = "CONTAINS"
    EMITS = "EMITS"
    MAPS_TO = "MAPS_TO"
    # DDD → Code
    IMPLEMENTED_BY = "IMPLEMENTED_BY"
    # DDD → Gherkin
    COVERED_BY = "COVERED_BY"
    # Ubiquitous language
    DEFINED_AS = "DEFINED_AS"
