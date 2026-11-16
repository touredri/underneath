"""Turn graph.json + notes.json into the 5-line card and the self-contained HTML map."""

from __future__ import annotations

import html
import json
from collections import defaultdict
from datetime import date
from pathlib import Path

from concepts import Fundamental

CAPS = {"summary": 140, "here": 160, "watch": 90, "fundamental": 220, "label": 18}
MAX_INFERRED = 4
MAX_WATCH = 2


def _cap(text: str, n: int) -> str:
    text = " ".join(str(text).split())
    return text if len(text) <= n else text[: n - 1].rstrip() + "…"


# ----------------------------------------------------------------- notes ---


def clean_notes(raw: dict, graph: dict, fundamentals: dict[str, Fundamental]) -> tuple[dict, list[str]]:
    """Keep only what refers to things that exist in the graph. Report the rest."""
    warn: list[str] = []
    node_ids = {n["id"] for n in graph["nodes"]}
    concept_ids = {c["id"] for c in graph["concepts"]}
    any_ids = node_ids | concept_ids
    out = {"nodes": {}, "concepts": {}, "inferred_edges": [], "watch": [], "fundamental": None}

    for nid, val in (raw.get("nodes") or {}).items():
        if nid not in node_ids:
            warn.append(f"notes.nodes: unknown node '{nid}' dropped")
            continue
        s = (val or {}).get("summary") if isinstance(val, dict) else val
        if s:
            if len(" ".join(str(s).split())) > CAPS["summary"]:
                warn.append(f"notes.nodes.{nid}: summary over {CAPS['summary']} chars, cut")
            out["nodes"][nid] = {"summary": _cap(s, CAPS["summary"])}

    for cid, val in (raw.get("concepts") or {}).items():
        if cid not in concept_ids:
            warn.append(f"notes.concepts: '{cid}' is not in this graph, dropped")
            continue
        h = (val or {}).get("here") if isinstance(val, dict) else val
        if h:
            out["concepts"][cid] = {"here": _cap(h, CAPS["here"])}

    existing = {(e["from"], e["to"]) for e in graph["edges"]}
    for e in raw.get("inferred_edges") or []:
        a, b, label = e.get("from"), e.get("to"), _cap(e.get("label", "relates"), 14)
        if a not in any_ids or b not in any_ids or a == b:
            warn.append(f"notes.inferred_edges: {a} -> {b} refers to unknown ids, dropped")
            continue
        if (a, b) in existing:
            continue
        if len(out["inferred_edges"]) >= MAX_INFERRED:
            warn.append("notes.inferred_edges: more than 4, extra dropped")
            break
        out["inferred_edges"].append({"from": a, "to": b, "type": label, "provenance": "inferred"})

    by_id = {n["id"]: n for n in graph["nodes"]}
    for w in raw.get("watch") or []:
        nid = w.get("node")
        if nid not in node_ids or by_id[nid]["status"] == "context":
            warn.append(f"notes.watch: '{nid}' is not a changed node, dropped")
            continue
        if len(out["watch"]) >= MAX_WATCH:
            warn.append("notes.watch: more than 2, extra dropped")
            break
        line = w.get("line") or by_id[nid]["line"]
        n = by_id[nid]
        if not (n["line"] <= int(line) <= n["end_line"]):
            line = n["line"]
        out["watch"].append({"node": nid, "file": n["file"], "line": int(line), "text": _cap(w.get("text", ""), CAPS["watch"])})

    f = raw.get("fundamental") or {}
    fid = f.get("id") if isinstance(f, dict) else f
    cands = graph.get("fundamental_candidates") or []
    if fid and fid not in fundamentals:
        warn.append(f"notes.fundamental: '{fid}' is not in references/fundamentals.md, using the top candidate")
        fid = None
    if not fid and cands:
        fid = cands[0]
    if fid:
        text = f.get("text") if isinstance(f, dict) else None
        out["fundamental"] = {
            "id": fid,
            "label": fundamentals[fid].label,
            "text": _cap(text, CAPS["fundamental"]) if text else fundamentals[fid].one_liner,
        }
    return out, warn


# ---------------------------------------------------------------- layout ---

FN_W, FN_H, FN_STEP = 152, 48, 64
CO_W, CO_H, CO_STEP = 164, 34, 46
COL_GAP = 54
PAD = 16


