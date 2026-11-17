"""Build the diff graph: changed symbols, their direct neighbours, the concepts they use."""

from __future__ import annotations

import difflib
import keyword
import re
from collections import Counter, defaultdict
from pathlib import PurePosixPath

from concepts import Concept, detect
from diffscope import Scope
from parse import Symbol, parse_file

LIMITS = {"changed": 7, "context": 3, "concepts": 5, "min_lines": 8}

STATUS_SCORE = {"new": 3, "modified": 2, "moved": 0}
# Methods of built-in collections, strings and promises. Called on an object other than
# self/this, they are almost always the built-in one, never linked to a project method by name.
COMMON_METHODS = set("""
get items keys values append extend insert pop remove clear copy update setdefault add discard sort reverse
index count join split strip lstrip rstrip replace lower upper startswith endswith format encode decode
read write close find push shift unshift map filter reduce forEach findIndex some every includes indexOf
slice splice concat entries has set delete then catch finally toString trim toLowerCase toUpperCase
startsWith endsWith json text assign send throw next
""".split())
UTILITY_FILES = 10  # a callee named in more files than this is a project-wide utility...
UTILITY_WEIGHT = 0.1  # ...and weighs this much as context
MOVE_SIMILARITY = 0.6  # below this, a same-named symbol elsewhere is a rewrite, not a move
EXTRACT_SHARE = 0.9  # share of a new symbol's lines found in one old symbol to call it extracted

_TEST = re.compile(
    r"(^|/)(tests?|__tests__|spec|testing)/|(^|/)(test_[^/]*|[^/]*_tests?|tests?|tests_[^/]*|conftest)\.py$|\.(test|spec)\.[jt]sx?$"
)


def is_test(path: str) -> bool:
    return bool(_TEST.search(path))


_EXPORT = re.compile(r"^\s*export\s+(?:default\s+)?")
_DOC = {
    "python": [re.compile(r'(?m)^[ \t]*[rRuU]?("""|\'\'\')[\s\S]*?\1[ \t]*$'), re.compile(r"(?m)^[ \t]*#.*$")],
    "sql": [re.compile(r"(?m)^[ \t]*--.*$"), re.compile(r"/\*[\s\S]*?\*/")],
}
_JS_DOC = [re.compile(r"(?m)^[ \t]*//.*$"), re.compile(r"(?m)^[ \t]*/\*[\s\S]*?\*/")]


def _code(s: Symbol) -> str:
    """The source without docstrings and whole-line comments: editing only those is not a code change."""
    text = s.source
    for rx in _DOC.get(s.lang, _JS_DOC):
        text = rx.sub("", text)
    return re.sub(r"\s+", " ", text).strip()


def _similarity(a: Symbol, b: Symbol) -> float:
    """Share of identical lines; 1.0 when only whitespace or an `export` keyword differs."""
    x, y = _EXPORT.sub("", a.norm()), _EXPORT.sub("", b.norm())
    if x == y:
        return 1.0
    la = [l.strip() for l in a.source.splitlines() if l.strip()]
    lb = [l.strip() for l in b.source.splitlines() if l.strip()]
    return min(difflib.SequenceMatcher(None, la, lb, autojunk=False).ratio(), 0.999)


_SIGNIFICANT = re.compile(r"\w{2}.*\w{2}|\w{4}")


def _line_bag(source: str) -> Counter:
    """Stripped lines that carry code (not `}`, `)}`, `</div>`), counted."""
    return Counter(l.strip() for l in source.splitlines() if _SIGNIFICANT.search(l))


def _containment(mine: Counter, theirs: Counter) -> float:
    total = sum(mine.values())
    return sum((mine & theirs).values()) / total if total else 0.0


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


def _suffix_index(files: set[str]) -> dict[str, list[str]]:
    """Every trailing path of every file (`b/c.py`, `c.py` for `a/b/c.py`) -> files ending with it."""
    idx: dict[str, list[str]] = defaultdict(list)
    for f in files:
        parts = f.split("/")
        for i in range(1, len(parts)):
            idx["/".join(parts[i:])].append(f)
    return idx


def _imports(file: str, text: str, files: set[str], suffixes: dict[str, list[str]] | None = None) -> set[str]:
    out = set()
    here = PurePosixPath(file).parent
    if file.endswith(".py"):
        if suffixes is None:
            suffixes = _suffix_index(files)
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
                    hits = suffixes.get(cand, [])
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


