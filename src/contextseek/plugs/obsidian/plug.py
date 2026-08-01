"""Incremental DataPlug for Obsidian Markdown vaults."""

from __future__ import annotations

import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import Any, Callable, Iterator
from uuid import NAMESPACE_URL, uuid5

from contextseek.domain.links import Link, LinkType
from contextseek.plugs.core.protocols import PlugMeta, RawEvent


_STATE_VERSION = 1
_WIKILINK_RE = re.compile(r"\[\[([^\]]+)\]\]")


@dataclass
class ObsidianSyncStats:
    """Counts collected during one vault stream."""

    added: int = 0
    updated: int = 0
    deleted: int = 0
    skipped: int = 0

    @property
    def changed(self) -> int:
        return self.added + self.updated + self.deleted


@dataclass
class ObsidianVaultPlug:
    """Stream incremental changes from an Obsidian Markdown vault.

    A compact JSON cursor records each source path's mtime, size, content hash,
    and stable ContextItem id. The cursor is committed only after the stream is
    consumed successfully, so failed materialization is retried on the next run.
    """

    vault_path: str | Path
    state_path: str | Path | None = None
    sync_key: str = "default"
    persist_state: bool = True
    on_progress: Callable[[int, int, int], None] | None = None
    stats: ObsidianSyncStats = field(default_factory=ObsidianSyncStats, init=False)

    def metadata(self) -> PlugMeta:
        return PlugMeta(
            name="obsidian_vault",
            source_type="document",
            description="Incremental Obsidian Markdown vault import",
        )

    def stream(self) -> Iterator[RawEvent]:
        """Yield add/update/delete events and commit the cursor on success."""
        vault = Path(self.vault_path).expanduser().resolve()
        if not vault.is_dir():
            raise ValueError(f"Obsidian vault not found: {vault}")

        store = _CursorStore(self._resolved_state_path(vault))
        previous = store.load()
        vault_id = str(previous.get("vault_id") or _vault_id(vault))
        syncs = _valid_sync_records(previous.get("syncs"))
        old_files = _valid_file_records(syncs.get(self.sync_key, {}).get("files"))
        markdown_files = _markdown_files(vault)
        item_ids = {
            rel: str(old_files.get(rel, {}).get("item_id") or _item_id(vault_id, rel))
            for rel in markdown_files
        }
        lookup = _NoteLookup(item_ids)

        next_files: dict[str, dict[str, Any]] = {}
        deleted_files = [
            (rel, str(old_files[rel]["item_id"]))
            for rel in sorted(set(old_files) - set(markdown_files))
            if old_files[rel].get("item_id")
        ]
        self.stats = ObsidianSyncStats()
        total = len(markdown_files) + len(deleted_files)

        if total == 0 and self.on_progress is not None:
            self.on_progress(0, 0, 0)

        for rel, path in markdown_files.items():
            stat = path.stat()
            old = old_files.get(rel)
            raw = path.read_text(encoding="utf-8", errors="replace")
            digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
            record = {
                "mtime_ns": stat.st_mtime_ns,
                "size": stat.st_size,
                "content_hash": digest,
                "item_id": item_ids[rel],
            }
            next_files[rel] = record
            if old is not None and old.get("content_hash") == digest:
                self.stats.skipped += 1
                if self.on_progress is not None:
                    self.on_progress(
                        self.stats.changed,
                        self.stats.skipped,
                        total,
                    )
                continue

            operation = "update" if old is not None else "add"
            yield RawEvent(
                content=_indexable_markdown(raw),
                source=f"obsidian://{rel}",
                tags=["obsidian", "markdown"],
                metadata={"vault": str(vault), "path": rel},
                operation=operation,
                item_id=item_ids[rel],
                links=_wikilinks(raw, source=rel, lookup=lookup),
            )
            if operation == "add":
                self.stats.added += 1
            else:
                self.stats.updated += 1
            if self.on_progress is not None:
                self.on_progress(self.stats.changed, self.stats.skipped, total)

        for rel, item_id in deleted_files:
            yield RawEvent(
                content="",
                source=f"obsidian://{rel}",
                operation="delete",
                item_id=item_id,
            )
            self.stats.deleted += 1
            if self.on_progress is not None:
                self.on_progress(self.stats.changed, self.stats.skipped, total)

        if self.persist_state:
            syncs[self.sync_key] = {"files": next_files}
            store.save(
                {
                    "version": _STATE_VERSION,
                    "vault_id": vault_id,
                    "syncs": syncs,
                }
            )

    def _resolved_state_path(self, vault: Path) -> Path:
        if self.state_path is None:
            return vault / ".contextseek" / "obsidian-sync.json"
        return Path(self.state_path).expanduser().resolve()


