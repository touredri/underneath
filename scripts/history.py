"""`.underneath/history.jsonl` (one line per rendered card) and `underneath log`.

Local, like the registry: it never leaves the machine and `.underneath/`
ignores itself in git. A card rendered again for the same change replaces
its line instead of adding one.
"""

from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

from concepts import Concept
from ids import change_id

KEEP = 500
MONTHS = "Jan Feb Mar Apr May Jun Jul Aug Sep Oct Nov Dec".split()


def entry(graph: dict, notes: dict, card_text: str, now: datetime | None = None) -> dict:
    s = graph["summary"]
    return {
        "at": (now or datetime.now()).isoformat(timespec="seconds"),
        "change": change_id(graph),
        "base": graph.get("base", ""),
        "counts": {k: (len(s[k]) if isinstance(s.get(k), list) else s.get(k, 0)) for k in ("new", "modified", "moved", "removed", "tests")},
        "concepts": [c["id"] for c in graph["concepts"]],
        "new_concepts": [c["id"] for c in graph["concepts"] if c.get("new_to_you")],
        "risks": [c["id"] for c in graph["concepts"] if c.get("risk")],
        "watch": [w["text"] for w in notes.get("watch", [])],
        "hub": next((n["label"] for n in graph["nodes"] if n.get("hub")), ""),
        "card": card_text,
    }


def append(path: Path, item: dict) -> None:
    lines = load(path)
    if lines and lines[-1].get("change") == item["change"]:
        lines[-1] = item  # the same change rendered again
    else:
        lines.append(item)
    path.write_text("".join(json.dumps(x, ensure_ascii=False) + "\n" for x in lines[-KEEP:]), encoding="utf8")


def load(path: Path) -> list[dict]:
    out = []
    try:
        for line in path.read_text(encoding="utf8").splitlines():
            try:
                out.append(json.loads(line))
            except ValueError:
                continue
    except OSError:
        pass
    return out


def _day(iso: str) -> str:
    d = datetime.fromisoformat(iso)
    return f"{MONTHS[d.month - 1]} {d.day}"


def _name(cid: str, catalogue: dict[str, Concept]) -> str:
    return catalogue[cid].label if cid in catalogue else cid


def log_card(items: list[dict], catalogue: dict[str, Concept], registry: dict, days: int, now: datetime | None = None) -> str:
    """At most 5 lines on the cards of the last `days` days, compared with the `days` before."""
    now = now or datetime.now()
    since, before = now - timedelta(days=days), now - timedelta(days=2 * days)
    recent = [x for x in items if datetime.fromisoformat(x["at"]) >= since]
    earlier = [x for x in items if before <= datetime.fromisoformat(x["at"]) < since]
    period = "today" if days <= 1 else f"in the last {days} days"
    entries = registry.get("concepts", {})
    known_now = [
        cid for cid, e in entries.items()
        if e.get("known") and e.get("known_at") and datetime.fromisoformat(e["known_at"]) >= since.replace(hour=0, minute=0, second=0, microsecond=0)
    ]
    if not recent and not known_now:
        return f"underneath log · no card {period}"
    seen = Counter(c for x in recent for c in x.get("concepts", []))
    new = list(dict.fromkeys(c for x in recent for c in x.get("new_concepts", [])))
    new_before = len(set(c for x in earlier for c in x.get("new_concepts", [])))
    minor = {cid for cid, c in catalogue.items() if c.minor}
    known = {cid for cid, e in entries.items() if e.get("known")}
    ranked = sorted(seen, key=lambda c: (c in minor, -seen[c], c))

    n = len(recent)
    head = f"underneath log · {n} change{'s' if n != 1 else ''} {period} · {len(seen)} concept{'s' if len(seen) != 1 else ''}"
    if new or earlier:
        head += f", {len(new)} new" + (f" ({new_before} the {days} days before)" if earlier else "")
    lines = {"head": head}
    if ranked:
        lines["most"] = "  most  " + " · ".join(f"{_name(c, catalogue)} ×{seen[c]}" for c in ranked[:3])
    if new:
        lines["new"] = "  new   " + ", ".join(_name(c, catalogue) for c in new[:3]) + (f" (+{len(new) - 3})" if len(new) > 3 else "")
    if known_now:
        names = sorted(known_now, key=lambda c: entries[c]["known_at"])
        lines["known"] = "  known " + ", ".join(f"{_name(c, catalogue)} ({_day(entries[c]['known_at'])})" for c in names[:3]) + (f" (+{len(names) - 3})" if len(names) > 3 else "")
    risky = [(x["at"], c) for x in recent for c in x.get("risks", [])]
    if risky:
        shown = ", ".join(f"{_name(c, catalogue)} ({_day(at)})" for at, c in risky[:2])
        lines["risk"] = f"  ⚠     {len(risky)} likely bug{'s' if len(risky) > 1 else ''} flagged: {shown}" + (" …" if len(risky) > 2 else "")
    todo = [c for c in ranked if c not in known and c not in minor and seen[c] > 1]
    if todo:
        c = todo[0]
        lines["next"] = f"  next  {_name(c, catalogue)} came back {seen[c]} times, never marked known: /underneath deeper {c}"
    # Five lines: what changed for the developer first; the most frequent concepts last.
    keep = [k for k in ("head", "risk", "new", "known", "next", "most") if k in lines][:5]
    return "\n".join(lines[k] for k in ("head", "most", "new", "known", "risk", "next") if k in keep)
