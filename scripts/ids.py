"""Identifiers shared by render.py and the Stop hook. No third-party imports."""

from __future__ import annotations

import hashlib
import json


def change_id(graph: dict) -> str:
    """Identifies the change itself: the changed symbols and files, nothing that the registry moves.

    Concept ranking depends on what the developer has already seen, so concepts are left out:
    rendering a card must not make the same diff look like a new one.
    """
    s = graph.get("summary", {})
    core = {
        "changed": sorted(
            [n["file"], n["label"], n["status"], n.get("source", "")] for n in graph.get("nodes", []) if n.get("status") != "context"
        ),
        "files": s.get("files", []),
        "hidden": s.get("hidden_changed", []),
        "removed": s.get("removed", []),
    }
    return hashlib.sha1(json.dumps(core, sort_keys=True).encode()).hexdigest()[:12]
