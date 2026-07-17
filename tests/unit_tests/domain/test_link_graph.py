"""Tests for the bounded, all-relation link graph projection."""

from __future__ import annotations

from contextseek.domain.context_item import ContextItem
from contextseek.domain.link_graph import build_link_graph
from contextseek.domain.links import Link, LinkType
from contextseek.domain.provenance import Provenance, SourceType
from contextseek.domain.stages import Stage


def _item(
    item_id: str,
    *,
    links: list[Link] | None = None,
    content: str | None = None,
) -> ContextItem:
    return ContextItem(
        id=item_id,
        scope="tenant/project",
        content=content or f"content for {item_id}",
        links=links or [],
        stage=Stage.knowledge,
        provenance=Provenance(
            source_type=SourceType.document,
            source_id=f"doc://{item_id}",
            confidence=0.8,
        ),
    )


def test_link_graph_includes_every_relation_type() -> None:
    links = [
        Link(target_id=f"target-{relation.value}", relation=relation, strength=0.75)
        for relation in LinkType
    ]
    root = _item("root", links=links)
    targets = [_item(link.target_id) for link in links]

    graph = build_link_graph(root, [root, *targets], max_depth=1)

    assert {edge.relation for edge in graph.edges} == set(LinkType)
    assert all(edge.strength == 0.75 for edge in graph.edges)
    assert len(graph.nodes) == len(LinkType) + 1


def test_link_graph_traverses_incoming_links() -> None:
    root = _item("root")
    child = _item(
        "child",
        links=[Link(target_id="root", relation=LinkType.derived_from)],
    )

    graph = build_link_graph(root, [root, child], max_depth=1)

    assert {node.item_id for node in graph.nodes} == {"root", "child"}
    assert graph.edges[0].source_id == "child"
    assert graph.edges[0].target_id == "root"


def test_link_graph_represents_missing_targets() -> None:
    root = _item(
        "root",
        links=[Link(target_id="missing", relation=LinkType.refuted_by)],
    )

    graph = build_link_graph(root, [root], max_depth=1)

    missing = next(node for node in graph.nodes if node.item_id == "missing")
    assert missing.is_missing is True
    assert missing.confidence == 0.0


def test_link_graph_caps_large_neighborhoods() -> None:
    root = _item(
        "root",
        links=[
            Link(target_id=f"target-{index}", relation=LinkType.related_to)
            for index in range(10)
        ],
    )
    targets = [_item(f"target-{index}") for index in range(10)]

    graph = build_link_graph(root, [root, *targets], max_depth=1, max_nodes=4)

    assert len(graph.nodes) == 4
    assert graph.truncated is True
    assert all(
        edge.source_id in {node.item_id for node in graph.nodes}
        and edge.target_id in {node.item_id for node in graph.nodes}
        for edge in graph.edges
    )
