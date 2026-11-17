"""Optional: callers of the changed functions from a Graphify graph (github.com/Graphify-Labs/graphify).

When `graphify-out/graph.json` exists in the repository, or in a parent folder
that holds several repositories (up to two levels up), its `calls` edges add
callers that underneath's own scan cannot see: code in another repository of
the workspace, or files outside the scan. Only edges Graphify marks
EXTRACTED (read from a syntax tree) are used; its INFERRED edges are not.

Read-only, local, off with `"graphify": false` in `.underneath/config.json`.
"""

from __future__ import annotations

import json
import re
from collections import defaultdict
from pathlib import Path

LEVELS = 2
_LINE = re.compile(r"L(\d+)")


def _short(label: str) -> str:
    """`.execute()` / `execute()` / `Billing.execute` -> `execute`."""
    return label.strip().lstrip(".").split("(")[0].split(".")[-1]


def find(root: Path) -> tuple[Path, str] | None:
    """(graph.json, prefix of the repository inside the graph's root) or None."""
    here = root.resolve()
    for up in range(LEVELS + 1):
        base = here.parents[up - 1] if up else here
        path = base / "graphify-out" / "graph.json"
        if path.is_file():
            prefix = here.relative_to(base).as_posix()
            return path, "" if prefix == "." else prefix + "/"
    return None


class Graph:
    def __init__(self, path: Path, prefix: str):
        data = json.loads(path.read_text(encoding="utf8"))
        self.path, self.prefix = path, prefix
        self.built_at = data.get("built_at_commit") or ""
        self.nodes = {n["id"]: n for n in data.get("nodes", []) if "id" in n}
        self.callers: dict[str, list[str]] = defaultdict(list)  # target node id -> caller node ids
        for link in data.get("links", data.get("edges", [])):
            if link.get("relation") == "calls" and link.get("confidence", "EXTRACTED") == "EXTRACTED":
                self.callers[link.get("target")].append(link.get("source"))
        self.by_place: dict[tuple[str, str], list[str]] = defaultdict(list)  # (file, name) -> node ids
        for nid, n in self.nodes.items():
            if n.get("source_file"):
                self.by_place[(n["source_file"], _short(n.get("label", "")))].append(nid)

    def _line(self, nid: str) -> int:
        m = _LINE.match(str(self.nodes[nid].get("source_location", "")))
        return int(m.group(1)) if m else 0

    def callers_of(self, file: str, name: str, line: int) -> list[dict]:
        """Callers of the function `name` in `file` (repository-relative), with their place."""
        cands = self.by_place.get((self.prefix + file, name), [])
        if not cands:
            return []
        target = min(cands, key=lambda nid: abs(self._line(nid) - line))  # the graph may predate the change
        out = []
        for src in self.callers.get(target, []):
            n = self.nodes.get(src)
            if not n or not n.get("source_file"):
                continue
            f = n["source_file"]
            inside = f.startswith(self.prefix) if self.prefix else True
            out.append({
                "name": _short(n.get("label", "")) or "?",
                "file": f[len(self.prefix):] if inside and self.prefix else f,
                "outside": not inside,  # in another repository of the workspace
                "line": self._line(src),
            })
        return out


def load(root: Path, config: dict) -> Graph | None:
    if config.get("graphify") is False:
        return None
    found = find(root)
    if found is None:
        return None
    try:
        return Graph(*found)
    except (OSError, ValueError, KeyError, TypeError):
        return None
