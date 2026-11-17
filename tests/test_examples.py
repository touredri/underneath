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

    return from_git(_git_repo(example), "HEAD")


def _git_repo(example: str) -> Path:
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
    return repo


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


def test_extract_cache():
    """Parsed symbols are cached by content: same graph from the cache, a broken cache is ignored."""
    repo = _git_repo("react-search")
    def extract():
        subprocess.run([sys.executable, CLI, "extract"], cwd=repo, capture_output=True, check=True)
        return json.loads((repo / ".underneath" / "graph.json").read_text())
    first = extract()
    cache = repo / ".underneath" / "cache" / "symbols.json"
    assert cache.exists() and json.loads(cache.read_text())["files"]
    assert extract() == first  # from the cache
    cache.write_text("not json {")
    assert extract() == first  # rebuilt
    assert json.loads(cache.read_text())["files"]


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


def test_minor_concepts_rank_last():
    """Basics that are everywhere (keys, event handler props) give way to concepts that say more."""
    import graph
    from concepts import detect, load_concepts
    from diffscope import from_dirs
    from parse import parse_file

    cat = load_concepts(ROOT / "references")
    case = ROOT / "evals" / "cases" / "react-memo-list"
    g = graph.build(from_dirs(case / "before", case / "after"), cat, {})
    shown = {c["id"] for c in g["concepts"]}
    assert shown == {"react.memo", "react.useMemo", "react.useCallback", "react.useRef", "react.useState"}, shown
    assert {"react.keys", "react.callbackProps"} <= set(g["summary"]["more_concept_ids"])  # still listed, one click away
    init = parse_file("a.py", "class A:\n    def __init__(self):\n        self.x = 1\n\n    def __len__(self):\n        return 1\n")
    assert [(s.kind, detect(s, cat)) for s in init] == [("class", []), ("method", []), ("method", ["py.dunder"])]  # __init__ is no lesson


# ------------------------------------------------------------ map, gaps ---


def _project(cmd: str, root: Path, out: Path):
    r = subprocess.run([sys.executable, CLI, cmd, "--root", root, "--out", out], capture_output=True, text=True, check=True)
    return r.stdout


def _project_out() -> Path:
    out = Path(tempfile.mkdtemp(prefix="underneath-map-"))
    shutil.copy(EX / "project-map" / "registry.json", out / "registry.json")
    return out


def test_map():
    out = _project_out()
    card = _project("map", EX / "project-map", out)
    lines = card.strip().splitlines()
    assert len(lines) <= 5, card
    assert lines[0].startswith("underneath map · 5 files · 7 functions · 13 concepts on 8 fundamentals"), lines[0]
    assert "py.dataclass" in json.loads((out / "map.json").read_text())["concepts"]  # a decorator on a class counts now
    assert lines[1].startswith("  top   closures 4 · event loop 4"), lines[1]
    assert "⚠" in card and "api/app/services.py:4" in card  # risks surface on the project map too
    assert "/underneath gaps" in card
    data = json.loads((out / "map.json").read_text())
    assert data["test_files"] == 1
    assert data["concepts"]["react.useState"]["count"] == 2  # the test harness's useState is not counted
    assert data["concepts"]["react.useState"]["top_files"] == [["web/src/Profile.jsx", 1], ["web/src/Search.jsx", 1]]
    assert data["concepts"]["sql.leftJoinWhere"]["places"] == ["db/reports.sql:1"]
    page = (out / "map.html").read_text()
    assert page.count('class="nd') >= 12
    assert 'data-id="f:closures"' in page and 'data-id="react.useEffect"' in page
    assert 'class="nd co ctx" data-id="react.useState"' in page  # marked known: faded
    assert "/underneath deeper react.useEffect" in page


