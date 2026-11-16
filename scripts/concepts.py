"""Load concept catalogues from references/stacks/*.md and detect them in symbols."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from parse import STACK_LANG, Symbol

LANG_ALIASES = {"tsx": "js", "jsx": "js", "ts": "js", "js": "js", "typescript": "js", "javascript": "js", "python": "python", "sql": "sql"}


@dataclass
class Concept:
    id: str
    label: str
    stack: str
    langs: set[str]
    calls: list[str] = field(default_factory=list)
    regexes: list[re.Pattern] = field(default_factory=list)
    names: list[re.Pattern] = field(default_factory=list)
    requires: list[str] = field(default_factory=list)
    fundamental: str = ""
    what: str = ""
    pitfalls: list[str] = field(default_factory=list)
    relates: list[str] = field(default_factory=list)
    risk: bool = False
    minor: bool = False  # everywhere and basic: drawn only when nothing more telling is left


@dataclass
class Fundamental:
    id: str
    label: str
    one_liner: str
    example: str
    example_lang: str


def _front_matter(text: str) -> tuple[dict, str]:
    meta = {}
    if text.startswith("---"):
        end = text.find("\n---", 3)
        if end != -1:
            for line in text[3:end].strip().splitlines():
                if ":" in line:
                    k, v = line.split(":", 1)
                    meta[k.strip()] = v.strip()
            text = text[end + 4 :]
    return meta, text


def load_concepts(ref_dir: Path) -> dict[str, Concept]:
    out: dict[str, Concept] = {}
    for md in sorted((ref_dir / "stacks").glob("*.md")):
        meta, body = _front_matter(md.read_text(encoding="utf8"))
        stack = meta.get("stack", md.stem)
        langs = {LANG_ALIASES.get(l.strip(), l.strip()) for l in meta.get("languages", "").split(",") if l.strip()}
        flags = re.IGNORECASE if "sql" in langs else 0
        for section in re.split(r"(?m)^## ", body)[1:]:
            lines = section.splitlines()
            label = lines[0].strip()
            c = Concept(id="", label=label, stack=stack, langs=langs)
            for line in lines[1:]:
                m = re.match(r"^- (\w+):\s?(.*)$", line)
                if not m:
                    continue
                key, val = m.group(1), m.group(2).strip()
                if key == "id":
                    c.id = val
                elif key == "detect":
                    kind, _, arg = val.partition(" ")
                    arg = arg.strip()
                    if kind == "call":
                        c.calls.append(arg)
                    elif kind == "regex":
                        c.regexes.append(re.compile(arg, flags | re.MULTILINE))
                    elif kind == "name":
                        c.names.append(re.compile(arg))
                elif key == "requires" and val:
                    c.requires += [v.strip() for v in val.split(",") if v.strip()]
                elif key == "fundamental":
                    c.fundamental = val
                elif key == "what":
                    c.what = val
                elif key == "pitfalls":
                    c.pitfalls = [p.strip()[:1].upper() + p.strip()[1:].rstrip(".") + "." for p in val.split(";") if p.strip()]
                elif key == "risk":
                    c.risk = val.lower() in ("yes", "true", "1")
                elif key == "minor":
                    c.minor = val.lower() in ("yes", "true", "1")
                elif key == "relates" and val:
                    c.relates = [v.strip() for v in val.split(",") if v.strip()]
            if c.id:
                out[c.id] = c
    return out


def load_fundamentals(ref_dir: Path) -> dict[str, Fundamental]:
    text = (ref_dir / "fundamentals.md").read_text(encoding="utf8")
    out = {}
    for section in re.split(r"(?m)^## ", text)[1:]:
        label = section.splitlines()[0].strip()
        fid = re.search(r"(?m)^- id:\s*(\S+)", section)
        one = re.search(r"(?m)^- one-liner:\s*(.+)$", section)
        ex = re.search(r"```(\w*)\n(.*?)```", section, re.DOTALL)
        if fid:
            out[fid.group(1)] = Fundamental(
                id=fid.group(1),
                label=label,
                one_liner=one.group(1).strip() if one else "",
                example=ex.group(2).rstrip() if ex else "",
                example_lang=ex.group(1) if ex else "",
            )
    return out


_PY_TRIPLE = re.compile(r"(?s)[rbfuRBFU]{0,2}(\"\"\"|''').*?\1")
_PY_STRING = re.compile(r"[rbfuRBFU]{0,2}(\"|')(?:\\.|(?!\1)[^\\\n])*\1")


def _strip_comments(source: str, lang: str) -> str:
    """Comments, and in Python string literals too: a docstring that says "await" is not async code."""
    if lang == "python":
        source = _PY_TRIPLE.sub('""', source)
        source = _PY_STRING.sub('""', source)
        source = re.sub(r"(?m)#.*$", "", source)
    elif lang == "sql":
        source = re.sub(r"--.*$", "", source, flags=re.MULTILINE)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    else:
        source = re.sub(r"(?m)//.*$", "", source)
        source = re.sub(r"/\*.*?\*/", "", source, flags=re.DOTALL)
    return source


def detect(symbol: Symbol, catalogue: dict[str, Concept]) -> list[str]:
    family = STACK_LANG.get(symbol.lang, symbol.lang)
    code = _strip_comments(symbol.source, symbol.lang)
    calls = set(symbol.calls)
    found = []
    for c in catalogue.values():
        if family not in c.langs:
            continue
        hit = (
            any(name in calls for name in c.calls)
            or any(rx.search(code) for rx in c.regexes)
            or any(rx.search(symbol.name) for rx in c.names)
        )
        if hit:
            found.append(c.id)
    # SQL written in a Python or JS string: the SQL rules run on it.
    if symbol.embedded_sql and family != "sql":
        sql = _strip_comments("\n;\n".join(symbol.embedded_sql), "sql")
        for c in catalogue.values():
            if "sql" in c.langs and c.id not in found and any(rx.search(sql) for rx in c.regexes):
                found.append(c.id)
    # `requires` is checked after everything else is known.
    present = set(found)
    return [cid for cid in found if all(r in present for r in catalogue[cid].requires)]
