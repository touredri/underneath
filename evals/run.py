#!/usr/bin/env python3
"""Evaluate what underneath extracts from a diff against what a human expects.

Each case is a folder in evals/cases/ with an `expected.json`, and either its
own `before/` and `after/` folders or a `"source"` pointing at an example.

    {
      "about": "one line: what the case checks",
      "source": "examples/react-search",          # optional
      "concepts": {"expected": [...], "allowed": [...]},
      "edges": {"expected": [["from", "to", "calls"], ...], "forbidden": [[...]], "complete": true},
      "status": {"Label": "moved"},               # optional
      "context": {"expected": [...], "forbidden": [...]}   # optional: unchanged functions drawn
    }

Concepts are every concept detected on the drawn changed functions (the five
shown plus "also present"). A detected concept that is neither expected nor
allowed is *invented*: the goal is zero. Recall is expected concepts found.
Edges: recall on `expected`; any `forbidden` edge, or, with `complete`, any
edge between two changed functions that is not expected, is a *false link*.

    python3 evals/run.py            # table, exit 1 if a threshold is missed
    python3 evals/run.py --json     # machine-readable
    python3 evals/run.py --show X   # what the tool sees for case X (to write expected.json)
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from concepts import load_concepts  # noqa: E402
from diffscope import from_dirs  # noqa: E402
from graph import build  # noqa: E402

CASES = Path(__file__).resolve().parent / "cases"
THRESHOLDS = Path(__file__).resolve().parent / "thresholds.json"


def _folders(case: Path, spec: dict) -> tuple[Path, Path]:
    base = ROOT / spec["source"] if spec.get("source") else case
    return base / "before", base / "after"


def _graph(case: Path, spec: dict, catalogue) -> dict:
    before, after = _folders(case, spec)
    return build(from_dirs(before, after), catalogue, {})


def evaluate(case: Path, catalogue) -> dict:
    spec = json.loads((case / "expected.json").read_text(encoding="utf8"))
    g = _graph(case, spec, catalogue)
    label = {n["id"]: n["label"] for n in g["nodes"]}
    changed = {n["label"] for n in g["nodes"] if n["status"] != "context"}

    found = {c["id"] for c in g["concepts"]} | set(g["summary"].get("more_concept_ids", []))
    want = set(spec.get("concepts", {}).get("expected", []))
    ok = want | set(spec.get("concepts", {}).get("allowed", []))

    edges = {(label[e["from"]], label[e["to"]], e["type"]) for e in g["edges"] if e["type"] != "uses"}
    es = spec.get("edges", {})
    exp_edges = {tuple(e) for e in es.get("expected", [])}
    false_links = {tuple(e) for e in es.get("forbidden", [])} & edges
    if es.get("complete"):
        false_links |= {e for e in edges if e[0] in changed and e[1] in changed and e not in exp_edges}
    status = {n["label"]: n["status"] for n in g["nodes"]}
    ctx = {n["label"] for n in g["nodes"] if n["status"] == "context"}
    cs = spec.get("context", {})
    wrong_context = sorted(
        [f"missing context {c}" for c in cs.get("expected", []) if c not in ctx]
        + [f"unwanted context {c}" for c in cs.get("forbidden", []) if c in ctx]
    )
    return {
        "case": case.name,
        "about": spec.get("about", ""),
        "concepts_found": len(found),
        "concepts_expected": len(want),
        "invented": sorted(found - ok),
        "missed": sorted(want - found),
        "edges_expected": len(exp_edges),
        "edges_found": len(exp_edges & edges),
        "missing_edges": sorted(map(list, exp_edges - edges)),
        "false_links": sorted(map(list, false_links)),
        "wrong_status": sorted(f"{k}: {status.get(k)} (want {v})" for k, v in spec.get("status", {}).items() if status.get(k) != v),
        "wrong_context": wrong_context,
    }


def show(case: Path, catalogue) -> None:
    spec = json.loads((case / "expected.json").read_text()) if (case / "expected.json").exists() else {}
    g = _graph(case, spec, catalogue)
    label = {n["id"]: n["label"] for n in g["nodes"]}
    print("nodes:", [(n["label"], n["status"]) for n in g["nodes"]])
    print("concepts:", sorted({c["id"] for c in g["concepts"]} | set(g["summary"]["more_concept_ids"])))
    print("edges:", sorted((label[e["from"]], label[e["to"]], e["type"]) for e in g["edges"] if e["type"] != "uses"))


def summarize(results: list[dict]) -> dict:
    found = sum(r["concepts_found"] for r in results)
    invented = sum(len(r["invented"]) for r in results)
    want = sum(r["concepts_expected"] for r in results)
    missed = sum(len(r["missed"]) for r in results)
    e_want = sum(r["edges_expected"] for r in results)
    e_found = sum(r["edges_found"] for r in results)
    return {
        "cases": len(results),
        "concept_precision": round((found - invented) / found, 3) if found else 1.0,
        "invented_concepts": invented,
        "concept_recall": round((want - missed) / want, 3) if want else 1.0,
        "edge_recall": round(e_found / e_want, 3) if e_want else 1.0,
        "false_links": sum(len(r["false_links"]) for r in results),
        "wrong_status": sum(len(r["wrong_status"]) for r in results),
        "wrong_context": sum(len(r["wrong_context"]) for r in results),
    }


def check(total: dict, limits: dict) -> list[str]:
    """`{"concept_recall_min": 0.9, "invented_concepts_max": 0}` -> the limits that are missed."""
    fails = []
    for key, bound in limits.items():
        name, _, kind = key.rpartition("_")
        value = total.get(name)
        if value is None or kind not in ("min", "max"):
            continue
        if (kind == "min" and value < bound) or (kind == "max" and value > bound):
            fails.append(f"{name} is {value}, limit {kind} {bound}")
    return fails


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--json", action="store_true", help="print the full results as JSON")
    p.add_argument("--show", metavar="CASE", help="print what the tool sees for one case")
    a = p.parse_args(argv)
    catalogue = load_concepts(ROOT / "references")
    if a.show:
        show(CASES / a.show, catalogue)
        return 0
    results = [evaluate(c, catalogue) for c in sorted(CASES.iterdir()) if (c / "expected.json").exists()]
    total = summarize(results)
    fails = check(total, json.loads(THRESHOLDS.read_text()) if THRESHOLDS.exists() else {})
    if a.json:
        print(json.dumps({"total": total, "fails": fails, "cases": results}, indent=1))
        return 1 if fails else 0
    w = max(len(r["case"]) for r in results)
    print(f"{'case':<{w}}  concepts  invented  missed  edges  false links")
    for r in results:
        print(
            f"{r['case']:<{w}}  {r['concepts_found']:>8}  {len(r['invented']):>8}  {len(r['missed']):>6}  "
            f"{r['edges_found']:>2}/{r['edges_expected']:<2}  {len(r['false_links']):>11}"
        )
        for key in ("invented", "missed", "missing_edges", "false_links", "wrong_status", "wrong_context"):
            if r[key]:
                print(f"{'':<{w}}    {key.replace('_', ' ')}: {r[key]}")
    print(
        f"\nprecision {total['concept_precision']:.1%} ({total['invented_concepts']} invented) · "
        f"recall {total['concept_recall']:.1%} · edge recall {total['edge_recall']:.1%} · "
        f"{total['false_links']} false link(s) · {total['wrong_status']} wrong status · {total['wrong_context']} wrong context · {total['cases']} cases"
    )
    for f in fails:
        print(f"FAIL {f}")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
