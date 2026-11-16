"""`underneath map` and `underneath gaps`: 5-line cards and the project map page.

The page reuses latest.html's style, nodes and click panel: one row per
fundamental, the concepts of the code that rest on it to its right, most
used first. Budgets: 7 fundamentals, 4 concepts per row, the rest one click away.
"""

from __future__ import annotations

import html
import json
from pathlib import Path

from concepts import Concept, Fundamental
from render import CSS, JS, PAD, _node_svg

MAP_FUNDAMENTALS = 7
MAP_PER_ROW = 4
GAP_ROWS = 4
F_W, F_H = 164, 44
C_W, C_H = 152, 48
ROW, GAP = 62, 14


def _state(cid: str, registry: dict) -> tuple[str, str]:
    """(css class, words) for a concept, from the registry."""
    e = registry.get("concepts", {}).get(cid, {})
    if e.get("known"):
        return "co ctx", "marked known"
    if e.get("seen", 0) == 0:
        return "co co-new", "never seen in a change"
    return "co", f"seen in {e['seen']} change{'s' if e['seen'] > 1 else ''}"


def _name(cid: str, catalogue: dict[str, Concept]) -> str:
    """The concept's label, with its id prefix when another stack uses the same label (async / await)."""
    c = catalogue[cid]
    twins = [o for o in catalogue.values() if o.label == c.label and o.id != cid]
    return f"{c.label} ({cid.split('.')[0]})" if twins else c.label


def _n(count: int, word: str) -> str:
    """`1 use`, `12 uses`, `1,204 uses`."""
    return f"{count:,} {word}{'' if count == 1 else 's'}"


def _label(fid: str, fundamentals: dict[str, Fundamental]) -> str:
    return fundamentals[fid].label if fid in fundamentals else fid.replace("-", " ").capitalize()


# ------------------------------------------------------------------ cards ---


def map_card(data: dict, groups: list[dict], catalogue: dict[str, Concept], fundamentals: dict, gap_ids: list[str], html_path: str) -> str:
    n_c = len(data["concepts"])
    head = f"underneath map · {data['files']:,} files · {data['functions']:,} functions · {n_c} concept{'s' if n_c != 1 else ''}"
    head += f" on {len(groups)} fundamental{'s' if len(groups) != 1 else ''}" if groups else ""
    if not groups:
        return "\n".join([head, "  none  no known concept in this code yet (stacks: references/stacks/*.md)", f"  map   {html_path}"])
    top = "  top   " + " · ".join(f"{_label(g['id'], fundamentals).lower()} {g['count']:,}" for g in groups[:3])
    used = sorted(data["concepts"], key=lambda c: (-data["concepts"][c]["count"], c))
    most = "  most  " + " · ".join(f"{_name(c, catalogue)} {data['concepts'][c]['count']:,}" for c in used[:3])
    risks = [c for c in used if catalogue[c].risk]
    extra: dict[str, str] = {}
    if risks:
        c = risks[0]
        more = f" (+{len(risks) - 1} other)" if len(risks) > 1 else ""
        extra["risk"] = f"  ⚠     {_name(c, catalogue)} ×{data['concepts'][c]['count']} · first at {data['concepts'][c]['places'][0]}{more}"
    if gap_ids:
        extra["gaps"] = f"  gaps  {len(gap_ids)} never marked known · /underneath gaps"
    extra["most"] = most
    keep = [k for k in ("risk", "gaps", "most") if k in extra][:2]  # 5 lines: head, top, two of these, map
    body = [top] + [extra[k] for k in ("most", "risk", "gaps") if k in keep]
    return "\n".join([head, *body, f"  map   {html_path}"])


def gaps_card(data: dict, gap_ids: list[str], catalogue: dict[str, Concept]) -> str:
    total = len(data["concepts"])
    if not total:
        return "underneath gaps · no known concept in this code yet"
    if not gap_ids:
        return f"underneath gaps · all {total} concepts in your code are marked known"
    lines = [f"underneath gaps · {len(gap_ids)} of {total} concepts in your code never marked known, most used first"]
    rows = gap_ids[:GAP_ROWS]
    width = max(len(_name(c, catalogue)) for c in rows)
    nw = max(len(f"{data['concepts'][c]['count']:,}") for c in rows)
    for c in rows:
        n = f"{data['concepts'][c]['count']:,}"
        lines.append(f"  {_name(c, catalogue):<{width}}  {n:>{nw}}×  /underneath deeper {c}")
    return "\n".join(lines)


# ------------------------------------------------------------------- page ---


def _layout(groups: list[dict]) -> tuple[dict, list[tuple[str, list[str], bool]], int, int]:
    rows = [(g["id"], g["concepts"][:MAP_PER_ROW], len(g["concepts"]) > MAP_PER_ROW) for g in groups[:MAP_FUNDAMENTALS]]
    pos: dict[str, dict] = {}
    for r, (fid, cids, more) in enumerate(rows):
        y = PAD + r * ROW
        pos["f:" + fid] = {"x": PAD, "y": y + (C_H - F_H) / 2, "w": F_W, "h": F_H}
        for i, cid in enumerate(cids + (["more:" + fid] if more else [])):
            pos[cid] = {"x": PAD + F_W + 40 + i * (C_W + GAP), "y": y, "w": C_W, "h": C_H}
    if len(groups) > MAP_FUNDAMENTALS:
        pos["more:fundamentals"] = {"x": PAD, "y": PAD + len(rows) * ROW, "w": F_W, "h": F_H}
    width = PAD * 2 + F_W + 40 + (MAP_PER_ROW + 1) * (C_W + GAP)
    height = PAD * 2 + (len(rows) + (1 if len(groups) > MAP_FUNDAMENTALS else 0)) * ROW
    return pos, rows, width, max(height, 120)


