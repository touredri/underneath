"""Deterministic symbol extraction with tree-sitter.

Only top-level symbols become nodes (module functions, class methods, SQL
statements). Nested functions are folded into their parent: their calls count
as the parent's calls. This keeps the graph at the level a reader thinks in.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from pathlib import PurePosixPath

try:
    from tree_sitter_language_pack import get_parser
except ImportError as exc:  # pragma: no cover
    raise SystemExit(
        "underneath needs tree-sitter. Install it once in a virtualenv the script finds by itself:\n"
        "  python3 -m venv ~/.underneath/venv && ~/.underneath/venv/bin/pip install tree-sitter tree-sitter-language-pack"
    ) from exc

LANG_BY_EXT = {
    ".tsx": "tsx",
    ".jsx": "tsx",
    ".ts": "typescript",
    ".mts": "typescript",
    ".cts": "typescript",
    ".js": "javascript",
    ".mjs": "javascript",
    ".cjs": "javascript",
    ".py": "python",
    ".sql": "sql",
}

# Which stack files apply to which grammar.
STACK_LANG = {"tsx": "js", "typescript": "js", "javascript": "js", "python": "python", "sql": "sql"}

_parsers: dict = {}


def language_for(path: str) -> str | None:
    return LANG_BY_EXT.get(PurePosixPath(path).suffix.lower())


def _parser(lang: str):
    if lang not in _parsers:
        _parsers[lang] = get_parser(lang)
    return _parsers[lang]


@dataclass
class Symbol:
    file: str
    qualname: str
    name: str
    kind: str
    lang: str
    start_line: int
    end_line: int
    source: str
    signature: str
    calls: list[str] = field(default_factory=list)
    renders: list[str] = field(default_factory=list)
    refs: list[str] = field(default_factory=list)
    decorators: list[str] = field(default_factory=list)
    member_only: list[str] = field(default_factory=list)
    bases: list[str] = field(default_factory=list)  # classes only: what it extends
    typed_calls: list[list[str]] = field(default_factory=list)  # [method, Type] when the receiver's type is known  # names only ever called as `other.name()`, never bare or on self/this
    exported: bool = False
    entry: bool = False
    label: str = ""

    @property
    def key(self) -> str:
        return f"{self.file}::{self.qualname}"

    def norm(self) -> str:
        return re.sub(r"\s+", " ", self.source).strip()


def _text(node, src: bytes) -> str:
    return src[node.start_byte : node.end_byte].decode("utf8", "replace")


def _walk(node):
    stack = [node]
    while stack:
        n = stack.pop()
        yield n
        stack.extend(reversed(n.children))


def _signature(source: str) -> str:
    """The declaration line(s), whitespace collapsed, decorators skipped."""
    lines = [l for l in source.strip().splitlines() if not l.strip().startswith("@")]
    head = []
    for line in lines[:12]:
        head.append(line.strip())
        joined = " ".join(head)
        if re.search(r"(\)\s*(->[^:]+)?:\s*$|\{\s*$|=>\s*\{?\s*$|\bAS\b|;\s*$)", joined, re.IGNORECASE):
            break
    sig = re.sub(r"\s+", " ", " ".join(head)).strip().rstrip("{").rstrip(":").strip()
    sig = re.sub(r"\(\s+", "(", re.sub(r",\s*\)", ")", sig))
    return sig if len(sig) <= 120 else sig[:119].rstrip() + "…"


# ------------------------------------------------------------ receivers ---
# The type of `obj` in `obj.method()`, when the code states it plainly: an
# annotation, a constructor call, a `self`/`this` attribute set from one of
# those, or a module-level instance. No inference beyond that.

_CONTAINERS = {
    "list", "dict", "set", "tuple", "frozenset", "List", "Dict", "Set", "Tuple", "FrozenSet", "Sequence", "Iterable",
    "Iterator", "Mapping", "MutableMapping", "Callable", "Type", "Any", "Array", "ReadonlyArray", "Record", "Map",
    "WeakMap", "Promise", "Partial", "Readonly", "Awaitable", "Generator", "AsyncIterator", "Union",
}


def _type_name(text: str | None) -> str | None:
    """`Optional[ReportCache]`, `ReportCache | None`, `: Repo` -> the class name; containers -> None."""
    if not text:
        return None
    t = re.sub(r"\s+", "", text).lstrip(":")
    t = re.sub(r"^Optional\[(.*)\]$", r"\1", t)
    parts = [p for p in t.split("|") if p not in ("None", "null", "undefined")]
    if len(parts) != 1:
        return None
    t = parts[0]
    base = re.split(r"[\[<]", t, maxsplit=1)[0].split(".")[-1]
    if base in _CONTAINERS or not re.fullmatch(r"[A-Z]\w*", base):
        return None
    return base


def _ctor(node, src) -> str | None:
    """`Cls(...)`, `mod.Cls(...)` or `new Cls(...)` -> Cls."""
    if node is None:
        return None
    if node.type == "new_expression":
        c = node.child_by_field_name("constructor")
        return _type_name(_text(c, src)) if c is not None else None
    if node.type in ("call", "await"):
        if node.type == "await":
            return None
        fn = node.child_by_field_name("function")
        return _type_name(_text(fn, src)) if fn is not None and fn.type in ("identifier", "attribute") else None
    return None


def _py_env(defn, src, outer_env: dict) -> tuple[dict, dict]:
    """(names -> type, self attributes -> type) for one Python function."""
    env, attrs = dict(outer_env), {}
    params = defn.child_by_field_name("parameters")
    for p in params.named_children if params is not None else []:
        if p.type in ("typed_parameter", "typed_default_parameter"):
            name = p.child_by_field_name("name") or next((c for c in p.named_children if c.type == "identifier"), None)
            t = _type_name(_text(p.child_by_field_name("type"), src)) if p.child_by_field_name("type") else None
            if name is not None and t:
                env[_text(name, src)] = t
    for n in _walk(defn):
        if n.type != "assignment":
            continue
        left, right, ann = n.child_by_field_name("left"), n.child_by_field_name("right"), n.child_by_field_name("type")
        t = _type_name(_text(ann, src)) if ann is not None else _ctor(right, src)
        if t is None and right is not None and right.type == "identifier":
            t = env.get(_text(right, src))
        if not t or left is None:
            continue
        if left.type == "identifier":
            env[_text(left, src)] = t
        elif left.type == "attribute" and _text(left.child_by_field_name("object"), src) == "self":
            attrs[_text(left.child_by_field_name("attribute"), src)] = t
    return env, attrs


def _js_env(fn, src, outer_env: dict) -> tuple[dict, dict]:
    """(names -> type, this attributes -> type) for one JS/TS function or method."""
    env, attrs = dict(outer_env), {}
    params = fn.child_by_field_name("parameters")
    for p in params.named_children if params is not None else []:
        if p.type in ("required_parameter", "optional_parameter"):
            name = p.child_by_field_name("pattern")
            ann = p.child_by_field_name("type")
            t = _type_name(_text(ann, src)) if ann is not None else None
            if name is not None and name.type == "identifier" and t:
                env[_text(name, src)] = t
                if any(c.type == "accessibility_modifier" for c in p.children):
                    attrs[_text(name, src)] = t  # constructor(private api: Api)
    for n in _walk(fn):
        if n.type == "variable_declarator":
            name, ann, value = n.child_by_field_name("name"), n.child_by_field_name("type"), n.child_by_field_name("value")
            t = _type_name(_text(ann, src)) if ann is not None else _ctor(value, src)
            if name is not None and name.type == "identifier" and t:
                env[_text(name, src)] = t
        elif n.type == "assignment_expression":
            left, right = n.child_by_field_name("left"), n.child_by_field_name("right")
            t = _ctor(right, src) or (env.get(_text(right, src)) if right is not None and right.type == "identifier" else None)
            if t and left is not None and left.type == "member_expression" and _text(left.child_by_field_name("object"), src) == "this":
                attrs[_text(left.child_by_field_name("property"), src)] = t
    return env, attrs


def _typed_calls(node, src, env: dict, attrs: dict, lang: str) -> list[list[str]]:
    """[method, Type] for each `recv.method()` whose receiver type is known."""
    out = []
    own = "self" if lang == "python" else "this"
    for n in _walk(node):
        if n.type not in ("call", "call_expression"):
            continue
        fn = n.child_by_field_name("function")
        if fn is None or fn.type not in ("attribute", "member_expression"):
            continue
        obj = fn.child_by_field_name("object")
        meth = fn.child_by_field_name("attribute" if fn.type == "attribute" else "property")
        if obj is None or meth is None:
            continue
        t = None
        if obj.type == "identifier":
            t = env.get(_text(obj, src))
        elif obj.type in ("attribute", "member_expression"):
            inner = obj.child_by_field_name("object")
            attr = obj.child_by_field_name("attribute" if obj.type == "attribute" else "property")
            if inner is not None and attr is not None and _text(inner, src) == own:
                t = attrs.get(_text(attr, src))
        if t:
            pair = [_text(meth, src), t]
            if pair not in out:
                out.append(pair)
    return out


# ---------------------------------------------------------------- JS / TS ---

_JS_FUNC_VALUES = {"arrow_function", "function_expression", "function", "generator_function"}


_OWN = {"this", "self", "cls", "super"}


def _member_only(calls: list[str], direct: set[str]) -> list[str]:
    return sorted(set(calls) - direct)


def _js_calls(node, src):
    calls, renders, direct = [], [], set()
    for n in _walk(node):
        if n.type == "call_expression":
            fn = n.child_by_field_name("function")
            if fn is None:
                continue
            if fn.type == "identifier":
                calls.append(_text(fn, src))
                direct.add(calls[-1])
            elif fn.type == "member_expression":
                prop = fn.child_by_field_name("property")
                obj = fn.child_by_field_name("object")
                if prop is not None:
                    calls.append(_text(prop, src))
                    if obj is not None and obj.type in ("this", "super"):
                        direct.add(calls[-1])
        elif n.type == "new_expression":
            ctor = n.child_by_field_name("constructor")
            if ctor is not None and ctor.type == "identifier":
                calls.append(_text(ctor, src))
        elif n.type in ("jsx_opening_element", "jsx_self_closing_element"):
            nm = n.child_by_field_name("name")
            if nm is None:
                continue
            t = _text(nm, src).split(".")[-1]
            if t[:1].isupper():
                renders.append(t)
    return calls, renders, direct


def _has_jsx(node) -> bool:
    return any(n.type in ("jsx_element", "jsx_self_closing_element", "jsx_fragment") for n in _walk(node))


def _wrapped_function(value):
    """`memo(() => ...)`, `forwardRef(function X() {...})` and the like."""
    if value is None:
        return None
    if value.type in _JS_FUNC_VALUES:
        return value
    if value.type == "call_expression":
        args = value.child_by_field_name("arguments")
        if args is not None:
            for a in args.named_children:
                if a.type in _JS_FUNC_VALUES:
                    return value
    return None


def _js_kind(name: str, node) -> str:
    if re.match(r"^use[A-Z0-9]", name):
        return "hook"
    if name[:1].isupper() and _has_jsx(node):
        return "component"
    return "function"


def _js_fn(node):
    """The function node that holds the parameters (for `const f = memo((p) => ...)` too)."""
    if node.child_by_field_name("parameters") is not None:
        return node
    for n in _walk(node):
        if n.type in _JS_FUNC_VALUES and n.child_by_field_name("parameters") is not None:
            return n
    return node


def _parse_js(path, src, lang):
    tree = _parser(lang).parse(src)
    out: list[Symbol] = []
    module_env: dict[str, str] = {}
    for stmt in tree.root_node.named_children:
        decl = stmt.child_by_field_name("declaration") if stmt.type == "export_statement" else stmt
        if decl is not None and decl.type in ("lexical_declaration", "variable_declaration"):
            env, _ = _js_env(decl, src, {})
            module_env.update(env)
    class_attrs: dict[str, dict] = {}

    def add(name, qual, node, src_node, exported, kind=None):
        source = _text(src_node, src)
        calls, renders, direct = _js_calls(node, src)
        env, attrs = _js_env(_js_fn(node), src, module_env)
        if kind == "method":
            attrs = {**class_attrs.get(qual.split(".")[0], {}), **attrs}
        k = kind or _js_kind(name, node)
        out.append(
            Symbol(
                file=path,
                qualname=qual,
                name=name,
                kind=k,
                lang=lang,
                start_line=src_node.start_point[0] + 1,
                end_line=src_node.end_point[0] + 1,
                source=source,
                signature=_signature(source),
                calls=calls,
                renders=renders,
                member_only=_member_only(calls, direct),
                typed_calls=_typed_calls(node, src, env, attrs, "js"),
                exported=exported,
                entry=exported and k == "component",
            )
        )

    def add_js_class(cname, node, outer, body, exported):
        """The class itself: header, `extends`, fields. Methods are symbols of their own."""
        start = outer.start_byte
        head = src[start : body.start_byte if body is not None else node.end_byte].decode("utf8", "replace")
        fields = [_text(m, src) for m in (body.named_children if body is not None else []) if m.type != "method_definition"]
        source = head + "{" + ("\n  " + "\n  ".join(fields) + "\n" if fields else "") + "}"
        bases = re.findall(r"\bextends\s+([\w$.]+)", head)
        attrs: dict[str, str] = {}
        for m in body.named_children if body is not None else []:
            if m.type == "public_field_definition":
                nm, ann, val = m.child_by_field_name("name"), m.child_by_field_name("type"), m.child_by_field_name("value")
                t = _type_name(_text(ann, src)) if ann is not None else _ctor(val, src)
                if nm is not None and t:
                    attrs[_text(nm, src)] = t
            elif m.type == "method_definition":
                attrs.update(_js_env(m, src, module_env)[1])
        class_attrs[cname] = attrs
        calls, direct = [], set()
        for m in body.named_children if body is not None else []:
            if m.type != "method_definition":
                c, _, d = _js_calls(m, src)
                calls += c
                direct |= d
        out.append(
            Symbol(
                file=path, qualname=cname, name=cname, kind="class", lang=lang,
                start_line=outer.start_point[0] + 1, end_line=outer.end_point[0] + 1,
                source=source, signature=_signature(head.strip() + " {"),
                calls=calls, member_only=_member_only(calls, direct),
                bases=[b.split(".")[-1] for b in bases], exported=exported,
            )
        )

    def visit(stmt, exported=False, outer=None):
        outer = outer or stmt
        t = stmt.type
        if t == "export_statement":
            decl = stmt.child_by_field_name("declaration")
            is_default = any(c.type == "default" for c in stmt.children)
            if decl is not None:
                visit(decl, True, stmt)
            else:
                for c in stmt.named_children:
                    if c.type in _JS_FUNC_VALUES:
                        add("default", "default", c, stmt, True)
                    elif c.type in ("function_declaration", "class_declaration"):
                        visit(c, True, stmt)
            if is_default:
                for s in out[-1:]:
                    s.entry = True
        elif t in ("function_declaration", "generator_function_declaration"):
            nm = stmt.child_by_field_name("name")
            if nm is not None:
                name = _text(nm, src)
                add(name, name, stmt, outer, exported)
        elif t in ("lexical_declaration", "variable_declaration"):
            for d in stmt.named_children:
                if d.type != "variable_declarator":
                    continue
                nm = d.child_by_field_name("name")
                val = _wrapped_function(d.child_by_field_name("value"))
                if nm is not None and nm.type == "identifier" and val is not None:
                    name = _text(nm, src)
                    add(name, name, d, outer, exported)
        elif t in ("class_declaration", "abstract_class_declaration"):
            cn = stmt.child_by_field_name("name")
            cname = _text(cn, src) if cn is not None else "Class"
            body = stmt.child_by_field_name("body")
            add_js_class(cname, stmt, outer, body, exported)
            for m in body.named_children if body is not None else []:
                if m.type == "method_definition":
                    mn = m.child_by_field_name("name")
                    if mn is not None:
                        mname = _text(mn, src)
                        add(mname, f"{cname}.{mname}", m, m, exported, kind="method")

    for stmt in tree.root_node.named_children:
        visit(stmt)
    return out


# ----------------------------------------------------------------- Python ---

_ROUTE = re.compile(r"@\w+\.(route|get|post|put|patch|delete|websocket|task|command)\b|@(app|router|bp|blueprint)\.")


def _py_calls(node, src):
    calls, direct = [], set()
    for n in _walk(node):
        if n.type == "call":
            fn = n.child_by_field_name("function")
            if fn is None:
                continue
            if fn.type == "identifier":
                calls.append(_text(fn, src))
                direct.add(calls[-1])
            elif fn.type == "attribute":
                a = fn.child_by_field_name("attribute")
                obj = fn.child_by_field_name("object")
                if a is not None:
                    calls.append(_text(a, src))
                    receiver = _text(obj, src) if obj is not None else ""
                    if receiver in _OWN or receiver == "super()":
                        direct.add(calls[-1])
    return calls, direct


def _parse_py(path, src, lang):
    tree = _parser(lang).parse(src)
    out: list[Symbol] = []
    module_env: dict[str, str] = {}
    for stmt in tree.root_node.named_children:
        if stmt.type in ("expression_statement", "assignment"):  # grammar versions differ
            module_env.update(_py_env(stmt, src, {})[0])
    class_attrs: dict[str, dict] = {}

    def decorators(outer):
        names = []
        for d in outer.children if outer.type == "decorated_definition" else []:
            if d.type != "decorator":
                continue
            expr = d.named_children[0] if d.named_children else None
            if expr is not None and expr.type == "call":
                expr = expr.child_by_field_name("function")
            if expr is None:
                continue
            if expr.type == "attribute":
                expr = expr.child_by_field_name("attribute")
            if expr is not None and expr.type == "identifier":
                names.append(_text(expr, src))
        return names

    def func(defn, outer, cls=None):
        nm = defn.child_by_field_name("name")
        if nm is None:
            return
        name = _text(nm, src)
        qual = f"{cls}.{name}" if cls else name
        source = _text(outer, src)
        calls, direct = _py_calls(defn, src)
        env, attrs = _py_env(defn, src, module_env)
        if cls:
            attrs = {**class_attrs.get(cls, {}), **attrs}
        out.append(
            Symbol(
                file=path,
                qualname=qual,
                name=name,
                kind="method" if cls else "function",
                lang=lang,
                start_line=outer.start_point[0] + 1,
                end_line=outer.end_point[0] + 1,
                source=source,
                signature=_signature(source),
                calls=calls,
                member_only=_member_only(calls, direct),
                typed_calls=_typed_calls(defn, src, env, attrs, "python"),
                decorators=decorators(outer),
                exported=not name.startswith("_") or (name.startswith("__") and name.endswith("__")),
                entry=bool(_ROUTE.search(source)) or name == "main",
            )
        )

    def py_class(cname, defn, outer, body):
        """The class itself: decorators, bases, class attributes. Methods are symbols of their own."""
        head = src[outer.start_byte : body.start_byte if body is not None else defn.end_byte].decode("utf8", "replace")
        own = []
        calls, direct = [], set()
        attrs: dict[str, str] = {}
        for m in body.named_children if body is not None else []:
            md, _ = unwrap(m)
            if md is not None and md.type == "function_definition":
                attrs.update(_py_env(md, src, module_env)[1])
                continue
            if m.type in ("expression_statement", "assignment"):  # `repo: Repo` or `repo = Repo()` at class level
                for n in ([m] if m.type == "assignment" else m.named_children):
                    if n.type == "assignment" and n.child_by_field_name("left") is not None and n.child_by_field_name("left").type == "identifier":
                        ann = n.child_by_field_name("type")
                        t = _type_name(_text(ann, src)) if ann is not None else _ctor(n.child_by_field_name("right"), src)
                        if t:
                            attrs[_text(n.child_by_field_name("left"), src)] = t
            own.append(_text(m, src))
            c, d = _py_calls(m, src)
            calls += c
            direct |= d
        class_attrs[cname] = attrs
        bases = []
        sup = defn.child_by_field_name("superclasses")
        for a in sup.named_children if sup is not None else []:
            if a.type in ("identifier", "attribute"):
                name = _text(a, src).split(".")[-1]
                if name != "object":
                    bases.append(name)
        source = head.rstrip() + ("\n    " + "\n    ".join(own) if own else "\n    ...")
        out.append(
            Symbol(
                file=path, qualname=cname, name=cname, kind="class", lang=lang,
                start_line=outer.start_point[0] + 1, end_line=outer.end_point[0] + 1,
                source=source, signature=_signature(head),
                calls=calls, member_only=_member_only(calls, direct), decorators=decorators(outer),
                bases=bases, exported=not cname.startswith("_"),
            )
        )

    def unwrap(stmt):
        if stmt.type == "decorated_definition":
            d = stmt.child_by_field_name("definition")
            return d, stmt
        return stmt, stmt

    for stmt in tree.root_node.named_children:
        defn, outer = unwrap(stmt)
        if defn is None:
            continue
        if defn.type == "function_definition":
            func(defn, outer)
        elif defn.type == "class_definition":
            cn = defn.child_by_field_name("name")
            cname = _text(cn, src) if cn is not None else "Class"
            body = defn.child_by_field_name("body")
            py_class(cname, defn, outer, body)
            for m in body.named_children if body is not None else []:
                md, mo = unwrap(m)
                if md is not None and md.type == "function_definition":
                    func(md, mo, cname)
    return out


# -------------------------------------------------------------------- SQL ---

_SQL_KINDS = {
    "create_table": "table",
    "create_view": "view",
    "create_materialized_view": "view",
    "create_function": "sql_function",
    "create_index": "index",
    "create_trigger": "trigger",
    "alter_table": "alter",
    "select": "query",
    "insert": "query",
    "update": "query",
    "delete": "query",
}
_SQL_NAMED = {"table", "view", "sql_function", "index", "trigger"}


def _sql_ident(node, src):
    return _text(node, src).strip().strip('"`[]').lower()


def _parse_sql(path, src, lang):
    tree = _parser(lang).parse(src)
    out: list[Symbol] = []
    for stmt in tree.root_node.named_children:
        if stmt.type != "statement" or not stmt.named_children:
            continue
        body = stmt.named_children[0]
        kind = _SQL_KINDS.get(body.type)
        if kind is None:
            continue
        source = _text(stmt, src)
        refs = []
        name = None
        if body.type == "create_index":
            ident = next((c for c in body.named_children if c.type == "identifier"), None)
            name = _sql_ident(ident, src) if ident is not None else None
        for n in _walk(body):
            if n.type == "object_reference":
                refs.append(_sql_ident(n, src))
        if kind in _SQL_NAMED and kind != "index" and refs:
            name = refs[0]
            refs = refs[1:]
        if kind == "alter" and refs:
            name = f"alter {refs[0]}"
        line = stmt.start_point[0] + 1
        if name is None:
            digest = hashlib.sha1(re.sub(r"\s+", " ", source).strip().lower().encode()).hexdigest()[:8]
            qual = f"{kind}:{digest}"
            label = f"{body.type} L{line}"
        else:
            qual = name
            label = name
        out.append(
            Symbol(
                file=path,
                qualname=qual,
                name=name or label,
                kind=kind,
                lang=lang,
                start_line=line,
                end_line=stmt.end_point[0] + 1,
                source=source,
                signature=_signature(source),
                refs=sorted(set(r for r in refs if r and r != name)),
                exported=True,
                entry=kind in ("view", "sql_function"),
                label=label,
            )
        )
    return out


# ------------------------------------------------------------------ entry ---


def parse_file(path: str, text: str) -> list[Symbol]:
    lang = language_for(path)
    if lang is None:
        return []
    src = text.encode("utf8")
    if lang == "python":
        syms = _parse_py(path, src, lang)
    elif lang == "sql":
        syms = _parse_sql(path, src, lang)
    else:
        syms = _parse_js(path, src, lang)
    seen: dict[str, int] = {}
    for s in syms:
        if not s.label:
            s.label = s.qualname
        n = seen.get(s.qualname, 0)
        seen[s.qualname] = n + 1
        if n:
            s.qualname = f"{s.qualname}#{n + 1}"
    return syms