def layout(graph: dict, notes: dict) -> dict:
    nodes = graph["nodes"]
    fn_edges = [e for e in graph["edges"] if e["type"] != "uses"]
    layer = {n["id"]: 0 for n in nodes}
    for _ in range(len(nodes) + 1):
        changed = False
        for e in fn_edges:
            a, b = e["from"], e["to"]
            if a in layer and b in layer and layer[b] < layer[a] + 1 <= 3:
                layer[b] = layer[a] + 1
                changed = True
        if not changed:
            break
    used = sorted(set(layer.values()))
    remap = {v: i for i, v in enumerate(used)}
    layer = {k: remap[v] for k, v in layer.items()}
    ncols = (max(layer.values()) + 1) if layer else 1

    cols: dict[int, list[str]] = defaultdict(list)
    order = {n["id"]: i for i, n in enumerate(nodes)}
    for n in nodes:
        cols[layer[n["id"]]].append(n["id"])
    for c in cols.values():
        c.sort(key=lambda k: order[k])

    preds = defaultdict(list)
    succs = defaultdict(list)
    for e in fn_edges:
        preds[e["to"]].append(e["from"])
        succs[e["from"]].append(e["to"])
    for _ in range(2):
        for ci in range(1, ncols):
            pos = {k: i for col in cols.values() for i, k in enumerate(col)}
            cols[ci].sort(key=lambda k: (sum(pos[p] for p in preds[k]) / len(preds[k])) if preds[k] else pos[k])
        for ci in range(ncols - 2, -1, -1):
            pos = {k: i for col in cols.values() for i, k in enumerate(col)}
            cols[ci].sort(key=lambda k: (sum(pos[s] for s in succs[k]) / len(succs[k])) if succs[k] else pos[k])

    more = graph["summary"]["hidden_changed"]
    if more:
        cols[ncols - 1].append("more")

    concept_ids = [c["id"] for c in graph["concepts"]]
    users = {c["id"]: c["users"] for c in graph["concepts"]}
    fpos = {k: i for col in cols.values() for i, k in enumerate(col)}
    concept_ids.sort(key=lambda c: sum(fpos.get(u, 0) for u in users[c]) / max(len(users[c]), 1))

    fn_height = max((len(c) for c in cols.values()), default=1) * FN_STEP
    has_f = bool(notes.get("fundamental"))
    co_height = len(concept_ids) * CO_STEP + (CO_STEP + 12 if has_f else 0)
    height = max(fn_height, co_height, 120)

    pos: dict[str, dict] = {}
    for ci in range(ncols):
        col = cols[ci]
        top = (height - len(col) * FN_STEP) / 2
        for i, k in enumerate(col):
            pos[k] = {"x": PAD + ci * (FN_W + COL_GAP), "y": top + i * FN_STEP + (FN_STEP - FN_H) / 2, "w": FN_W, "h": FN_H}
    cx = PAD + ncols * (FN_W + COL_GAP) + 10 if concept_ids or has_f else PAD + ncols * (FN_W + COL_GAP)
    top = (height - co_height) / 2
    for i, cid in enumerate(concept_ids):
        pos[cid] = {"x": cx, "y": top + i * CO_STEP + (CO_STEP - CO_H) / 2, "w": CO_W, "h": CO_H}
    if has_f:
        fid = "f:" + notes["fundamental"]["id"]
        pos[fid] = {"x": cx, "y": top + len(concept_ids) * CO_STEP + 12 + (CO_STEP - 40) / 2, "w": CO_W, "h": 40}
    width = (cx + CO_W + PAD + 48) if (concept_ids or has_f) else (PAD + ncols * (FN_W + COL_GAP) - COL_GAP + PAD + 24)
    return {"pos": pos, "width": width, "height": height}