def test_map_cache():
    root = Path(tempfile.mkdtemp(prefix="underneath-proj-")) / "p"
    shutil.copytree(EX / "project-map", root)
    out = _project_out()
    _project("map", root, out)
    assert json.loads((out / "map.json").read_text())["parsed"] == 5
    _project("map", root, out)
    assert json.loads((out / "map.json").read_text())["parsed"] == 0  # nothing changed: all from the cache
    (root / "web" / "src" / "Counter.jsx").write_text(
        "import { useState } from 'react';\n\nexport function Counter() {\n"
        "  const [n, setN] = useState(0);\n  return <button onClick={() => setN(n + 1)}>{n}</button>;\n}\n"
    )
    _project("map", root, out)
    data = json.loads((out / "map.json").read_text())
    assert data["parsed"] == 1 and data["files"] == 6
    assert data["concepts"]["react.useState"]["count"] == 3


def test_map_always_shows_likely_bugs():
    """A likely bug in a rarely used fundamental still gets its row, first in it, with the amber dot."""
    from concepts import load_concepts, load_fundamentals
    from project import by_fundamental
    from render_map import MAP_FUNDAMENTALS, map_page

    cat = load_concepts(ROOT / "references")
    busy, seen = [], set()
    for cid, c in cat.items():  # one concept per fundamental, used a lot, no risk
        if not c.risk and c.fundamental not in seen and c.fundamental != "mutability":
            busy.append(cid)
            seen.add(c.fundamental)
    assert len(busy) > MAP_FUNDAMENTALS
    concepts = {cid: {"count": 50, "files": 5, "top_files": [["a.py", 50]], "places": []} for cid in busy}
    concepts["py.mutableDefault"] = {"count": 1, "files": 1, "top_files": [["app.py", 1]], "places": ["app.py:3"]}
    for cid in [c for c in cat if cat[c].fundamental == "closures"][:6]:  # a row with "+N more" too
        concepts[cid] = {"count": 60, "files": 6, "top_files": [["b.py", 60]], "places": []}
    data = {"root": "/p", "generated": "2026-11-16", "files": 10, "test_files": 0, "functions": 99, "truncated": False, "concepts": concepts}
    groups = by_fundamental(data, cat)
    assert groups[-1]["id"] == "mutability"  # the least used fundamental
    page = map_page(data, groups, cat, load_fundamentals(ROOT / "references"), {}, [])
    assert 'data-id="f:mutability"' in page
    node = page[page.index('data-id="py.mutableDefault"'):]
    assert '<g class="bdg">' in node[: node.index("</g></g>") + 8]
    assert page.count('class="nd fu"') == MAP_FUNDAMENTALS  # still 7 rows
    assert 'data-id="more:closures"' in page and 'data-id="more:fundamentals"' in page


def test_gaps():
    out = _project_out()
    card = _project("gaps", EX / "project-map", out)
    lines = card.strip().splitlines()
    assert len(lines) <= 5, card
    assert lines[0] == "underneath gaps · 12 of 13 concepts in your code never marked known, most used first"
    assert "useState" not in card  # marked known in the registry
    assert lines[1].startswith("  async / await (py)") and "3×" in lines[1]
    assert all("/underneath deeper " in l for l in lines[1:])
    counts_ = [int(l.split("×")[0].split()[-1]) for l in lines[1:]]
    assert counts_ == sorted(counts_, reverse=True)


# -------------------------------------------------------------- history ---


def test_history_and_log():
    """Each card goes to history.jsonl once; `log` sums up a period in 5 lines."""
    g, _, _, _, out = run("python-dashboard")
    subprocess.run([sys.executable, CLI, "render", "--out", out], capture_output=True, check=True)  # same change again
    lines = (out / "history.jsonl").read_text().splitlines()
    assert len(lines) == 1, lines
    first = json.loads(lines[0])
    assert first["risks"] == ["py.mutableDefault"] and first["hub"]

    from datetime import datetime, timedelta

    from concepts import load_concepts
    from history import log_card

    cat = load_concepts(ROOT / "references")
    now = datetime(2026, 11, 16, 12, 0)
    def item(days_ago, concepts, new=(), risks=()):
        return {"at": (now - timedelta(days=days_ago)).isoformat(), "concepts": list(concepts), "new_concepts": list(new), "risks": list(risks)}
    items = [
        item(30, ["react.useMemo"]),  # outside the week
        item(5, ["react.useEffect", "react.useState", "react.keys"], new=["react.useEffect"]),
        item(3, ["react.useEffect", "sql.leftJoinWhere", "react.keys", "react.callbackProps"], risks=["sql.leftJoinWhere"]),
        item(1, ["react.useEffect", "js.promiseAll", "react.keys"], new=["js.promiseAll"]),
    ]
    card = log_card(items, cat, {"concepts": {"react.useState": {"known": True}}}, 7, now)
    lines = card.splitlines()
    assert len(lines) <= 5, card
    assert lines[0] == "underneath log · 3 changes in the last 7 days · 6 concepts, 2 new", lines[0]
    assert lines[1].startswith("  most  useEffect ×3 ·"), lines[1]  # List keys (×3, minor) comes after
    assert "useMemo" not in card
    assert "LEFT JOIN" in lines[3] and "Nov 13" in lines[3]
    assert lines[4].endswith("/underneath deeper react.useEffect")
    assert log_card([], cat, {}, 7, now) == "underneath log · no card in the last 7 days"


