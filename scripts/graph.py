"""Build the diff graph: changed symbols, their direct neighbours, the concepts they use."""

from __future__ import annotations

import difflib
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from concepts import Concept, detect
from diffscope import Scope
from parse import Symbol, parse_file

LIMITS = {"changed": 7, "context": 3, "concepts": 5, "min_lines": 8}

STATUS_SCORE = {"new": 3, "modified": 2}

_TEST = re.compile(r"(^|/)(tests?|__tests__|spec)/|(^|/)test_[^/]*\.py$|_test\.py$|\.(test|spec)\.[jt]sx?$")


def is_test(path: str) -> bool:
    return bool(_TEST.search(path))


def _added_lines(old: str, new: str) -> int:
    return sum(
        1
        for l in difflib.unified_diff(old.splitlines(), new.splitlines(), lineterm="", n=0)
        if l.startswith("+") and not l.startswith("+++") and l[1:].strip()
    )


# --------------------------------------------------------------- imports ---

_JS_IMPORT = re.compile(r"""(?:import|export)\s[^;]*?from\s+['"](\.{1,2}/[^'"]+)['"]|require\(\s*['"](\.{1,2}/[^'"]+)['"]\s*\)""")
_PY_IMPORT = re.compile(r"(?m)^\s*from\s+([\w.]+)\s+import\s")
_JS_EXTS = ("", ".ts", ".tsx", ".js", ".jsx", ".mjs", "/index.ts", "/index.tsx", "/index.js", "/index.jsx")


def _imports(file: str, text: str, files: set[str]) -> set[str]:
    out = set()
    here = PurePosixPath(file).parent
    if file.endswith(".py"):
        for mod in _PY_IMPORT.findall(text):
            dots = len(mod) - len(mod.lstrip("."))
            parts = mod.lstrip(".").split(".") if mod.strip(".") else []
            base = here
            for _ in range(max(dots - 1, 0)):
                base = base.parent
            for cand in (
                (base if dots else PurePosixPath(".")).joinpath(*parts).as_posix() + ".py",
                (base if dots else PurePosixPath(".")).joinpath(*parts, "__init__.py").as_posix(),
            ):
                cand = cand.lstrip("./") if not cand.startswith("..") else cand
                if cand in files:
                    out.add(cand)
                else:
                    # absolute imports from a src/ layout or a sub-package
                    hits = [f for f in files if f.endswith("/" + cand)]
                    if len(hits) == 1:
                        out.add(hits[0])
    else:
        for a, b in _JS_IMPORT.findall(text):
            spec = a or b
            target = (here / spec).as_posix()
            norm = []
            for part in target.split("/"):
                if part == "..":
                    if norm:
                        norm.pop()
                elif part not in (".", ""):
                    norm.append(part)
            target = "/".join(norm)
            for ext in _JS_EXTS:
                if target + ext in files:
                    out.add(target + ext)
                    break
    return out


# ----------------------------------------------------------------- graph ---