def _route(a: dict, b: dict) -> tuple[str, tuple[float, float]]:
    ay, by = a["y"] + a["h"] / 2, b["y"] + b["h"] / 2
    if b["x"] > a["x"] + a["w"] - 1:
        x1, x2 = a["x"] + a["w"], b["x"] - 3
        dx = max((x2 - x1) * 0.5, 20)
        return f"M{x1:.1f} {ay:.1f} C{x1 + dx:.1f} {ay:.1f} {x2 - dx:.1f} {by:.1f} {x2:.1f} {by:.1f}", ((x1 + x2) / 2, (ay + by) / 2)
    if abs(b["x"] - a["x"]) < 1:
        x = a["x"] + a["w"]
        bend = x + 26
        return f"M{x:.1f} {ay:.1f} C{bend:.1f} {ay:.1f} {bend:.1f} {by:.1f} {x + 3:.1f} {by:.1f}", (bend, (ay + by) / 2)
    x1, x2 = a["x"], b["x"] + b["w"] + 3
    return f"M{x1:.1f} {ay:.1f} C{x1 - 40:.1f} {ay:.1f} {x2 + 40:.1f} {by:.1f} {x2:.1f} {by:.1f}", ((x1 + x2) / 2, (ay + by) / 2)


# ------------------------------------------------------------------- svg ---


def _short(title: str, n: int) -> str:
    """Keep the end of `Class.method`: the method name is what people look for."""
    if len(title) <= n or "." not in title:
        return _cap(title, n)
    cls, meth = title.rsplit(".", 1)
    room = n - len(meth) - 2
    if room < 3:
        return _cap(meth, n)
    return f"{cls[:room]}….{meth}"


def _node_svg(nid: str, p: dict, title: str, sub: str, cls: str, badge: bool = False) -> str:
    e = html.escape
    t = _short(title, CAPS["label"])
    cy = p["y"] + p["h"] / 2
    if sub:
        texts = (
            f'<text class="t" x="{p["x"] + p["w"] / 2:.1f}" y="{cy - 3:.1f}">{e(t)}</text>'
            f'<text class="s" x="{p["x"] + p["w"] / 2:.1f}" y="{cy + 13:.1f}">{e(sub)}</text>'
        )
    else:
        texts = f'<text class="t" x="{p["x"] + p["w"] / 2:.1f}" y="{cy + 5:.1f}">{e(t)}</text>'
    return (
        f'<g class="nd {cls}" data-id="{e(nid)}" tabindex="0">'
        f'<title>{e(title)}</title>'
        f'<rect x="{p["x"]:.1f}" y="{p["y"]:.1f}" width="{p["w"]}" height="{p["h"]}" rx="5"/>{texts}'
        + (
            f'<g class="bdg"><circle cx="{p["x"] + p["w"] - 2:.1f}" cy="{p["y"] + 2:.1f}" r="8"/>'
            f'<text x="{p["x"] + p["w"] - 2:.1f}" y="{p["y"] + 6:.1f}">!</text></g>'
            if badge
            else ""
        )
        + "</g>"
    )


def svg(graph: dict, notes: dict, lay: dict) -> str:
    pos = lay["pos"]
    parts = [
        f'<svg viewBox="0 0 {lay["width"]:.0f} {lay["height"]:.0f}" width="{lay["width"]:.0f}" role="img" aria-label="Map of the changed functions and the concepts they use">',
        '<defs><marker id="ar" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" class="arh"/></marker>'
        '<marker id="ari" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="6" markerHeight="6" orient="auto"><path d="M0 0L10 5L0 10z" class="arhi"/></marker></defs>',
    ]
    status = {n["id"]: n["status"] for n in graph["nodes"]}

    def edge(e, cls, marker, label=None):
        a, b = e["from"], e["to"]
        if a not in pos or b not in pos:
            return ""
        d, mid = _route(pos[a], pos[b])
        ctx = " ctx" if status.get(a) == "context" or status.get(b) == "context" else ""
        lab = (
            f'<text class="el" x="{mid[0]:.1f}" y="{mid[1] - 5:.1f}">{html.escape(label)}</text>' if label else ""
        )
        return f'<g class="ed {cls}{ctx}" data-a="{html.escape(a)}" data-b="{html.escape(b)}"><path d="{d}" marker-end="url(#{marker})"/>{lab}</g>'

    for e in graph["edges"]:
        if e["type"] == "uses":
            parts.append(edge(e, "use", "ar"))
        else:
            parts.append(edge(e, "call", "ar"))
    for e in notes["inferred_edges"]:
        parts.append(edge(e, "inf", "ari", e["type"]))
    if notes.get("fundamental"):
        fid = "f:" + notes["fundamental"]["id"]
        for c in graph["concepts"]:
            if c["fundamental"] == notes["fundamental"]["id"]:
                parts.append(edge({"from": c["id"], "to": fid}, "fund", "ar"))

    watched = {w["node"] for w in notes["watch"]}
    for n in graph["nodes"]:
        sub = n["kind"].replace("_", " ")
        sub = f"hub · {n['status']}" if n["hub"] else f"{sub} · {n['status']}"
        cls = {"new": "fn-new", "modified": "fn-mod", "moved": "fn-mov", "context": "fn-ctx ctx"}[n["status"]]
        if n["hub"]:
            cls += " hub"
        parts.append(_node_svg(n["id"], pos[n["id"]], n["label"], sub, cls, n["id"] in watched))
    if "more" in pos:
        k = len(graph["summary"]["hidden_changed"])
        parts.append(_node_svg("more", pos["more"], f"+{k} more", "changed, not shown", "fn-more"))
    for c in graph["concepts"]:
        cls = "co" + (" co-new" if c["new_to_you"] else "")
        parts.append(_node_svg(c["id"], pos[c["id"]], c["label"], "", cls))
    if notes.get("fundamental"):
        fid = notes["fundamental"]["id"]
        parts.append(_node_svg("f:" + fid, pos["f:" + fid], notes["fundamental"]["label"], "underneath", "fu"))
    parts.append("</svg>")
    return "".join(parts)