# ------------------------------------------------------------ stop hook ---

HOOK = ROOT / "scripts" / "stop_hook.py"


def _transcript(tmp: Path, *entries) -> str:
    """A Claude Code transcript: ("prompt", text) or ("tool", name) entries, in order."""
    lines = []
    for kind, value in entries:
        if kind == "prompt":
            lines.append({"type": "user", "message": {"role": "user", "content": value}})
        else:
            lines.append({"type": "assistant", "message": {"role": "assistant", "content": [
                {"type": "tool_use", "id": "t1", "name": value, "input": {}}]}})
            lines.append({"type": "user", "message": {"role": "user", "content": [
                {"type": "tool_result", "tool_use_id": "t1", "content": "ok"}]}})
    path = tmp / "transcript.jsonl"
    path.write_text("\n".join(json.dumps(l) for l in lines))
    return str(path)


def _hook(repo: Path, transcript: str | None, active: bool = False) -> dict | None:
    payload = {"session_id": "s", "cwd": str(repo), "hook_event_name": "Stop", "stop_hook_active": active}
    if transcript:
        payload["transcript_path"] = transcript
    r = subprocess.run([sys.executable, HOOK], input=json.dumps(payload), capture_output=True, text=True, check=True)
    return json.loads(r.stdout) if r.stdout.strip() else None


def test_stop_hook_asks_for_the_card_once():
    repo = _git_repo("react-search")
    edited = _transcript(repo.parent, ("prompt", "add a user search"), ("tool", "Write"), ("tool", "Edit"))
    answer = _hook(repo, edited)
    assert answer and answer["hookSpecificOutput"]["hookEventName"] == "Stop"
    reason = answer["hookSpecificOutput"]["additionalContext"]  # feedback, not a "hook error"
    assert "decision" not in answer
    assert "NODES" in reason and "SearchUsers" in reason  # the brief rides along
    assert "do not run extract again" in reason
    assert '"stop_hook": false' in reason
    assert _hook(repo, edited) is None  # same graph: asked already, never nag
    # The agent writes notes and renders: the registry now holds this graph, still quiet.
    shutil.copy(EX / "react-search" / "notes.json", repo / ".underneath" / "notes.json")
    subprocess.run([sys.executable, CLI, "render"], cwd=repo, capture_output=True, check=True)
    assert _hook(repo, edited) is None
    # A new change in a later turn asks again.
    (repo / "src" / "lib" / "sort.ts").write_text((repo / "src" / "lib" / "sort.ts").read_text() + (
        "\nexport function sortByEmail(users) {\n  return [...users].sort((a, b) => a.email.localeCompare(b.email));\n}\n"
        "\nexport function sortByAge(users) {\n  return [...users].sort((a, b) => a.age - b.age);\n}\n"))
    assert "additionalContext" in _hook(repo, edited)["hookSpecificOutput"]