def build(scope: Scope, catalogue: dict[str, Concept], registry: dict, limits: dict | None = None) -> dict:
    lim = {**LIMITS, **(limits or {})}

    # 1. Parse the current universe and the previous version of changed files.
    syms: dict[str, Symbol] = {}
    by_file: dict[str, list[Symbol]] = defaultdict(list)
    for rel, text in scope.universe.items():
        for s in parse_file(rel, text):
            syms[s.key] = s
            by_file[rel].append(s)
    old_syms: dict[str, Symbol] = {}
    for rel, text in scope.old.items():
        for s in parse_file(rel, text):
            old_syms[s.key] = s

    # 2. Status of each symbol in a changed file.
    status: dict[str, str] = {}
    added: dict[str, int] = {}
    for rel in scope.new:
        for s in by_file.get(rel, []):
            o = old_syms.get(s.key)
            if o is None:
                status[s.key] = "new"
                added[s.key] = len([l for l in s.source.splitlines() if l.strip()])
            elif o.norm() != s.norm():
                status[s.key] = "modified"
                added[s.key] = _added_lines(o.source, s.source)
    removed = sorted(
        o.label for k, o in old_syms.items() if k not in syms and o.file in scope.changed
    )
    total_added = sum(_added_lines(scope.old.get(r, ""), t) for r, t in scope.new.items())

    # 3. Resolve calls, renders and SQL references to symbols.
    files = set(scope.universe)
    imports = {f: _imports(f, t, files) for f, t in scope.universe.items()}
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    for s in syms.values():
        by_name[s.name].append(s)
        if s.qualname.endswith((".__init__", ".constructor")):
            by_name[s.qualname.rsplit(".", 1)[0].split(".")[-1]].append(s)
        short = s.name.split(".")[-1]
        if s.lang == "sql" and short != s.name:
            by_name[short].append(s)

    def resolve(src: Symbol, name: str) -> Symbol | None:
        cands = [c for c in by_name.get(name, []) if c.key != src.key]
        if not cands:
            return None
        same = [c for c in cands if c.file == src.file]
        if "." in src.qualname:
            cls = src.qualname.rsplit(".", 1)[0] + "."
            same_cls = [c for c in same if c.qualname.startswith(cls)]
            if same_cls:
                return same_cls[0]
        if same:
            return same[0]
        imported = [c for c in cands if c.file in imports.get(src.file, set())]
        if len(imported) >= 1:
            return imported[0]
        if src.lang == "sql":
            sql = [c for c in cands if c.lang == "sql" and c.kind in ("table", "view")]
            return sql[0] if len(sql) == 1 else None
        same_family = [c for c in cands if (c.lang == "python") == (src.lang == "python") and c.lang != "sql"]
        return same_family[0] if len(same_family) == 1 else None

    edges: set[tuple[str, str, str]] = set()
    for s in syms.values():
        for name in set(s.calls):
            t = resolve(s, name)
            if t is not None:
                edges.add((s.key, t.key, "calls"))
        for name in set(s.renders):
            t = resolve(s, name)
            if t is not None:
                edges.add((s.key, t.key, "renders"))
        for name in set(s.decorators):
            t = resolve(s, name)
            if t is not None:
                edges.add((s.key, t.key, "decorated by"))
        for name in set(s.refs):
            t = resolve(s, name)
            if t is not None:
                label = {"index": "indexes", "table": "references"}.get(s.kind, "reads")
                edges.add((s.key, t.key, label))

    out_e: dict[str, set[str]] = defaultdict(set)
    in_e: dict[str, set[str]] = defaultdict(set)
    for a, b, _ in edges:
        out_e[a].add(b)
        in_e[b].add(a)

    # 4. Rank changed symbols and pick what is shown.
    changed = [k for k in status]

    def score(k: str) -> float:
        s = syms[k]
        neigh = (out_e[k] | in_e[k]) - {k}
        deg = len([n for n in neigh if n in status]) + 0.5 * len([n for n in neigh if n not in status])
        return (
            STATUS_SCORE[status[k]]
            + min(deg, 4)
            + (2 if s.entry else 0)
            + (1 if s.kind in ("component", "hook", "view", "table") else 0)
            + min(added.get(k, 0) / 10, 3)
            - (3 if is_test(s.file) else 0)
        )

    changed.sort(key=lambda k: (-score(k), syms[k].file, syms[k].start_line))
    shown = changed[: lim["changed"]]
    hidden = changed[lim["changed"] :]

    tested_by: dict[str, list[str]] = defaultdict(list)
    for k in changed:
        for n in in_e[k]:
            if is_test(syms[n].file) and not is_test(syms[k].file):
                tested_by[k].append(syms[n].label)

    ctx_scores: Counter = Counter()
    for k in shown:
        for n in in_e[k]:
            if is_test(syms[n].file):
                continue
            if n not in status:
                ctx_scores[n] += 2  # callers matter most: they are what the change can break
        for n in out_e[k]:
            if n not in status:
                ctx_scores[n] += 1
    context = [k for k, _ in ctx_scores.most_common(lim["context"])]

    visible = shown + context
    vis_set = set(visible)

    # 5. Concepts used by shown changed symbols.
    uses: dict[str, list[str]] = {}
    concept_users: dict[str, list[str]] = defaultdict(list)
    for k in shown:
        found = detect(syms[k], catalogue)
        uses[k] = found
        for cid in found:
            concept_users[cid].append(k)
    seen = registry.get("concepts", {})

    rank_of = {k: i for i, k in enumerate(shown)}

    def cscore(cid: str) -> float:
        best = min(rank_of[k] for k in concept_users[cid])
        new_to_you = seen.get(cid, {}).get("seen", 0) == 0 and not seen.get(cid, {}).get("known")
        familiar = seen.get(cid, {}).get("seen", 0) >= 10 or seen.get(cid, {}).get("known", False)
        return (3 if new_to_you else 0) - (2 if familiar else 0) + len(concept_users[cid]) + (0.5 if catalogue[cid].requires else 0) + 1 / (1 + best) + (10 if catalogue[cid].risk else 0)

    ranked_concepts = sorted(concept_users, key=lambda c: (-cscore(c), c))
    # Risks first, then one concept per shown symbol (in rank order), then the best of the rest.
    picked = [c for c in ranked_concepts if catalogue[c].risk][: lim["concepts"]]
    for k in shown:
        if len(picked) >= lim["concepts"]:
            break
        mine = [c for c in ranked_concepts if k in concept_users[c]]
        if mine and not any(c in picked for c in mine):
            picked.append(mine[0])
    for c in ranked_concepts:
        if len(picked) >= lim["concepts"]:
            break
        if c not in picked:
            picked.append(c)
    shown_concepts = [c for c in ranked_concepts if c in picked]
    more_concepts = [c for c in ranked_concepts if c not in picked]

    fund_count = Counter(catalogue[c].fundamental for c in shown_concepts if catalogue[c].fundamental)
    fundamental_candidates = [f for f, _ in fund_count.most_common()]

    # 6. Hub: the changed symbol most connected to the rest of the visible graph.
    def vis_degree(k: str) -> int:
        return len((out_e[k] | in_e[k]) & vis_set - {k})

    hub = None
    if shown:
        best = max(shown, key=lambda k: (vis_degree(k), score(k)))
        if vis_degree(best) >= 2:
            hub = best

    # 7. Short ids for the agent and the renderer.
    ids = {k: f"n{i + 1}" for i, k in enumerate(visible)}
    nodes = []
    for k in visible:
        s = syms[k]
        nodes.append(
            {
                "id": ids[k],
                "label": s.label,
                "kind": s.kind,
                "lang": s.lang,
                "file": s.file,
                "line": s.start_line,
                "end_line": s.end_line,
                "status": status.get(k, "context"),
                "signature": s.signature,
                "added_lines": added.get(k, 0),
                "entry": s.entry,
                "hub": k == hub,
                "concepts": [c for c in uses.get(k, []) if c in shown_concepts],
                "tested_by": sorted(set(tested_by.get(k, []))),
                "test": is_test(s.file),
                "source": s.source if k in status else "",
            }
        )
    vis_edges = [
        {"from": ids[a], "to": ids[b], "type": t, "provenance": "extracted"}
        for a, b, t in sorted(edges)
        if a in ids and b in ids and a != b
    ]
    for k in shown:
        for cid in uses.get(k, []):
            if cid in shown_concepts:
                vis_edges.append({"from": ids[k], "to": cid, "type": "uses", "provenance": "extracted"})

    concept_nodes = []
    for cid in shown_concepts:
        c = catalogue[cid]
        concept_nodes.append(
            {
                "id": cid,
                "label": c.label,
                "stack": c.stack,
                "what": c.what,
                "pitfalls": c.pitfalls,
                "fundamental": c.fundamental,
                "new_to_you": seen.get(cid, {}).get("seen", 0) == 0 and not seen.get(cid, {}).get("known"),
                "risk": c.risk,
                "seen": seen.get(cid, {}).get("seen", 0),
                "users": [ids[k] for k in concept_users[cid] if k in ids],
            }
        )

    return {
        "schema": 1,
        "root": str(scope.root),
        "base": scope.base_label,
        "summary": {
            "new": sum(1 for v in status.values() if v == "new"),
            "modified": sum(1 for v in status.values() if v == "modified"),
            "removed": removed,
            "files": scope.changed,
            "added_lines": total_added,
            "hidden_changed": [syms[k].label for k in hidden],
            "more_concepts": [catalogue[c].label for c in more_concepts],
            "truncated_universe": scope.truncated,
        },
        "skip": total_added < lim["min_lines"] and not any(v == "new" for v in status.values()),
        "nodes": nodes,
        "concepts": concept_nodes,
        "edges": vis_edges,
        "fundamental_candidates": fundamental_candidates,
    }