# ------------------------------------------------------------------ card ---


def counts(s: dict) -> list[str]:
    """`2 new · 1 modified · 30 moved · 1 removed · 3 tests`, zeros left out (but never empty)."""
    out = [f"{s['new']} new"] if s["new"] or not (s["modified"] or s.get("moved")) else []
    if s["modified"]:
        out.append(f"{s['modified']} modified")
    if s.get("moved"):
        out.append(f"{s['moved']} moved")
    if s["removed"]:
        out.append(f"{len(s['removed'])} removed")
    if s.get("tests"):
        out.append(f"{s['tests']} test{'s' if s['tests'] > 1 else ''}")
    return out


def card(graph: dict, notes: dict, html_path: str) -> str:
    s = graph["summary"]
    nodes = graph["nodes"]
    by_id = {n["id"]: n for n in nodes}
    new_concepts = [c["label"] for c in graph["concepts"] if c["new_to_you"]]
    head = ["underneath"]
    head += counts(s)
    if new_concepts:
        head.append(f"{len(new_concepts)} new concept{'s' if len(new_concepts) > 1 else ''}")
    if notes["watch"]:
        head.append(f"{len(notes['watch'])} to watch")
    lines = [" · ".join(head)]

    hub = next((n for n in nodes if n["hub"]), None)
    if hub:
        order = {n["id"]: i for i, n in enumerate(nodes)}
        targets = sorted({e["to"] for e in graph["edges"] if e["from"] == hub["id"] and e["to"] in by_id}, key=order.get)
        outs = [by_id[t]["label"] for t in targets][:3]
        ins = [by_id[e["from"]]["label"] for e in graph["edges"] if e["to"] == hub["id"] and e["from"] in by_id][:1]
        chain = (f"{ins[0]} → " if ins else "") + hub["label"] + (f" → {', '.join(outs)}" if outs else "")
        lines.append(f"  hub   {chain}")
    else:
        top = [n["label"] for n in nodes if n["status"] != "context"][:3]
        if top:
            lines.append(f"  top   {', '.join(top)}")

    fund = notes.get("fundamental")
    tail = f"   ↓ {fund['label'].lower()}" if fund else ""
    if new_concepts:
        lines.append(f"  new   {', '.join(new_concepts[:3])}{tail}")
    elif graph["concepts"]:
        lines.append(f"  uses  {', '.join(c['label'] for c in graph['concepts'][:3])}{tail}")
    if notes["watch"]:
        w = notes["watch"][0]
        lines.append(f"  ⚠     {w['file']}:{w['line']}  {w['text']}")
    lines.append(f"  map   {html_path}")
    return "\n".join(lines[:5])


# ------------------------------------------------------------------ html ---

