#!/usr/bin/env python3
"""underneath: see what the AI just wrote, and what it rests on.

  underneath.py extract [--base REF] [--before DIR --after DIR] [--out DIR]
  underneath.py render  [--out DIR]
  underneath.py map     [--root DIR] [--out DIR]
  underneath.py gaps    [--root DIR] [--out DIR]
  underneath.py log     [--days N] [--root DIR] [--out DIR]
  underneath.py deeper  ID
  underneath.py known   CONCEPT_ID
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from pathlib import Path

__version__ = "0.2.1"

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))


def _use_skill_venv() -> None:
    """Re-run under <skill>/.venv when the system Python lacks tree-sitter.

    macOS and recent Linux distributions refuse `pip install` into the system
    Python, so the dependencies usually live in a virtualenv next to the skill.
    """
    try:
        import tree_sitter_language_pack  # noqa: F401
        return
    except ImportError:
        pass
    # Next to the skill (a git clone), or in the user's home (a plugin, whose folder changes on update).
    for venv in (HERE.parent / ".venv", Path.home() / ".underneath" / "venv"):
        venv_py = venv / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if venv_py.exists() and Path(sys.prefix).resolve() != venv.resolve():
            os.execv(str(venv_py), [str(venv_py), str(Path(__file__).resolve()), *sys.argv[1:]])
    # Otherwise parse.py explains how to install.


_use_skill_venv()

from concepts import load_concepts, load_fundamentals  # noqa: E402
from diffscope import from_dirs, from_git, project_scope  # noqa: E402
from graph import LIMITS, build  # noqa: E402
from history import append as history_append, entry as history_entry, load as history_load, log_card  # noqa: E402
from project import by_fundamental, gaps, scan  # noqa: E402
from render import card, clean_notes, counts, page, update_registry  # noqa: E402
from render_map import gaps_card, map_card, map_page  # noqa: E402

REF = HERE.parent / "references"
MAX_SNIPPET = 40
MAX_BRIEF_LINES = 320
FENCE = {"tsx": "tsx", "typescript": "ts", "javascript": "js", "python": "python", "sql": "sql"}


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, json.JSONDecodeError):
        return default


def _out_dir(arg: str | None, root: Path) -> Path:
    out = Path(arg) if arg else root / ".underneath"
    out.mkdir(parents=True, exist_ok=True)
    gi = out / ".gitignore"
    if not gi.exists():
        gi.write_text("# underneath output and personal registry\n*\n", encoding="utf8")
    return out


def cmd_extract(a) -> int:
    if a.before or a.after:
        if not (a.before and a.after):
            print("--before and --after go together", file=sys.stderr)
            return 2
        scope = from_dirs(Path(a.before), Path(a.after))
        out = _out_dir(a.out, Path.cwd())
    else:
        try:
            scope = from_git(Path.cwd(), a.base)
        except RuntimeError as e:
            print(f"underneath: {e}\nRun inside a git repository, or use --before/--after.", file=sys.stderr)
            return 2
        out = _out_dir(a.out, scope.root)

    config = _load(out / "config.json", {})
    registry = _load(out / "registry.json", {})
    catalogue = load_concepts(REF)
    g = build(scope, catalogue, registry, config.get("limits"))
    (out / "graph.json").write_text(json.dumps(g, indent=1), encoding="utf8")
    (out / "notes.json").unlink(missing_ok=True)

    s = g["summary"]
    if not g["nodes"]:
        print(f"underneath: no supported changes since {scope.base_label}. Nothing to map.")
        return 0
    if g["skip"]:
        print(f"underneath: small change (+{s['added_lines']} lines, nothing new). Skip the card.")
        return 0

    lines = [
        f"underneath extract · {', '.join(counts(s))} · compared with {scope.base_label}",
        f"graph: {out / 'graph.json'}",
        "",
        "NODES (ids are fixed; write a summary only for changed ones)",
    ]
    by_id = {n["id"]: n for n in g["nodes"]}
    rel_out, rel_in = {}, {}
    for e in g["edges"]:
        if e["type"] != "uses":
            rel_out.setdefault((e["from"], e["type"]), []).append(e["to"])
            rel_in.setdefault((e["to"], e["type"]), []).append(e["from"])
    passive = {"calls": "called by", "renders": "rendered by", "reads": "read by", "references": "referenced by", "indexes": "indexed by", "decorated by": "decorates", "inherits": "inherited by", "queries": "queried by"}
    for n in g["nodes"]:
        tag = f"{n['kind'].replace('_', ' ')} · {n['status']}" + (f" from {n['moved_from']}" if n.get("moved_from") else "") + (" · hub" if n["hub"] else "")
        lines.append(f"{n['id']:<4}{n['label']}  [{tag}]  {n['file']}:{n['line']}-{n['end_line']}")
        if n["concepts"]:
            lines.append(f"    concepts: {', '.join(n['concepts'])}")
        rels = []
        for (nid, typ), targets in sorted(rel_out.items()):
            if nid == n["id"]:
                rels.append(f"{typ} " + ", ".join(f"{i} {by_id[i]['label']}" for i in targets))
        for (nid, typ), sources in sorted(rel_in.items()):
            if nid == n["id"]:
                rels.append(f"{passive.get(typ, typ + ' by')} " + ", ".join(f"{i} {by_id[i]['label']}" for i in sources))
        if n.get("tested_by"):
            rels.append(f"tested by {len(n['tested_by'])} test(s)")
        elif n["status"] != "context" and not n.get("test"):
            rels.append("no direct test call found")
        if rels:
            lines.append("    " + " · ".join(rels))
        if n["source"] and len(lines) < MAX_BRIEF_LINES:
            src = n["source"].rstrip().splitlines()
            start = n["line"]
            shown = src[:MAX_SNIPPET]
            lines.append(f"    ```{FENCE.get(n['lang'], '')}")
            lines += [f"    {start + i:>4} {l}" for i, l in enumerate(shown)]
            if len(src) > MAX_SNIPPET:
                lines.append(f"    … {len(src) - MAX_SNIPPET} more lines in the file")
            lines.append("    ```")
    lines += ["", "CONCEPTS (write `here` for each; `watch` only for a pitfall present or avoided in this code)"]
    for c in g["concepts"]:
        flag = "new to you" if c["new_to_you"] else f"seen {c['seen']}x"
        if c.get("risk"):
            flag = "LIKELY BUG, check and add a watch item · " + flag
        lines.append(f"{c['id']}  {c['label']} · {flag} · in {', '.join(c['users'])} · fundamental: {c['fundamental']}")
        lines.append(f"    pitfalls: {' '.join(c['pitfalls'])}")
    if s["more_concepts"]:
        lines.append(f"(also present, not drawn: {', '.join(s['more_concepts'])})")
    lines += [
        "",
        f"FUNDAMENTAL candidates: {', '.join(g['fundamental_candidates']) or 'none'}",
        "",
        f"NEXT: write {out / 'notes.json'} (format: references/card-format.md), then run:",
        f"  python3 {HERE / 'underneath.py'} render" + (f" --out {out}" if a.out or a.before else ""),
    ]
    print("\n".join(lines))
    return 0


def cmd_render(a) -> int:
    out = Path(a.out) if a.out else None
    if out is None:
        try:
            from diffscope import _git  # local import keeps extract/render independent

            out = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip()) / ".underneath"
        except RuntimeError:
            out = Path.cwd() / ".underneath"
    graph = _load(out / "graph.json", None)
    if graph is None:
        print(f"underneath: no {out / 'graph.json'}. Run extract first.", file=sys.stderr)
        return 2
    fundamentals = load_fundamentals(REF)
    raw = _load(out / "notes.json", {})
    notes, warnings = clean_notes(raw, graph, fundamentals)
    html_path = out / "latest.html"
    html_path.write_text(page(graph, notes, fundamentals), encoding="utf8")
    try:
        shown_path = html_path.relative_to(Path.cwd())
    except ValueError:
        shown_path = html_path
    text = card(graph, notes, str(shown_path))
    (out / "card.md").write_text(text + "\n", encoding="utf8")
    gid = hashlib.sha1((out / "graph.json").read_bytes()).hexdigest()[:12]
    reg = update_registry(_load(out / "registry.json", {}), graph, gid)
    (out / "registry.json").write_text(json.dumps(reg, indent=1), encoding="utf8")
    history_append(out / "history.jsonl", history_entry(graph, notes, text))
    if not raw:
        warnings.insert(0, "no notes.json: card drawn from the syntax tree only")
    for w in warnings:
        print(f"note: {w}", file=sys.stderr)
    print(text)
    return 0


def _project(a):
    """Scan the project (cached), with the output folder and registry it uses."""
    scope = project_scope(Path(a.root) if a.root else None)
    out = _out_dir(a.out, scope.root)
    catalogue = load_concepts(REF)
    data = scan(scope, catalogue, REF, out / "cache")
    registry = _load(out / "registry.json", {})
    return data, catalogue, registry, out


def _shown(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def cmd_map(a) -> int:
    data, catalogue, registry, out = _project(a)
    fundamentals = load_fundamentals(REF)
    groups = by_fundamental(data, catalogue)
    gap_ids = gaps(data, registry, catalogue)
    (out / "map.json").write_text(json.dumps(data, indent=1), encoding="utf8")
    html_path = out / "map.html"
    html_path.write_text(map_page(data, groups, catalogue, fundamentals, registry, gap_ids), encoding="utf8")
    print(map_card(data, groups, catalogue, fundamentals, gap_ids, _shown(html_path)))
    return 0


def cmd_gaps(a) -> int:
    data, catalogue, registry, _ = _project(a)
    print(gaps_card(data, gaps(data, registry, catalogue), catalogue))
    return 0


def cmd_log(a) -> int:
    out = Path(a.out) if a.out else _repo_out(Path(a.root) if a.root else Path.cwd())
    catalogue = load_concepts(REF)
    print(log_card(history_load(out / "history.jsonl"), catalogue, _load(out / "registry.json", {}), a.days))
    return 0


def _repo_out(here: Path) -> Path:
    try:
        from diffscope import _git

        return Path(_git(here, "rev-parse", "--show-toplevel").strip()) / ".underneath"
    except (RuntimeError, OSError):
        return here / ".underneath"


def cmd_deeper(a) -> int:
    fundamentals = load_fundamentals(REF)
    catalogue = load_concepts(REF)
    key = a.id.removeprefix("f:")
    if key in fundamentals:
        f = fundamentals[key]
        print(f"{f.label}\n{f.one_liner}\n\n```{f.example_lang}\n{f.example}\n```")
        users = [c.label for c in catalogue.values() if c.fundamental == key]
        if users:
            print(f"\nConcepts that rest on it: {', '.join(users)}")
        return 0
    if key in catalogue:
        c = catalogue[key]
        print(f"{c.label} ({c.stack})\n{c.what}\n\nPitfalls:")
        for p in c.pitfalls:
            print(f"  - {p}")
        if c.fundamental in fundamentals:
            f = fundamentals[c.fundamental]
            print(f"\nUnderneath: {f.label}. {f.one_liner}\n\n```{f.example_lang}\n{f.example}\n```")
        return 0
    print(f"underneath: unknown id '{a.id}'. Fundamentals: {', '.join(sorted(fundamentals))}", file=sys.stderr)
    return 2


def cmd_known(a) -> int:
    catalogue = load_concepts(REF)
    if a.id not in catalogue:
        print(f"underneath: unknown concept '{a.id}'", file=sys.stderr)
        return 2
    try:
        from diffscope import _git

        out = Path(_git(Path.cwd(), "rev-parse", "--show-toplevel").strip()) / ".underneath"
    except RuntimeError:
        out = Path.cwd() / ".underneath"
    out = _out_dir(a.out, out.parent) if a.out else _out_dir(None, out.parent)
    reg = _load(out / "registry.json", {})
    reg.setdefault("concepts", {}).setdefault(a.id, {"seen": 0})["known"] = True
    (out / "registry.json").write_text(json.dumps(reg, indent=1), encoding="utf8")
    print(f"underneath: {catalogue[a.id].label} marked as known. It will be drawn compact from now on.")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="underneath", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--version", action="version", version=f"underneath {__version__}")
    sub = p.add_subparsers(dest="cmd", required=True)
    e = sub.add_parser("extract", help="read the diff and build graph.json")
    e.add_argument("--base", default="HEAD", help="git ref to compare with (default HEAD: uncommitted work)")
    e.add_argument("--before", help="folder with the old version (instead of git)")
    e.add_argument("--after", help="folder with the new version (instead of git)")
    e.add_argument("--out", help="output folder (default <repo>/.underneath)")
    r = sub.add_parser("render", help="build card.md and latest.html from graph.json + notes.json")
    r.add_argument("--out")
    for name, text in (("map", "the whole project's concepts, grouped by fundamental: card + map.html"),
                       ("gaps", "concepts in the code you never marked known, most used first")):
        m = sub.add_parser(name, help=text)
        m.add_argument("--root", help="project folder (default: the current git repository, or the current folder)")
        m.add_argument("--out", help="output folder (default <project>/.underneath)")
    lg = sub.add_parser("log", help="what the last cards showed: concepts that came back, new ones, likely bugs")
    lg.add_argument("--days", type=int, default=7, help="period, in days (default 7)")
    lg.add_argument("--root", help="project folder (default: the current git repository)")
    lg.add_argument("--out", help="output folder (default <project>/.underneath)")
    d = sub.add_parser("deeper", help="explain a fundamental or a concept with a minimal example")
    d.add_argument("id")
    k = sub.add_parser("known", help="mark a concept as known so it is drawn compact")
    k.add_argument("id")
    k.add_argument("--out")
    a = p.parse_args(argv)
    cmds = {"extract": cmd_extract, "render": cmd_render, "map": cmd_map, "gaps": cmd_gaps, "log": cmd_log, "deeper": cmd_deeper, "known": cmd_known}
    return cmds[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