# ------------------------------------------------------------ neighbours ---

_METHOD_PREFIX = r"(?:(?:async|static|public|private|protected|override|readonly|get|set)\s+)*\*?\s*"
_IDENT = re.compile(r"[A-Za-z_$][\w$]*")
_NAME_IN = re.compile(r"[A-Za-z_$][\w$]*(?=\s*\(?\s*$)|[A-Za-z_$][\w$]*$")
RARE = 3  # a callee defined in more files than this cannot resolve by name alone
_RESERVED = set(keyword.kwlist) | {
    "default", "constructor", "function", "class", "const", "let", "var", "new", "this", "super",
    "export", "import", "return", "typeof", "delete", "void", "yield", "await", "async", "static",
}


def _alt(names) -> str:
    return "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))


def _family(path: str) -> str:
    return "sql" if path.endswith(".sql") else "py" if path.endswith(".py") else "js"


def _stem(path: str) -> str:
    p = PurePosixPath(path)
    return p.parent.name if p.stem in ("index", "__init__") else p.stem


def neighbour_files(scope: Scope, changed: list[Symbol], suffixes: dict[str, list[str]]) -> set[str]:
    """Files worth parsing besides the changed ones.

    Parsing every file of a large repository takes seconds. A few text scans
    find the only files that can add an edge to a changed symbol, given how
    `resolve` works (same file, imported file, or a name defined only once):
    - files a changed file imports, and files that import a changed file;
    - callers by name: files that mention a changed symbol whose name is
      defined nowhere else (if it is defined elsewhere too, only imports link it);
    - callees by name: files that define a name a changed symbol calls, when at
      most RARE files define it.
    Definition patterns match more than the parser keeps, so a name never
    looks unique when it is not.
    """
    files = set(scope.universe)
    changed_files = set(scope.new)
    callers: dict[str, set[str]] = defaultdict(set)  # name -> families
    callees: dict[str, set[str]] = defaultdict(set)
    for s in changed:
        fam = _family(s.file)
        callers[s.name.split(".")[-1]].add(fam)
        if "." in s.qualname:
            callers[s.qualname.split(".")[0]].add(fam)  # a constructor is called by its class name
        for n in (*s.calls, *s.renders, *s.decorators, *s.bases, *(t for _, t in s.typed_calls)):
            callees[n].add(fam)
    names = {n for n in set(callers) | set(callees) if _IDENT.fullmatch(n) and n not in _RESERVED}

    out: set[str] = set()
    for rel in changed_files:
        out |= _imports(rel, scope.new[rel], files, suffixes)

    # Importers of a changed file: an import line that names its module, confirmed by _imports.
    stems = {_stem(f) for f in changed_files} - {""}
    if stems:
        rx = rf"(?:\bimport\b|\bfrom\b|\brequire\s*\().*(?<![\w$])(?:{_alt(stems)})(?![\w$])"
        for rel in scope.scan(rx):
            if rel not in changed_files and changed_files & _imports(rel, scope.universe[rel], files, suffixes):
                out.add(rel)

    # SQL: names are case-insensitive and SQL repos are small; take every file that mentions one.
    sql = {s.name.split(".")[-1].lower() for s in changed if s.lang == "sql"}
    for s in changed:
        sql.update(r.split(".")[-1].lower() for r in s.refs)  # SQL files, and SQL inside strings
    if sql:
        out |= {f for f in scope.scan(rf"(?i)\b(?:{_alt(sql)})\b") if f.endswith(".sql")}

    if not names:
        return out - changed_files

    alt = _alt(names)
    defined: dict[tuple[str, str], set[str]] = defaultdict(set)  # (family, name) -> files

    def collect(pattern: str, fam: str, only: set[str] | None = None) -> None:
        for rel, matches in scope.scan(pattern).items():
            if _family(rel) != fam or (only is not None and rel not in only):
                continue
            for m in matches:
                hit = _NAME_IN.search(m)
                if hit and hit.group(0) in names:
                    defined[(fam, hit.group(0))].add(rel)

    collect(rf"^[ \t]*(?:async\s+)?(?:def|class)\s+(?:{alt})\b", "py")
    collect(
        rf"^(?:export\s+(?:default\s+)?)?(?:async\s+)?(?:function\*?\s*|(?:const|let|var)\s+|class\s+)(?:{alt})(?![\w$])",
        "js",
    )
    # JS class methods have no keyword: only count them in files that declare a class.
    class_files = set(scope.scan(r"\bclass\s+[A-Za-z_$]"))
    collect(rf"^[ \t]+{_METHOD_PREFIX}(?:{alt})\s*\(", "js", class_files)

    for n, fams in callees.items():
        for f in fams:
            hits = defined.get((f, n), set())
            if len(hits) <= RARE:
                out |= hits
    unique = {n for n, fams in callers.items() if n in names and all(len(defined[(f, n)] - changed_files) == 0 for f in fams)}
    if unique:
        out |= set(scope.scan(rf"(?<![\w$])(?:{_alt(unique)})(?![\w$])"))
    return out - changed_files


