"""End-to-end checks on the three examples. Run with `python tests/test_examples.py` or pytest."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CLI = ROOT / "scripts" / "underneath.py"
EX = ROOT / "examples"


def run(example: str):
    out = Path(tempfile.mkdtemp(prefix=f"underneath-{example}-"))
    base = EX / example
    r = subprocess.run(
        [sys.executable, CLI, "extract", "--before", base / "before", "--after", base / "after", "--out", out],
        capture_output=True, text=True, check=True,
    )
    graph = json.loads((out / "graph.json").read_text())
    shutil.copy(base / "notes.json", out / "notes.json")
    c = subprocess.run([sys.executable, CLI, "render", "--out", out], capture_output=True, text=True, check=True)
    return graph, r.stdout, c.stdout, c.stderr, out


def labels(graph, status=None):
    return {n["label"] for n in graph["nodes"] if status is None or n["status"] == status}


def edge(graph, a, b, typ):
    ids = {n["label"]: n["id"] for n in graph["nodes"]}
    return any(e["from"] == ids.get(a) and e["to"] == ids.get(b) and e["type"] == typ for e in graph["edges"])


def test_react():
    g, brief, card, err, out = run("react-search")
    assert labels(g, "new") == {"SearchUsers", "useDebounce", "searchUsers", "sortUsers"}
    assert labels(g, "modified") == {"App"}
    assert next(n for n in g["nodes"] if n["hub"])["label"] == "SearchUsers"
    assert edge(g, "SearchUsers", "useDebounce", "calls")
    assert edge(g, "SearchUsers", "UserList", "renders")
    concepts = {c["id"] for c in g["concepts"]}
    assert {"react.useEffect", "react.effectCleanup", "web.AbortController"} <= concepts
    assert "closures" in g["fundamental_candidates"]
    assert len(card.strip().splitlines()) <= 5
    assert "SearchUsers.tsx:21" in card
    assert err.strip() == "", err
    assert (out / "latest.html").read_text().count('class="nd') >= 10


def test_python():
    g, brief, card, err, _ = run("python-dashboard")
    assert edge(g, "load_dashboard", "cached", "decorated by")
    assert edge(g, "load_dashboard", "fetch_orders", "calls")
    assert "get_session" in labels(g, "context")
    assert g["concepts"][0]["id"] == "py.mutableDefault"  # risks come first
    assert "LIKELY BUG" in brief
    assert "services.py:17" in card


def test_sql():
    g, brief, card, err, _ = run("sql-orders")
    assert edge(g, "user_order_stats", "orders", "reads")
    assert edge(g, "user_order_stats", "users", "reads")
    assert edge(g, "idx_orders_user_created", "orders", "indexes")
    assert edge(g, "top_customers", "user_order_stats", "reads")
    assert any(c["id"] == "sql.leftJoinWhere" for c in g["concepts"])
    assert "three-valued logic" in card


def test_notes_are_validated():
    _, _, _, _, out = run("react-search")
    (out / "notes.json").write_text(json.dumps({
        "nodes": {"n99": {"summary": "invented"}},
        "concepts": {"react.useImaginary": {"here": "x"}},
        "inferred_edges": [{"from": "n1", "to": "n42", "label": "x"}],
        "watch": [{"node": "n6", "text": "context nodes cannot be watched"}],
        "fundamental": {"id": "quantum-physics"},
    }))
    c = subprocess.run([sys.executable, CLI, "render", "--out", out], capture_output=True, text=True, check=True)
    for bit in ("n99", "react.useImaginary", "n42", "'n6'", "quantum-physics"):
        assert bit in c.stderr, bit
    assert "⚠" not in c.stdout


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
