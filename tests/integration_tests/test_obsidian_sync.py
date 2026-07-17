"""Integration coverage for incremental Obsidian vault sync."""

from __future__ import annotations

import shutil
from pathlib import Path

from seekvfs import VFS

from contextseek.client.contextseek import ContextSeek
from contextseek.daemon.sync_cmd import sync_path
from contextseek.domain.links import LinkType
from contextseek.storage.sqlite_backend import SQLiteBackend
from contextseek.storage.storage_adapter import SeekVFSStorageAdapter


FIXTURE_VAULT = Path(__file__).parents[1] / "fixtures" / "obsidian_vault"
SCOPE = "tests/obsidian/vault"


def _contextseek(tmp_path: Path) -> tuple[ContextSeek, SQLiteBackend]:
    backend = SQLiteBackend(path=str(tmp_path / "contextseek.sqlite3"))
    backend.initialize()
    vfs = VFS(
        routes={"contextseek://": {"backend": backend}},
        scheme="contextseek://",
    )
    return ContextSeek(adapter=SeekVFSStorageAdapter(vfs)), backend


def _copy_vault(tmp_path: Path) -> Path:
    vault = tmp_path / "vault"
    shutil.copytree(FIXTURE_VAULT, vault)
    return vault


def test_obsidian_sync_is_incremental_and_materializes_wikilinks(
    tmp_path: Path,
) -> None:
    vault = _copy_vault(tmp_path)
    ctx, backend = _contextseek(tmp_path)

    first = sync_path(ctx, vault, scope=SCOPE)

    assert first.format_detected == "obsidian_vault"
    assert (first.added, first.updated, first.deleted, first.skipped) == (2, 0, 0, 0)
    items = ctx.items(scope=SCOPE)
    by_source = {item.provenance.source_id: item for item in items}
    home = by_source["obsidian://Home.md"]
    alpha = by_source["obsidian://Projects/Alpha.md"]
    assert home.links == [
        next(
            link
            for link in home.links
            if link.target_id == alpha.id and link.relation is LinkType.related_to
        )
    ]

    original_write = ctx.adapter.write
    writes: list[str] = []

    def counting_write(ref: str, payload: dict) -> None:
        writes.append(ref)
        original_write(ref, payload)

    ctx.adapter.write = counting_write  # type: ignore[method-assign]
    second = sync_path(ctx, vault, scope=SCOPE)

    assert (second.added, second.updated, second.deleted, second.skipped) == (
        0,
        0,
        0,
        2,
    )
    assert writes == []

    alpha_path = vault / "Projects" / "Alpha.md"
    alpha_path.write_text(
        alpha_path.read_text(encoding="utf-8") + "\nOnly this note changed.\n",
        encoding="utf-8",
    )
    changed = sync_path(ctx, vault, scope=SCOPE)

    assert (changed.added, changed.updated, changed.deleted, changed.skipped) == (
        0,
        1,
        0,
        1,
    )
    assert len(writes) == 1
    updated_alpha = {
        item.provenance.source_id: item for item in ctx.items(scope=SCOPE)
    }["obsidian://Projects/Alpha.md"]
    assert updated_alpha.id == alpha.id
    assert "Only this note changed" in updated_alpha.content_text

    writes.clear()
    alpha_path.unlink()
    deleted = sync_path(ctx, vault, scope=SCOPE)

    assert (deleted.added, deleted.updated, deleted.deleted, deleted.skipped) == (
        0,
        0,
        1,
        1,
    )
    assert len(writes) == 1
    alpha_ref = ctx.resolver.ref_for(SCOPE, alpha.id)
    assert ctx._read_item(alpha_ref).is_deleted is True  # noqa: SLF001
    backend.close()


def test_obsidian_cursor_is_isolated_by_destination_scope(tmp_path: Path) -> None:
    vault = _copy_vault(tmp_path)
    ctx, backend = _contextseek(tmp_path)

    first = sync_path(ctx, vault, scope="tests/obsidian/first")
    second = sync_path(ctx, vault, scope="tests/obsidian/second")

    assert first.added == 2
    assert second.added == 2
    assert len(ctx.items(scope="tests/obsidian/first")) == 2
    assert len(ctx.items(scope="tests/obsidian/second")) == 2
    backend.close()