CSS = """
:root{--bg:#fff;--fg:#1f1e1c;--mut:#6b6a65;--line:#d9d7cf;--panel:#f6f5f1;
--pn-f:#EEEDFE;--pn-s:#534AB7;--pn-t:#3C3489;--ct-f:#F1EFE8;--ct-s:#B4B2A9;--ct-t:#444441;
--co-f:#E1F5EE;--co-s:#1D9E75;--co-t:#085041;--wa:#BA7517;--wa-bg:#FAEEDA;--edge:#9a988f;--inf:#7F77DD}
@media (prefers-color-scheme:dark){:root{--bg:#1c1c1a;--fg:#ecebe6;--mut:#a3a19a;--line:#3a3935;--panel:#262624;
--pn-f:#3C3489;--pn-s:#AFA9EC;--pn-t:#EEEDFE;--ct-f:#2C2C2A;--ct-s:#5F5E5A;--ct-t:#D3D1C7;
--co-f:#085041;--co-s:#5DCAA5;--co-t:#E1F5EE;--wa:#EF9F27;--wa-bg:#412402;--edge:#6f6d66;--inf:#AFA9EC}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:1100px;margin:0 auto;padding:20px 20px 40px}
header{display:flex;flex-wrap:wrap;gap:8px;align-items:center;margin-bottom:14px}
h1{font-size:16px;font-weight:600;margin:0 10px 0 0}
.chip{font-size:13px;padding:3px 10px;border-radius:6px;background:var(--panel);color:var(--mut)}
.chip.n{background:var(--pn-f);color:var(--pn-t)}.chip.c{background:var(--co-f);color:var(--co-t)}.chip.w{background:var(--wa-bg);color:var(--wa)}
header .sp{flex:1}button{font:inherit;font-size:13px;background:transparent;color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:4px 10px;cursor:pointer}
.wrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px;padding:8px}
svg{display:block;max-width:100%;height:auto;margin:0 auto}
.nd{cursor:pointer}.nd rect{stroke-width:1}.nd .t{font-size:13px;font-weight:600;text-anchor:middle;font-family:ui-monospace,SFMono-Regular,Menlo,monospace}.nd .s{font-size:11px;text-anchor:middle}
.fn-new rect,.fn-mod rect{fill:var(--pn-f);stroke:var(--pn-s)}.fn-new text,.fn-mod text{fill:var(--pn-t)}.fn-mod rect{stroke-dasharray:5 3}
.fn-mov rect{fill:var(--pn-f);stroke:var(--pn-s);stroke-dasharray:1 3;opacity:.7}.fn-mov text{fill:var(--pn-t)}
.fn-ctx rect,.fn-more rect{fill:var(--ct-f);stroke:var(--ct-s)}.fn-ctx text,.fn-more text{fill:var(--ct-t)}.fn-more rect{stroke-dasharray:3 3}
.hub>rect{stroke-width:2.5}.bdg circle{fill:var(--wa)}.bdg text{fill:#fff;font-size:11px;font-weight:700;text-anchor:middle}
.co>rect{fill:var(--co-f);stroke:var(--co-s)}.co text{fill:var(--co-t)}.co-new>rect{stroke-width:2.5}
.fu rect{fill:transparent;stroke:var(--ct-s);stroke-dasharray:4 3}.fu text{fill:var(--fg)}
.nd.sel>rect{stroke-width:3}.nd:focus{outline:none}.nd:focus-visible>rect{stroke-width:3;stroke-dasharray:none}
.ed path{fill:none;stroke:var(--edge);stroke-width:1.2}.arh{fill:var(--edge)}.arhi{fill:var(--inf)}
.ed.use path{stroke-width:.8;stroke-dasharray:2 3;opacity:.55}.ed.fund path{stroke-dasharray:4 3;opacity:.7}
.ed.inf path{stroke:var(--inf);stroke-dasharray:5 3;stroke-width:1.4}.el{font-size:11px;fill:var(--inf);text-anchor:middle}
.dim{opacity:.13;transition:opacity .15s}.ed.inf.dim{opacity:.4}.ed.hl path{opacity:1;stroke-width:1.6}.hidectx .ctx{opacity:.1}
.legend{font-size:12px;color:var(--mut);margin:8px 2px 14px}
#panel{background:var(--panel);border-radius:10px;padding:14px 18px}
#panel .h{display:flex;flex-wrap:wrap;gap:10px;align-items:baseline}#panel .h b{font-family:ui-monospace,Menlo,monospace;font-size:16px}
#panel .loc{font-size:12px;color:var(--mut);font-family:ui-monospace,Menlo,monospace}#panel .loc a{color:inherit}
#panel p{margin:8px 0}.wt{color:var(--wa)}.rel{font-size:13px;color:var(--mut)}
.lk{font-family:ui-monospace,Menlo,monospace;font-size:12.5px;cursor:pointer;text-decoration:underline dotted;color:var(--fg);background:none;border:0;padding:0}
pre{background:var(--bg);border:1px solid var(--line);border-radius:8px;padding:10px 12px;font-size:12.5px;overflow-x:auto}
ul{margin:6px 0;padding-left:20px}footer{font-size:12px;color:var(--mut);margin-top:14px}
"""