def map_page(data: dict, groups: list[dict], catalogue: dict[str, Concept], fundamentals: dict[str, Fundamental], registry: dict, gap_ids: list[str]) -> str:
    e = html.escape
    pos, rows, width, height = _layout(groups)
    parts = [
        f'<svg viewBox="0 0 {width} {height}" width="{width}" role="img" aria-label="Concepts of the project grouped by the fundamental they rest on">'
    ]
    items: dict[str, dict] = {}
    for fid, cids, more in rows:
        f, last = pos["f:" + fid], pos[(["more:" + fid] if more else cids)[-1]]
        y = f["y"] + f["h"] / 2
        parts.append(f'<g class="ed fund" data-a="f:{e(fid)}" data-b=""><path d="M{f["x"] + f["w"]:.1f} {y:.1f} H{last["x"] + last["w"] / 2:.1f}"/></g>')
    for fid, cids, more in rows:
        g = next(x for x in groups if x["id"] == fid)
        parts.append(_node_svg("f:" + fid, pos["f:" + fid], _label(fid, fundamentals), _n(g['count'], 'use'), "fu"))
        fu = fundamentals.get(fid)
        items["f:" + fid] = {
            "label": _label(fid, fundamentals),
            "loc": f"fundamental · {_n(g['count'], 'use')} in your code" + (f" · /underneath deeper {fid}" if fu else ""),
            "text": fu.one_liner if fu else "",
            "example": fu.example if fu else "",
            "users": g["concepts"],
        }
        for cid in g["concepts"]:
            c, info = catalogue[cid], data["concepts"][cid]
            cls, state = _state(cid, registry)
            if cid in cids:
                parts.append(_node_svg(cid, pos[cid], _name(cid, catalogue), f"{_n(info['count'], 'use')} · {_n(info['files'], 'file')}", cls, c.risk))
            items[cid] = {
                "label": _name(cid, catalogue),
                "loc": f"concept · {c.stack} · {_n(info['count'], 'use')} in {_n(info['files'], 'file')} · {state}",
                "text": c.what,
                "watch": [f"likely bug at {p}" for p in info["places"]],
                "pitfalls": c.pitfalls[:2],
                "fundamental": "f:" + fid if fid in fundamentals else None,
                "tests": f"/underneath deeper {cid}" + (" · /underneath known " + cid if "ctx" not in cls else ""),
                "list": ["Main files: " + ", ".join(f"{rel} ({n})" for rel, n in info["top_files"])],
            }
        if more:
            rest = g["concepts"][MAP_PER_ROW:]
            parts.append(_node_svg("more:" + fid, pos["more:" + fid], f"+{len(rest)} more", "on this fundamental", "fn-more"))
            items["more:" + fid] = {"label": f"+{len(rest)} more", "loc": _label(fid, fundamentals), "text": "", "users": rest}
    if "more:fundamentals" in pos:
        rest = groups[MAP_FUNDAMENTALS:]
        parts.append(_node_svg("more:fundamentals", pos["more:fundamentals"], f"+{len(rest)} fundamentals", "used less", "fn-more"))
        items["more:fundamentals"] = {
            "label": f"+{len(rest)} fundamentals",
            "loc": "used less in this code",
            "text": "",
            "list": [f"{_label(g['id'], fundamentals)} ({g['count']:,}): " + ", ".join(catalogue[c].label for c in g["concepts"]) for g in rest],
        }
        for g in rest:
            for cid in g["concepts"]:
                items.setdefault(cid, {"label": catalogue[cid].label, "loc": "concept", "text": catalogue[cid].what})
    parts.append("</svg>")

    start = next(iter(items), "")
    chips = [
        f'<span class="chip n">{data["files"]:,} files</span>',
        f'<span class="chip">{data["functions"]:,} functions</span>',
        f'<span class="chip c">{len(data["concepts"])} concepts</span>',
    ]
    if gap_ids:
        chips.append(f'<span class="chip">{len(gap_ids)} never marked known</span>')
    n_risk = sum(data["concepts"][c]["count"] for c in data["concepts"] if catalogue[c].risk)
    if n_risk:
        chips.append(f'<span class="chip w">{n_risk} likely bug{"s" if n_risk > 1 else ""}</span>')
    payload = json.dumps({"items": items, "start": start}).replace("</", "<\\/")
    note = " Only the first 3,000 files were read." if data.get("truncated") else ""
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>underneath map · {e(Path(data['root']).name)}</title><style>{CSS}</style></head>
<body><main>
<header><h1>underneath map</h1>{''.join(chips)}<span class="sp"></span><button id="toggle">New only</button></header>
<div class="wrap">{''.join(parts)}</div>
<div class="legend">Each row: a fundamental, then the concepts of your code that rest on it, most used first. Thick border: never seen in a change. Faded: marked known ("New only" hides them). Amber dot: a likely-bug pattern. Test files are not counted.{note}</div>
<section id="panel" aria-live="polite"></section>
<footer>{e(data['root'])} · {data['files']:,} files, {data['test_files']:,} test files not counted · {e(data['generated'])}</footer>
</main>
<script type="application/json" id="data">{payload}</script>
<script>{JS}</script>
</body></html>"""