def test_stop_hook_stays_quiet():
    repo = _git_repo("react-search")
    edited = _transcript(repo.parent, ("prompt", "add a user search"), ("tool", "Edit"))
    assert _hook(repo, edited, active=True) is None  # already continuing because of a Stop hook: no loop
    talked = _transcript(repo.parent, ("prompt", "add it"), ("tool", "Edit"), ("prompt", "what does it do?"), ("tool", "Read"))
    assert _hook(repo, talked) is None  # this turn edited nothing
    (repo / ".underneath").mkdir(exist_ok=True)
    (repo / ".underneath" / "config.json").write_text(json.dumps({"stop_hook": False}))
    assert _hook(repo, edited) is None  # switched off
    small = _git_repo("react-search")
    shutil.rmtree(small / "src")
    shutil.copytree(EX / "react-search" / "before" / "src", small / "src")
    (small / "src" / "App.tsx").write_text((small / "src" / "App.tsx").read_text() + "\n// tweak\n")
    assert _hook(small, edited) is None  # small change
    outside = Path(tempfile.mkdtemp(prefix="underneath-nogit-"))
    assert _hook(outside, edited) is None  # not a git repository


def test_version_is_consistent():
    r = subprocess.run([sys.executable, CLI, "--version"], capture_output=True, text=True, check=True)
    version = r.stdout.split()[-1]
    assert json.loads((ROOT / ".claude-plugin" / "plugin.json").read_text())["version"] == version
    assert f"## [{version}]" in (ROOT / "CHANGELOG.md").read_text()


# ---------------------------------------------------------------- evals ---


def test_evals():
    """evals/cases are the fixtures of every detection rule: zero invented concept, zero false link."""
    r = subprocess.run([sys.executable, ROOT / "evals" / "run.py", "--json"], capture_output=True, text=True)
    report = json.loads(r.stdout)
    assert r.returncode == 0, report["fails"]
    by = {c["case"]: c for c in report["cases"]}
    # The traps that v0.1 fell into, one per fixed rule.
    assert by["py-docstring-trap"]["concepts_found"] == 0  # strings are not code
    assert by["py-generators"]["invented"] == []  # a decorated method is not a closure
    assert by["sql-null-trap"]["invented"] == []  # IS NOT NULL is not a constraint
    assert by["js-signal-trap"]["invented"] == []  # a variable named signal is not an AbortController
    assert by["py-dict-get-false-link"]["false_links"] == [] and by["js-push-false-link"]["false_links"] == []
    assert report["total"]["concept_precision"] == 1.0
    # Likely bugs: each rule fires on its pattern and stays quiet on the safe version next to it.
    assert report["total"]["false_alarms"] == 0
    for case in ("react-risks", "py-risks", "sql-risks"):
        assert by[case]["missed_alarms"] == [] and by[case]["alarms_found"] >= 3, case
    for case in ("react-risk-traps", "py-risk-traps", "sql-risk-traps"):
        assert by[case]["false_alarms"] == [] and by[case]["alarms_expected"] == 0, case


def test_stop_hook_follows_the_code_not_the_tool():
    """A file changed through Bash asks for the card; a Bash turn that only read does not; a slow extract gives up."""
    repo = _git_repo("react-search")
    bash = _transcript(repo.parent, ("prompt", "regenerate the client"), ("tool", "Bash"))
    answer = _hook(repo, bash)
    assert answer and "additionalContext" in answer["hookSpecificOutput"]  # sed, scripts, generators
    shutil.copy(EX / "react-search" / "notes.json", repo / ".underneath" / "notes.json")
    subprocess.run([sys.executable, CLI, "render"], cwd=repo, capture_output=True, check=True)
    look = _transcript(repo.parent, ("prompt", "what changed?"), ("tool", "Bash"))  # git status, ls...
    assert _hook(repo, look) is None
    (repo / ".underneath" / "config.json").write_text(json.dumps({"stop_hook_timeout": 0.001}))
    (repo / "src" / "lib" / "sort.ts").write_text((repo / "src" / "lib" / "sort.ts").read_text() + "\nexport const BY = 'name';\n")
    slow = _hook(repo, bash)
    assert slow and "took longer than" in slow["systemMessage"] and "hookSpecificOutput" not in slow
    assert _hook(repo, bash) is None  # said once a day, never blocking


if __name__ == "__main__":
    for name, fn in list(globals().items()):
        if name.startswith("test_"):
            fn()
            print(f"ok  {name}")