JS = r"""
const D=JSON.parse(document.getElementById('data').textContent);
const P=document.getElementById('panel');
const esc=s=>String(s??'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const lk=id=>`<button class="lk" data-go="${esc(id)}">${esc((D.items[id]||{}).label||id)}</button>`;
function show(id){
  const it=D.items[id]; if(!it) return;
  document.querySelectorAll('.nd').forEach(g=>g.classList.toggle('sel',g.dataset.id===id));
  document.querySelectorAll('.ed').forEach(e=>{const on=e.dataset.a===id||e.dataset.b===id;e.classList.toggle('dim',!on);e.classList.toggle('hl',on)});
  let h=`<div class="h"><b>${esc(it.label)}</b><span class="loc">${it.href?`<a href="${esc(it.href)}">${esc(it.loc)}</a>`:esc(it.loc)}</span></div>`;
  if(it.text) h+=`<p>${esc(it.text)}</p>`;
  (it.watch||[]).forEach(w=>h+=`<p class="wt">⚠ ${esc(w)}</p>`);
  if(it.pitfalls&&it.pitfalls.length) h+=`<div class="rel">Classic pitfalls</div><ul>${it.pitfalls.map(p=>`<li>${esc(p)}</li>`).join('')}</ul>`;
  const rel=[];
  if(it.calls&&it.calls.length) rel.push('Calls '+it.calls.map(lk).join(', '));
  if(it.callers&&it.callers.length) rel.push('Called by '+it.callers.map(lk).join(', '));
  if(it.concepts&&it.concepts.length) rel.push('Uses '+it.concepts.map(lk).join(', '));
  if(it.users&&it.users.length) rel.push('Used in '+it.users.map(lk).join(', '));
  if(it.fundamental) rel.push('Underneath '+lk(it.fundamental));
  if(it.tests) rel.push(esc(it.tests));
  if(it.list&&it.list.length) rel.push(it.list.map(esc).join(', '));
  if(rel.length) h+=`<p class="rel">${rel.join(' · ')}</p>`;
  if(it.example) h+=`<pre>${esc(it.example)}</pre>`;
  P.innerHTML=h;
  P.querySelectorAll('[data-go]').forEach(b=>b.addEventListener('click',()=>show(b.dataset.go)));
}
document.querySelectorAll('.nd').forEach(g=>{g.addEventListener('click',()=>show(g.dataset.id));
  g.addEventListener('keydown',e=>{if(e.key==='Enter')show(g.dataset.id)})});
const T=document.getElementById('toggle');
T.addEventListener('click',()=>{const on=document.body.classList.toggle('hidectx');T.textContent=on?'With context':'New only'});
show(D.start);
"""