# ----------------------------------------------------------------- graph ---


def build(scope: Scope, catalogue: dict[str, Concept], registry: dict, limits: dict | None = None) -> dict:
    lim = {**LIMITS, **(limits or {})}

    # 1. Parse the changed files (both versions), then only the files that can
    #    connect to them. The rest of the universe is never parsed.
    syms: dict[str, Symbol] = {}
    by_file: dict[str, list[Symbol]] = defaultdict(list)

    def take(rel: str, text: str) -> None:
        for s in parse_file(rel, text):
            syms[s.key] = s
            by_file[rel].append(s)

    for rel, text in scope.new.items():
        take(rel, text)
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
            elif _code(o) != _code(s):
                status[s.key] = "modified"
                added[s.key] = _added_lines(o.source, s.source)
    gone = {k: o for k, o in old_syms.items() if k not in syms and o.file in scope.changed}
    total_added = sum(_added_lines(scope.old.get(r, ""), t) for r, t in scope.new.items())

    # A "new" symbol that already existed elsewhere in the diff was moved, not
    # written: a split file, a rename or a component pulled out of a big
    # function must not read as hundreds of new lines.
    # - same name, gone from its old place, mostly the same body: moved (or moved and edited);
    # - otherwise, nearly all its lines were already in one old symbol: extracted from it.
    moved_from: dict[str, str] = {}
    # Only code that left its old place can have moved: a copy of an unchanged function is new code.
    old_lines = {k: _line_bag(o.source) for k, o in old_syms.items()
                 if o.file in scope.changed and (k not in syms or status.get(k) == "modified")}
    for k in [k for k, v in status.items() if v == "new"]:
        s = syms[k]
        fam = s.lang == "python"
        same = [o for o in gone.values() if o.name == s.name and (o.lang == "python") == fam]
        best = max(((_similarity(o, s), o) for o in same), key=lambda p: (p[0], p[1].file), default=(0.0, None))
        lines = added[k]
        if best[0] >= MOVE_SIMILARITY:
            sim, o = best
            del gone[o.key]
            status[k], added[k] = ("moved", 0) if sim == 1.0 else ("modified", _added_lines(o.source, s.source))
        else:
            mine = _line_bag(s.source.split("\n", 1)[-1])  # the declaration line is new by definition
            if sum(mine.values()) < 3:
                continue
            cands = [(_containment(mine, old_lines[ok]), ok) for ok, o in old_syms.items()
                     if ok in old_lines and (o.lang == "python") == fam]
            share, ok = max(cands, key=lambda p: (p[0], p[1]), default=(0.0, ""))
            if share < EXTRACT_SHARE:
                continue
            o = old_syms[ok]
            status[k] = "moved"
            added[k] = sum((mine - old_lines[ok]).values())
        moved_from[k] = f"{o.file}:{o.start_line}"
        total_added -= lines - added[k]
    total_added = max(total_added, 0)
    removed = sorted(o.label for o in gone.values())

    # 3. Parse the neighbours, then resolve calls, renders and SQL references.
    files = set(scope.universe)
    suffixes = _suffix_index(files)
    seeds = [syms[k] for k in status if not is_test(syms[k].file)]  # nothing calls a test
    for rel in sorted(neighbour_files(scope, seeds, suffixes)):
        take(rel, scope.universe[rel])
    imports = {f: _imports(f, scope.universe.get(f) or scope.new.get(f, ""), files, suffixes) for f in by_file}
    by_name: dict[str, list[Symbol]] = defaultdict(list)
    for s in syms.values():
        by_name[s.name].append(s)  # a class is found by its name: `Cart()` links to the class
        short = s.name.split(".")[-1]
        if s.lang == "sql" and short != s.name:
            by_name[short].append(s)

    def resolve(src: Symbol, name: str, methods: bool = True) -> Symbol | None:
        # Sorted by place in the code, so the choice never depends on parse order.
        cands = sorted((c for c in by_name.get(name, []) if c.key != src.key), key=lambda c: (c.file, c.start_line, c.qualname))
        if not methods:  # `render(...)` called bare is a function or a class, never some class's method
            cands = [c for c in cands if c.kind != "method"]
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

    def pick(src: Symbol, cands: list[Symbol]) -> Symbol | None:
        cands = sorted(cands, key=lambda c: (c.file, c.start_line))
        same = [c for c in cands if c.file == src.file]
        imported = [c for c in cands if c.file in imports.get(src.file, set())]
        return (same or imported or (cands if len(cands) == 1 else [None]))[0]

    def method_of(src: Symbol, cls: str, meth: str, depth: int = 0) -> Symbol | None:
        """`cls.meth`, or the method a base class provides. `Model.objects` uses the type the class gives it."""
        if "." in cls:
            owner, attr = cls.split(".", 1)
            klass = pick(src, [c for c in by_name.get(owner, []) if c.kind == "class"])
            t = klass.attr_types.get(attr) if klass is not None else None
            return method_of(src, t, meth, depth + 1) if t and depth < 4 else None
        hit = pick(src, [c for c in by_name.get(meth, []) if c.qualname.split("#")[0] == f"{cls}.{meth}"])
        if hit is not None or depth >= 4:
            return hit
        klass = pick(src, [c for c in by_name.get(cls, []) if c.kind == "class"])
        for base in klass.bases if klass is not None else []:
            hit = method_of(klass, base, meth, depth + 1)
            if hit is not None:
                return hit
        return None

    edges: set[tuple[str, str, str]] = set()
    for s in syms.values():
        # `cache.get(k)` with `cache: ReportCache`: the type says which method it is.
        typed = set()
        for meth, cls in s.typed_calls:
            typed.add(meth)
            t = method_of(s, cls, meth)
            if t is not None and t.key != s.key:
                edges.add((s.key, t.key, "calls"))
        # `rows.get(k)` or `late.push(x)` on some object: the name alone cannot say it is ours.
        guess = set(s.member_only) & COMMON_METHODS
        # A typed receiver whose class is not ours (`session: requests.Session`) links nothing by name either.
        guess |= typed & set(s.member_only)
        # `self.decompressor.flush()`: an object of unknown type, so no guess by name either.
        guess |= set(s.blocked)
        bare = set(s.bare_only)
        for name in set(s.calls) - guess:
            t = resolve(s, name, methods=name not in bare)
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
        for name in set(s.bases):
            t = resolve(s, name)
            if t is not None and t.kind == "class":
                edges.add((s.key, t.key, "inherits"))
        if s.lang != "sql":  # SQL in a Python or JS string: link to the tables and views it names
            for name in set(s.refs):
                tables = [c for c in by_name.get(name, []) if c.lang == "sql" and c.kind in ("table", "view")]
                if len(tables) == 1:
                    edges.add((s.key, tables[0].key, "queries"))
            continue
        for name in set(s.refs):
            t = resolve(s, name)
            if t is not None:
                label = {"index": "indexes", "table": "references"}.get(s.kind, "reads")
                edges.add((s.key, t.key, label))

    # Likely bugs one call away, through extracted edges only: a loop calling a
    # helper that queries is N+1; forEach(save) with an async save does not wait.
    by_key_calls: dict[str, dict[str, str]] = defaultdict(dict)  # caller -> callee name -> callee key
    for a, b, typ in edges:
        if typ == "calls":
            by_key_calls[a][syms[b].name] = b
    for k in status:
        s = syms[k]
        for name in s.loop_calls:
            t = by_key_calls[k].get(name)
            if t and "db-query" in syms[t].flags and "query-in-loop" not in s.flags:
                s.flags = sorted({*s.flags, "query-in-loop"})
                s.via["query-in-loop"] = syms[t].label
        for name in s.foreach_refs:
            t = by_key_calls[k].get(name) or (lambda c: c.key if c else None)(resolve(s, name))
            if t and "async-fn" in syms[t].flags and "foreach-async" not in s.flags:
                s.flags = sorted({*s.flags, "foreach-async"})
                s.via["foreach-async"] = syms[t].label

    out_e: dict[str, set[str]] = defaultdict(set)
    in_e: dict[str, set[str]] = defaultdict(set)
    for a, b, _ in edges:
        out_e[a].add(b)
        in_e[b].add(a)

    # 4. Rank changed symbols and pick what is shown. Tests are not drawn: they
    #    become "tested by N tests" on what they call (unless only tests changed).
    changed_tests = [k for k in status if is_test(syms[k].file)]
    changed = [k for k in status if not is_test(syms[k].file)] or changed_tests

    def score(k: str) -> float:
        s = syms[k]
        neigh = {n for n in (out_e[k] | in_e[k]) - {k} if not is_test(syms[n].file)}  # tests are counted apart
        deg = len([n for n in neigh if n in status]) + 0.5 * len([n for n in neigh if n not in status])
        return (
            STATUS_SCORE[status[k]]
            + min(deg, 4)
            + (2 if s.entry else 0)
            + (1 if s.kind in ("component", "hook", "view", "table", "class") else 0)
            + min(added.get(k, 0) / 10, 3)
            - (3 if is_test(s.file) else 0)
        )

    changed.sort(key=lambda k: (-score(k), syms[k].file, syms[k].start_line))
    shown = changed[: lim["changed"]]
    hidden = changed[lim["changed"] :]

    tested_by: dict[str, list[str]] = defaultdict(list)
    for k in status:
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
            if n not in status and not is_test(syms[n].file):
                ctx_scores[n] += 1
    # A callee used all over the project (`cn`, `Button`) says little about this change:
    # it keeps a place only if nothing more specific wants it.
    callees = {n for n in ctx_scores if not any(n in in_e[k] for k in shown) and _IDENT.fullmatch(syms[n].name)}
    if callees:
        spread: Counter = Counter()
        for matches in scope.scan(rf"(?<![\w$])(?:{_alt({syms[n].name for n in callees})})(?![\w$])").values():
            spread.update(set(matches))
        for n in callees:
            if spread[syms[n].name] > UTILITY_FILES:
                ctx_scores[n] *= UTILITY_WEIGHT
    # Ties are broken by place in the code, never by set order: the same diff gives the same map.
    ranked_ctx = sorted(ctx_scores, key=lambda k: (-ctx_scores[k], syms[k].file, syms[k].start_line))
    context = ranked_ctx[: lim["context"]]

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
        return (3 if new_to_you else 0) - (2 if familiar else 0) + len(concept_users[cid]) + (0.5 if catalogue[cid].requires else 0) + 1 / (1 + best) + (10 if catalogue[cid].risk else 0) - (6 if catalogue[cid].minor else 0)

    ranked_concepts = sorted(concept_users, key=lambda c: (-cscore(c), c))
    # Risks first, then one concept per shown symbol (in rank order), then the best of the rest.
    picked = [c for c in ranked_concepts if catalogue[c].risk][: lim["concepts"]]
    for k in shown:
        if len(picked) >= lim["concepts"]:
            break
        mine = [c for c in ranked_concepts if k in concept_users[c] and not catalogue[c].minor]
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
                "moved_from": moved_from.get(k, ""),
                "signature": s.signature,
                "added_lines": added.get(k, 0),
                "entry": s.entry,
                "hub": k == hub,
                "concepts": [c for c in uses.get(k, []) if c in shown_concepts],
                "via": {cid: s.via[t] for cid in uses.get(k, []) for t in catalogue[cid].trees if t in s.via},
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
            "new": sum(1 for k in changed if status[k] == "new"),
            "modified": sum(1 for k in changed if status[k] == "modified"),
            "moved": sum(1 for k in changed if status[k] == "moved"),
            "tests": len(changed_tests) if changed is not changed_tests else 0,
            "removed": removed,
            "files": scope.changed,
            "added_lines": total_added,
            "hidden_changed": [syms[k].label for k in hidden],
            "more_concepts": [catalogue[c].label for c in more_concepts],
            "more_concept_ids": more_concepts,
            "truncated_universe": scope.truncated,
        },
        "skip": total_added < lim["min_lines"] and not any(status[k] == "new" for k in changed),
        "nodes": nodes,
        "concepts": concept_nodes,
        "edges": vis_edges,
        "fundamental_candidates": fundamental_candidates,
    }
