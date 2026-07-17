"""Domain models for ContextSeek — unified ContextItem model."""

from contextseek.domain.conflicts import (
    ConflictCheckResult,
    ConflictType,
    WriteConflict,
    detect_conflicts,
)
from contextseek.domain.context_item import ContextItem
from contextseek.domain.levels import ContentLevel
from contextseek.domain.evidence_chain import (
    ChainEdge,
    ChainNode,
    ConflictReport,
    EvidenceChain,
    compute_chain_confidence,
    compute_evidence_chain,
)
from contextseek.domain.inference import (
    build_provenance,
    infer_confidence,
    infer_stability,
    infer_stage,
)
from contextseek.domain.invalidation import (
    DegradedItem,
    InvalidationResult,
    propagate_invalidation,
)
from contextseek.domain.links import Link, LinkType
from contextseek.domain.link_graph import (
    LinkGraph,
    LinkGraphEdge,
    LinkGraphNode,
    build_link_graph,
)
from contextseek.domain.provenance import Provenance, SourceType
from contextseek.domain.results import (
    CompactReport,
    EvolutionReport,
    ResponseMeta,
    RetrieveResponse,
    SearchHit,
)
from contextseek.domain.serialization import (
    deserialize_context_item,
    serialize_context_item,
)
from contextseek.domain.stages import (
    STAGE_CONFIDENCE,
    STAGE_DEFAULT_STABILITY,
    Stability,
    Stage,
)
from contextseek.domain.tools import ToolSpec, default_tool_specs

__all__ = [
    "ChainEdge",
    "ChainNode",
    "CompactReport",
    "ConflictCheckResult",
    "ConflictReport",
    "ConflictType",
    "ContentLevel",
    "ContextItem",
    "DegradedItem",
    "EvolutionReport",
    "EvidenceChain",
    "InvalidationResult",
    "Link",
    "LinkGraph",
    "LinkGraphEdge",
    "LinkGraphNode",
    "LinkType",
    "Provenance",
    "ResponseMeta",
    "RetrieveResponse",
    "SearchHit",
    "SourceType",
    "Stability",
    "Stage",
    "STAGE_CONFIDENCE",
    "STAGE_DEFAULT_STABILITY",
    "ToolSpec",
    "WriteConflict",
    "default_tool_specs",
    "build_provenance",
    "build_link_graph",
    "compute_chain_confidence",
    "compute_evidence_chain",
    "deserialize_context_item",
    "detect_conflicts",
    "infer_confidence",
    "infer_stability",
    "infer_stage",
    "propagate_invalidation",
    "serialize_context_item",
]