class _CursorStore:
    def __init__(self, path: Path) -> None:
        self._path = path

    def load(self) -> dict[str, Any]:
        if not self._path.is_file():
            return {}
        try:
            data = json.loads(self._path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"Invalid Obsidian sync cursor: {self._path}") from exc
        if not isinstance(data, dict) or data.get("version") != _STATE_VERSION:
            raise ValueError(f"Unsupported Obsidian sync cursor: {self._path}")
        return data

    def save(self, data: dict[str, Any]) -> None:
        serialized = (
            json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
        if self._path.is_file():
            try:
                if self._path.read_text(encoding="utf-8") == serialized:
                    return
            except OSError:
                pass
        self._path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self._path.with_suffix(self._path.suffix + ".tmp")
        temporary.write_text(serialized, encoding="utf-8")
        temporary.replace(self._path)


class _NoteLookup:
    def __init__(self, item_ids: dict[str, str]) -> None:
        self._by_path = {_note_key(rel): item_id for rel, item_id in item_ids.items()}
        by_stem: dict[str, list[str]] = {}
        for rel, item_id in item_ids.items():
            by_stem.setdefault(PurePosixPath(rel).stem.casefold(), []).append(item_id)
        self._by_stem = {stem: ids[0] for stem, ids in by_stem.items() if len(ids) == 1}

    def resolve(self, target: str, *, source: str) -> str | None:
        clean = target.split("|", 1)[0].split("#", 1)[0].split("^", 1)[0].strip()
        if not clean:
            return None
        clean = clean.replace("\\", "/")
        source_dir = PurePosixPath(source).parent
        local = (source_dir / clean).as_posix()
        for candidate in (local, clean):
            item_id = self._by_path.get(_note_key(candidate))
            if item_id is not None:
                return item_id
        return self._by_stem.get(PurePosixPath(clean).stem.casefold())


def _valid_file_records(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): dict(record)
        for key, record in value.items()
        if isinstance(record, dict)
    }


def _valid_sync_records(value: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(value, dict):
        return {}
    return {
        str(key): dict(record)
        for key, record in value.items()
        if isinstance(record, dict)
    }


def _markdown_files(vault: Path) -> dict[str, Path]:
    files: dict[str, Path] = {}
    for root, dirnames, filenames in os.walk(vault, topdown=True, followlinks=False):
        root_path = Path(root)
        dirnames[:] = [
            name
            for name in sorted(dirnames)
            if not name.startswith(".") and not (root_path / name).is_symlink()
        ]
        for filename in sorted(filenames):
            if filename.startswith(".") or not filename.casefold().endswith(".md"):
                continue
            path = root_path / filename
            if path.is_symlink() or not path.is_file():
                continue
            files[path.relative_to(vault).as_posix()] = path
    return dict(sorted(files.items()))


def _vault_id(vault: Path) -> str:
    return uuid5(NAMESPACE_URL, f"contextseek:obsidian-vault:{vault.as_posix()}").hex


def _item_id(vault_id: str, rel: str) -> str:
    return uuid5(NAMESPACE_URL, f"contextseek:obsidian:{vault_id}:{rel}").hex


def _note_key(value: str) -> str:
    normalized = value.replace("\\", "/")
    if normalized.casefold().endswith(".md"):
        normalized = normalized[:-3]
    return normalized.strip("/").casefold()


def _wikilinks(raw: str, *, source: str, lookup: _NoteLookup) -> list[Link]:
    links: list[Link] = []
    seen: set[str] = set()
    for match in _WIKILINK_RE.finditer(raw):
        target_id = lookup.resolve(match.group(1), source=source)
        if target_id is None or target_id in seen:
            continue
        seen.add(target_id)
        links.append(Link(target_id=target_id, relation=LinkType.related_to))
    return links


def _indexable_markdown(raw: str) -> str:
    text = raw
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            text = text[end + 4 :]
    text = re.sub(r"\[\[([^\]|]+)\|([^\]]+)\]\]", r"\2", text)
    text = re.sub(r"\[\[([^\]]+)\]\]", r"\1", text)
    return text.strip()
