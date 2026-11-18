#!/usr/bin/env python3
"""Turn one commit of a git repository into an eval case.

    python3 evals/tools/import_case.py REPO_DIR COMMIT NAME

Copies into evals/cases/NAME/ the supported files the commit changed, plus the
files they import and a few files that import them (so calls and callers can
be resolved), at the parent commit (before/) and at the commit (after/).
Writes SOURCE.md (repository, commit, license) and an expected.json skeleton.

The skeleton is empty on purpose: expectations are written by a human reading
the diff, never copied from what underneath outputs. Run
`python3 evals/run.py --show NAME` only afterwards, to see the disagreements.

Nothing from the repository is executed: files are only read.
"""

from __future__ import annotations

import json
import re
import subprocess
import sys
from pathlib import Path, PurePosixPath

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from diffscope import _skip  # noqa: E402
from graph import _imports, _suffix_index  # noqa: E402

MAX_IMPORTERS = 6
# Key-shaped strings are redacted on import, even public test keys: a case must never republish one.
SECRET = re.compile(
    r"\b((?:sk|pk|rk)_(?:test|live)_)[A-Za-z0-9]{10,}|\bAKIA[0-9A-Z]{16}\b|\bgh[pousr]_[A-Za-z0-9]{30,}\b"
    r"|\bxox[baprs]-[A-Za-z0-9-]{10,}|\bAIza[0-9A-Za-z_-]{30,}|-----BEGIN [A-Z ]*PRIVATE KEY-----[\s\S]*?-----END [A-Z ]*PRIVATE KEY-----"
)
MAX_FILE = 150_000


def git(repo: Path, *args: str) -> str:
    return subprocess.run(["git", *args], cwd=repo, capture_output=True, text=True, check=True).stdout


def show(repo: Path, rev: str, path: str) -> str | None:
    r = subprocess.run(["git", "show", f"{rev}:{path}"], cwd=repo, capture_output=True, text=True, errors="replace")
    return r.stdout if r.returncode == 0 and len(r.stdout) <= MAX_FILE else None


def main(argv: list[str]) -> int:
    if len(argv) != 3:
        print(__doc__)
        return 2
    repo, sha, name = Path(argv[0]).resolve(), argv[1], argv[2]
    parent = f"{sha}^"
    changed = [p for p in git(repo, "diff", "--name-only", parent, sha).splitlines() if not _skip(p)]
    if not changed:
        print("no supported file changed in this commit")
        return 1
    tree = [p for p in git(repo, "ls-tree", "-r", "--name-only", sha).splitlines() if not _skip(p)]
    files, suffixes = set(tree), _suffix_index(set(tree))

    keep = set(changed)
    for rev in (parent, sha):
        for rel in changed:
            text = show(repo, rev, rel)
            if text is not None:
                keep |= _imports(rel, text, files, suffixes)
    stems = {PurePosixPath(p).stem for p in changed}
    importers = []
    for rel in tree:
        if rel in keep or len(importers) >= MAX_IMPORTERS:
            continue
        text = show(repo, sha, rel)
        if text and any(s in text for s in stems) and set(changed) & _imports(rel, text, files, suffixes):
            importers.append(rel)
    keep |= set(importers)

    case = ROOT / "evals" / "cases" / name
    redacted = 0
    for side, rev in (("before", parent), ("after", sha)):
        for rel in sorted(keep):
            text = show(repo, rev, rel)
            if text is None:
                continue
            out = case / side / rel
            out.parent.mkdir(parents=True, exist_ok=True)
            text, hits = SECRET.subn(lambda m: (m.group(1) or "") + "REDACTED", text)
            redacted += hits
            out.write_text(text, encoding="utf8")

    url = git(repo, "remote", "get-url", "origin").strip()
    subject = git(repo, "log", "-1", "--format=%s", sha).strip()
    license_file = next((p for p in ("LICENSE", "LICENSE.md", "LICENSE.txt", "COPYING") if (repo / p).exists()), "")
    (case / "SOURCE.md").write_text(
        f"# Source\n\n- Repository: {url}\n- Commit: {sha}\n- Subject: {subject}\n"
        f"- License: see `{license_file or 'the repository'}` in {url} (copied in evals/third_party/).\n"
        f"- Files: the {len(changed)} changed file(s) and {len(keep) - len(changed)} neighbour(s), unmodified"
        + (f" except {redacted} key-shaped string(s) replaced by REDACTED" if redacted else "") + ".\n",
        encoding="utf8",
    )
    expected = case / "expected.json"
    if not expected.exists():
        expected.write_text(json.dumps({
            "about": f"{PurePosixPath(url).stem}: {subject}",
            "concepts": {"expected": [], "allowed": []},
            "edges": {"expected": []},
        }, indent=2) + "\n", encoding="utf8")
    print(f"{case}: {len(changed)} changed, {len(keep) - len(changed)} neighbours")
    for rel in changed:
        print(f"  changed  {rel}")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
