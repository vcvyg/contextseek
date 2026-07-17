"""Bounded link-graph projection for dashboard and API consumers."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import dataclass
from typing import Any

from contextseek.domain.context_item import ContextItem
from contextseek.domain.links import LinkType
from contextseek.domain.stages import Stage


@dataclass(frozen=True)
class LinkGraphNode:
    """One visible item (or unresolved target) in a link graph."""

    item_id: str
    stage: Stage
    confidence: float
    depth: int
    is_root: bool
    is_missing: bool
    content_preview: str


@dataclass(frozen=True)
class LinkGraphEdge:
    """One directed ContextItem link in a link graph."""

    source_id: str
    target_id: str
    relation: LinkType
    strength: float


@dataclass(frozen=True)
class LinkGraph:
    """A bounded, connected projection centered on one item."""

    root_item_id: str
    nodes: list[LinkGraphNode]
    edges: list[LinkGraphEdge]
    max_depth: int
    max_nodes: int
    truncated: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_item_id": self.root_item_id,
            "nodes": [
                {
                    "item_id": node.item_id,
                    "stage": node.stage.value,
                    "confidence": node.confidence,
                    "depth": node.depth,
                    "is_root": node.is_root,
                    "is_missing": node.is_missing,
                    "content_preview": node.content_preview,
                }
                for node in self.nodes
            ],
            "edges": [
                {
                    "source_id": edge.source_id,
                    "target_id": edge.target_id,
                    "relation": edge.relation.value,
                    "strength": edge.strength,
                }
                for edge in self.edges
            ],
            "max_depth": self.max_depth,
            "max_nodes": self.max_nodes,
            "truncated": self.truncated,
        }


def build_link_graph(
    root: ContextItem,
    items: list[ContextItem],
    *,
    max_depth: int = 3,
    max_nodes: int = 100,
) -> LinkGraph:
    """Build a bounded graph that follows both incoming and outgoing links.

    Traversal is undirected so selecting either end of a relation reveals its
    local neighborhood. Returned edges retain their original direction.
    """
    if max_depth < 0:
        raise ValueError("max_depth must be non-negative")
    if max_nodes < 1:
        raise ValueError("max_nodes must be at least 1")

    item_by_id = {item.id: item for item in items}
    item_by_id[root.id] = root
    all_edges: list[LinkGraphEdge] = []
    neighbors: dict[str, set[str]] = defaultdict(set)
    for item in item_by_id.values():
        for link in item.links:
            edge = LinkGraphEdge(
                source_id=item.id,
                target_id=link.target_id,
                relation=link.relation,
                strength=max(0.0, min(1.0, float(link.strength))),
            )
            all_edges.append(edge)
            neighbors[item.id].add(link.target_id)
            neighbors[link.target_id].add(item.id)

    depth_by_id = {root.id: 0}
    queue: deque[str] = deque([root.id])
    truncated = False
    while queue:
        item_id = queue.popleft()
        depth = depth_by_id[item_id]
        if depth >= max_depth:
            continue
        for neighbor_id in sorted(neighbors[item_id]):
            if neighbor_id in depth_by_id:
                continue
            if len(depth_by_id) >= max_nodes:
                truncated = True
                continue
            depth_by_id[neighbor_id] = depth + 1
            queue.append(neighbor_id)

    visible_ids = set(depth_by_id)
    graph_nodes: list[LinkGraphNode] = []
    for item_id, depth in sorted(
        depth_by_id.items(), key=lambda entry: (entry[1], entry[0])
    ):
        item = item_by_id.get(item_id)
        if item is None:
            graph_nodes.append(
                LinkGraphNode(
                    item_id=item_id,
                    stage=Stage.raw,
                    confidence=0.0,
                    depth=depth,
                    is_root=False,
                    is_missing=True,
                    content_preview="",
                )
            )
            continue
        confidence = (
            item.effective_confidence
            if item.effective_confidence is not None
            else item.provenance.confidence
        )
        preview = " ".join(item.content_text.split())[:160]
        graph_nodes.append(
            LinkGraphNode(
                item_id=item.id,
                stage=item.stage,
                confidence=max(0.0, min(1.0, float(confidence))),
                depth=depth,
                is_root=item.id == root.id,
                is_missing=False,
                content_preview=preview,
            )
        )

    graph_edges = [
        edge
        for edge in all_edges
        if edge.source_id in visible_ids and edge.target_id in visible_ids
    ]
    graph_edges.sort(
        key=lambda edge: (edge.source_id, edge.target_id, edge.relation.value)
    )
    return LinkGraph(
        root_item_id=root.id,
        nodes=graph_nodes,
        edges=graph_edges,
        max_depth=max_depth,
        max_nodes=max_nodes,
        truncated=truncated,
    )