def build_items(graph: dict, notes: dict, fundamentals: dict[str, Fundamental]) -> dict:
    root = graph["root"]
    by_id = {n["id"]: n for n in graph["nodes"]}
    calls = defaultdict(list)
    callers = defaultdict(list)
    for e in graph["edges"]:
        if e["type"] != "uses" and e["from"] in by_id and e["to"] in by_id:
            calls[e["from"]].append(e["to"])
            callers[e["to"]].append(e["from"])
    watch = defaultdict(list)
    for w in notes["watch"]:
        watch[w["node"]].append(f"{w['file']}:{w['line']}  {w['text']}")
    fund_id = notes["fundamental"]["id"] if notes.get("fundamental") else None
    items = {}
    for n in graph["nodes"]:
        summary = notes["nodes"].get(n["id"], {}).get("summary")
        items[n["id"]] = {
            "label": n["label"],
            "loc": f"{n['file']}:{n['line']} · {n['kind'].replace('_', ' ')} · {n['status']}"
            + (f" from {n['moved_from']}" if n.get("moved_from") else "")
            + (" · hub" if n["hub"] else ""),
            "href": f"vscode://file/{root}/{n['file']}:{n['line']}",
            "text": summary or n["signature"],
            "watch": watch.get(n["id"], []),
            "calls": calls[n["id"]],
            "callers": callers[n["id"]],
            "concepts": n["concepts"],
            "tests": (
                f"Tested by {len(n['tested_by'])} test(s): " + ", ".join(n["tested_by"][:4]) + ("…" if len(n["tested_by"]) > 4 else "")
                if n.get("tested_by")
                else ("No direct test call found." if n["status"] != "context" and not n.get("test") else "")
            ),
        }
    for c in graph["concepts"]:
        here = notes["concepts"].get(c["id"], {}).get("here")
        seen = "new to you" if c["new_to_you"] else f"seen {c['seen']} times"
        items[c["id"]] = {
            "label": c["label"],
            "loc": f"concept · {c['stack']} · {seen}",
            "text": here or c["what"],
            "pitfalls": c["pitfalls"][:2],
            "users": c["users"],
            "fundamental": ("f:" + c["fundamental"]) if c["fundamental"] == fund_id else None,
        }
    if fund_id:
        f = fundamentals[fund_id]
        items["f:" + fund_id] = {
            "label": f.label,
            "loc": "fundamental · /underneath deeper " + fund_id,
            "text": notes["fundamental"]["text"],
            "example": f.example,
            "users": [c["id"] for c in graph["concepts"] if c["fundamental"] == fund_id],
        }
    if graph["summary"]["hidden_changed"]:
        items["more"] = {
            "label": f"+{len(graph['summary']['hidden_changed'])} more",
            "loc": "changed, ranked lower, not drawn",
            "text": "Run with a higher limit in .underneath/config.json to draw them.",
            "list": graph["summary"]["hidden_changed"],
        }
    return items


def page(graph: dict, notes: dict, fundamentals: dict[str, Fundamental]) -> str:
    s = graph["summary"]
    lay = layout(graph, notes)
    items = build_items(graph, notes, fundamentals)
    hub = next((n["id"] for n in graph["nodes"] if n["hub"]), None)
    start = hub or next((n["id"] for n in graph["nodes"] if n["status"] != "context"), None) or next(iter(items), "")
    new_c = sum(1 for c in graph["concepts"] if c["new_to_you"])
    chips = []
    for i, c in enumerate(counts(s)):
        tip = f' title="{html.escape(", ".join(s["removed"]))}"' if c.endswith("removed") else ""
        chips.append(f'<span class="chip{" n" if i == 0 else ""}"{tip}>{html.escape(c)}</span>')
    if new_c:
        chips.append(f'<span class="chip c">{new_c} new concept{"s" if new_c > 1 else ""}</span>')
    if notes["watch"]:
        chips.append(f'<span class="chip w">{len(notes["watch"])} to watch</span>')
    data = json.dumps({"items": items, "start": start}).replace("</", "<\\/")
    more = (
        f" Other concepts in this change: {html.escape(', '.join(s['more_concepts']))}." if s["more_concepts"] else ""
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>underneath · {html.escape(Path(graph['root']).name)}</title><style>{CSS}</style></head>
<body><main>
<header><h1>underneath</h1>{''.join(chips)}<span class="sp"></span><button id="toggle">New only</button></header>
<div class="wrap">{svg(graph, notes, lay)}</div>
<div class="legend">Solid line: read from the code. Purple dashed: inferred by the agent. Purple: changed function (dashed border = modified, dotted = moved). Teal: concept (thick border = new to you). Gray: context. Amber dot: something to watch.{more}</div>
<section id="panel" aria-live="polite"></section>
<footer>{html.escape(graph['root'])} · compared with {html.escape(graph['base'])} · {len(s['files'])} file(s), +{s['added_lines']} lines · {date.today().isoformat()}</footer>
</main>
<script type="application/json" id="data">{data}</script>
<script>{JS}</script>
</body></html>"""


# -------------------------------------------------------------- registry ---


def update_registry(registry: dict, graph: dict, graph_id: str) -> dict:
    if registry.get("last_graph") == graph_id:
        return registry
    today = date.today().isoformat()
    concepts = registry.setdefault("concepts", {})
    for c in graph["concepts"]:
        entry = concepts.setdefault(c["id"], {"seen": 0, "first_seen": today})
        entry["seen"] += 1
        entry["last_seen"] = today
    registry["last_graph"] = graph_id
    return registry
