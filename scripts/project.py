"""The whole project's concept skeleton, for `underneath map` and `underneath gaps`.

Every supported file is parsed once; the concepts found in each file are
cached by content hash in `.underneath/cache/concepts.json`, so later runs
only parse what changed. Test files are counted but their concepts are not:
the skeleton describes the code the project ships.
"""

from __future__ import annotations

import hashlib
import json
import os
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from datetime import date
from pathlib import Path

from concepts import Concept, detect, load_concepts
from diffscope import Scope
from graph import is_test
from parse import parse_file

CACHE_SCHEMA = 1
PARALLEL_FROM = 150  # below this many files to parse, a process pool costs more than it saves
TOP_FILES = 5
RISK_PLACES = 5


def _catalogue_key(ref_dir: Path) -> str:
    """Changes when a stack file or the parser changes, so cached detections never outlive their rules."""
    h = hashlib.sha1(str(CACHE_SCHEMA).encode())
    for md in sorted((ref_dir / "stacks").glob("*.md")):
        h.update(md.name.encode())
        h.update(md.read_bytes())
    for py in ("parse.py", "concepts.py"):
        h.update((Path(__file__).parent / py).read_bytes())
    return h.hexdigest()[:16]


def file_concepts(rel: str, text: str, catalogue: dict[str, Concept]) -> dict:
    """Functions in one file and, for each concept, how many use it and the first line."""
    syms = parse_file(rel, text)
    counts: Counter = Counter()
    first: dict[str, int] = {}
    for s in syms:
        for cid in detect(s, catalogue):
            counts[cid] += 1
            first.setdefault(cid, s.start_line)
    return {"functions": sum(1 for s in syms if s.kind != "class"), "concepts": dict(counts), "first": first}


_worker_catalogue: dict[str, Concept] | None = None


def _init_worker(ref_dir: str) -> None:
    global _worker_catalogue
    _worker_catalogue = load_concepts(Path(ref_dir))


def _work(batch: list[tuple[str, str]]) -> list[tuple[str, dict]]:
    return [(rel, file_concepts(rel, text, _worker_catalogue)) for rel, text in batch]


def _analyse(todo: list[tuple[str, str]], catalogue: dict[str, Concept], ref_dir: Path) -> dict[str, dict]:
    if len(todo) < PARALLEL_FROM:
        return {rel: file_concepts(rel, text, catalogue) for rel, text in todo}
    workers = max(1, min(os.cpu_count() or 1, 8))
    size = max(16, len(todo) // (workers * 4))
    batches = [todo[i : i + size] for i in range(0, len(todo), size)]
    out: dict[str, dict] = {}
    try:
        with ProcessPoolExecutor(max_workers=workers, initializer=_init_worker, initargs=(str(ref_dir),)) as pool:
            for part in pool.map(_work, batches):
                out.update(part)
    except (OSError, RuntimeError):  # no process pool here (sandbox, frozen interpreter): do it inline
        out = {rel: file_concepts(rel, text, catalogue) for rel, text in todo}
    return out


def scan(scope: Scope, catalogue: dict[str, Concept], ref_dir: Path, cache_dir: Path | None) -> dict:
    """Aggregate concept counts over the project. Reuses and refreshes the cache."""
    key = _catalogue_key(ref_dir)
    cache_path = cache_dir / "concepts.json" if cache_dir else None
    cache: dict = {}
    if cache_path and cache_path.exists():
        try:
            cache = json.loads(cache_path.read_text(encoding="utf8"))
        except (OSError, json.JSONDecodeError):
            cache = {}
    entries = cache.get("files", {}) if cache.get("key") == key else {}

    shas = {rel: hashlib.sha1(text.encode("utf8", "replace")).hexdigest() for rel, text in scope.universe.items()}
    sources = [rel for rel in sorted(scope.universe) if not is_test(rel)]
    todo = [(rel, scope.universe[rel]) for rel in sources if entries.get(rel, {}).get("sha") != shas[rel]]
    fresh = _analyse(todo, catalogue, ref_dir)
    files = {rel: entries[rel] for rel in sources if rel not in fresh}
    for rel, info in fresh.items():
        files[rel] = {"sha": shas[rel], **info}
    if cache_path:
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_text(json.dumps({"key": key, "files": files}, separators=(",", ":")), encoding="utf8")

    per_concept: dict[str, Counter] = defaultdict(Counter)
    places: dict[str, list[str]] = defaultdict(list)
    for rel in sorted(files):
        info = files[rel]
        for cid, n in info["concepts"].items():
            if cid not in catalogue:
                continue
            per_concept[cid][rel] += n
            places[cid].append(f"{rel}:{info['first'].get(cid, 1)}")
    concepts = {}
    for cid, by_file in per_concept.items():
        top = sorted(by_file.items(), key=lambda p: (-p[1], p[0]))
        concepts[cid] = {
            "count": sum(by_file.values()),
            "files": len(by_file),
            "top_files": [[rel, n] for rel, n in top[:TOP_FILES]],
            "places": places[cid][:RISK_PLACES] if catalogue[cid].risk else [],
        }
    return {
        "schema": 1,
        "root": str(scope.root),
        "generated": date.today().isoformat(),
        "files": len(sources),
        "test_files": len(scope.universe) - len(sources),
        "functions": sum(f["functions"] for f in files.values()),
        "parsed": len(todo),
        "truncated": scope.truncated,
        "concepts": concepts,
    }


def by_fundamental(data: dict, catalogue: dict[str, Concept]) -> list[dict]:
    """[{id, count, concepts: [cid, ...]}], biggest first; inside, likely bugs first and minor basics last."""
    groups: dict[str, list[str]] = defaultdict(list)
    for cid in data["concepts"]:
        groups[catalogue[cid].fundamental or "other"].append(cid)
    out = []
    for fid, cids in groups.items():
        # Likely bugs first, `minor` basics last, the rest by use count.
        cids.sort(key=lambda c: (not catalogue[c].risk, catalogue[c].minor, -data["concepts"][c]["count"], c))
        out.append({"id": fid, "count": sum(data["concepts"][c]["count"] for c in cids), "concepts": cids})
    out.sort(key=lambda g: (-g["count"], g["id"]))
    return out


def gaps(data: dict, registry: dict, catalogue: dict[str, Concept] | None = None) -> list[str]:
    """Concepts present in the code and never marked known, most used first; `minor` basics after the rest."""
    known = {cid for cid, e in registry.get("concepts", {}).items() if e.get("known")}
    minor = {cid for cid, c in (catalogue or {}).items() if c.minor}
    return sorted((c for c in data["concepts"] if c not in known), key=lambda c: (c in minor, -data["concepts"][c]["count"], c))
