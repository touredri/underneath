"""End-to-end checks on the examples. Run with `python tests/test_examples.py` or pytest."""

from __future__ import annotations

import json
import os
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


# ----------------------------------------------------- v0.2 dogfood fixes ---

sys.path.insert(0, str(ROOT / "scripts"))


def _git_scope(example: str):
    """A throwaway git repo: `before` committed, `after` in the working tree."""
    from diffscope import from_git

    repo = Path(tempfile.mkdtemp(prefix=f"underneath-git-{example}-"))
    shutil.copytree(EX / example / "before", repo, dirs_exist_ok=True)
    git = ["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid", "-c", "commit.gpgsign=false"]
    subprocess.run([*git, "init", "-q"], cwd=repo, check=True)
    subprocess.run([*git, "add", "-A"], cwd=repo, check=True)
    subprocess.run([*git, "commit", "-q", "-m", "before"], cwd=repo, check=True)
    for p in repo.iterdir():
        if p.name != ".git":
            shutil.rmtree(p) if p.is_dir() else p.unlink()
    shutil.copytree(EX / example / "after", repo, dirs_exist_ok=True)
    return from_git(repo, "HEAD")


def _full_parse_graph(scope):
    """The graph as v0.1 built it: every file of the universe parsed."""
    import graph
    from concepts import load_concepts

    saved = graph.neighbour_files
    graph.neighbour_files = lambda sc, changed, suffixes: set(sc.universe) - set(sc.new)
    try:
        return graph.build(scope, load_concepts(ROOT / "references"), {})
    finally:
        graph.neighbour_files = saved


def test_only_neighbours_are_parsed():
    """Fix 1 (speed): unrelated files are skipped, and the graph is the same as a full parse."""
    import graph
    from concepts import load_concepts
    from diffscope import from_dirs
    from parse import parse_file

    cat = load_concepts(ROOT / "references")
    for scope in (from_dirs(EX / "js-neighbours" / "before", EX / "js-neighbours" / "after"), _git_scope("js-neighbours")):
        g = graph.build(scope, cat, {})
        changed = [s for rel, text in scope.new.items() for s in parse_file(rel, text)]
        parsed = set(scope.new) | graph.neighbour_files(scope, changed, graph._suffix_index(set(scope.universe)))
        assert "src/money.ts" in parsed  # defines formatPrice, called by addItem
        assert "src/unrelated.ts" not in parsed
        assert "src/audit.ts" not in parsed  # log() is defined in 4 files: the name alone links nothing
        assert g == _full_parse_graph(scope), "selective parse changed the graph"
        assert edge(g, "addItem", "formatPrice", "calls")
        assert edge(g, "startCheckout", "addItem", "calls")
        assert "log" not in labels(g)
    g, _, card, err, _ = run("js-neighbours")
    assert err.strip() == "", err
    assert len(card.strip().splitlines()) <= 5


def test_same_diff_same_map():
    """Fix 1 (determinism): context and links never depend on Python's hash order."""
    outs = []
    for seed in ("1", "2", "3"):
        out = Path(tempfile.mkdtemp(prefix="underneath-seed-"))
        base = EX / "python-dashboard"
        subprocess.run(
            [sys.executable, CLI, "extract", "--before", base / "before", "--after", base / "after", "--out", out],
            capture_output=True, text=True, check=True, env={**os.environ, "PYTHONHASHSEED": seed},
        )
        outs.append((out / "graph.json").read_text())
    assert outs[0] == outs[1] == outs[2]


def test_moved_code_is_not_new():
    """Fix 2: a component moved to its own file reads as moved, not as new + removed."""
    g, brief, card, err, out = run("react-move")
    by = {n["label"]: n for n in g["nodes"]}
    assert by["StatCard"]["status"] == "moved"
    assert by["StatCard"]["moved_from"] == "src/Dashboard.jsx:3"
    assert by["TripList"]["status"] == "modified"  # moved and edited
    assert by["TripList"]["moved_from"] == "src/Dashboard.jsx:12"
    assert by["DashboardHeader"]["status"] == "moved"  # pulled out of Dashboard's JSX, new name
    assert by["DashboardHeader"]["moved_from"] == "src/Dashboard.jsx:24"
    assert by["EmptyState"]["status"] == "new"
    assert g["summary"]["removed"] == []
    assert g["summary"]["added_lines"] <= 22, g["summary"]["added_lines"]  # v0.1 counted 37: moved lines are not new
    head = card.splitlines()[0]
    assert "1 new" in head and "2 moved" in head and "removed" not in head, head
    assert "moved from src/Dashboard.jsx:3" in brief
    assert err.strip() == "", err
    assert 'class="nd fn-mov' in (out / "latest.html").read_text()


def test_tests_are_not_nodes():
    """Fix 3: test functions become "tested by N", their concepts are not counted."""
    g, brief, card, err, _ = run("python-tests")
    assert not any(n["test"] or n["label"].startswith("test_") for n in g["nodes"])
    by = {n["label"]: n for n in g["nodes"]}
    assert len(by["total"]["tested_by"]) == 2
    assert len(by["apply_discount"]["tested_by"]) == 1
    assert g["summary"]["tests"] == 3
    assert g["summary"]["new"] == 1 and g["summary"]["modified"] == 1
    assert "py.contextManager" not in {c["id"] for c in g["concepts"]}  # `with pytest.raises` is in the test only
    assert "3 tests" in card.splitlines()[0]
    assert err.strip() == "", err


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
