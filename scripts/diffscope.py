"""Find what changed: from git, or from two folders (used by the examples and tests)."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path

from parse import LANG_BY_EXT, language_for

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", ".next", "out", "coverage", ".venv", "venv",
    "env", "__pycache__", ".mypy_cache", ".pytest_cache", ".underneath", "vendor", "site-packages",
}
MAX_FILES = 3000
MAX_BYTES = 300_000


@dataclass
class Scope:
    root: Path
    base_label: str
    old: dict[str, str] = field(default_factory=dict)      # changed files, previous content
    new: dict[str, str] = field(default_factory=dict)      # changed files, current content
    deleted: list[str] = field(default_factory=list)
    universe: dict[str, str] = field(default_factory=dict)  # every supported file, current content
    truncated: bool = False
    git_root: Path | None = None  # set when the universe is a git working tree: scans use git grep

    def scan(self, pattern: str) -> dict[str, list[str]]:
        """Every match of a Perl-style regex, by universe file. Matches never span lines.

        In a git working tree this runs `git grep -P` (C, multithreaded), which
        is 10 to 50 times faster than a Python scan of a large repository.
        """
        if self.git_root is not None:
            hits = _git_grep(self.git_root, pattern)
            if hits is not None:
                return {f: m for f, m in hits.items() if f in self.universe}
        rx = re.compile(pattern, re.MULTILINE)
        out = {}
        for rel, text in self.universe.items():
            found = [m.group(0) for m in rx.finditer(text)]
            if found:
                out[rel] = found
        return out

    @property
    def changed(self) -> list[str]:
        return sorted(set(self.new) | set(self.deleted))


def _skip(rel: str) -> bool:
    parts = Path(rel).parts
    if any(p in SKIP_DIRS for p in parts):
        return True
    name = parts[-1]
    return name.endswith((".min.js", ".d.ts", ".map")) or language_for(rel) is None


def _read(path: Path) -> str | None:
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf8", errors="replace")
    except OSError:
        return None


def _git(root: Path, *args: str, check=True) -> str:
    res = subprocess.run(["git", *args], cwd=root, capture_output=True, text=True)
    if check and res.returncode != 0:
        raise RuntimeError(res.stderr.strip() or f"git {' '.join(args)} failed")
    return res.stdout


_GREP_SPECS = [f"*{ext}" for ext in LANG_BY_EXT]
_grep_ok: dict[Path, bool] = {}


def _git_grep(root: Path, pattern: str) -> dict[str, list[str]] | None:
    """`git grep -P -o` over tracked and untracked files. None if this git cannot do it."""
    if _grep_ok.get(root) is False:
        return None
    res = subprocess.run(
        ["git", "grep", "--untracked", "-I", "-P", "-o", "--null", "-e", pattern, "--", *_GREP_SPECS],
        cwd=root, capture_output=True, text=True, errors="replace",
    )
    if res.returncode not in (0, 1):  # 1 = no match; anything else = no PCRE support or a bad pattern
        _grep_ok[root] = False
        return None
    _grep_ok[root] = True
    out: dict[str, list[str]] = {}
    for line in res.stdout.splitlines():
        rel, _, match = line.partition("\0")
        out.setdefault(rel, []).append(match)
    return out


def from_git(cwd: Path, base: str = "HEAD") -> Scope:
    root = Path(_git(cwd, "rev-parse", "--show-toplevel").strip())
    has_head = subprocess.run(["git", "rev-parse", "--verify", "-q", base], cwd=root, capture_output=True).returncode == 0
    scope = Scope(root=root, base_label=base if has_head else "(empty repository)", git_root=root)

    statuses: dict[str, str] = {}
    if has_head:
        for line in _git(root, "diff", "--name-status", "-M", base).splitlines():
            bits = line.split("\t")
            code = bits[0][:1]
            if code == "R":
                statuses[bits[1]] = "D"
                statuses[bits[2]] = "A"
            else:
                statuses[bits[-1]] = code
    else:
        for rel in _git(root, "ls-files").splitlines():
            statuses[rel] = "A"
    for rel in _git(root, "ls-files", "--others", "--exclude-standard").splitlines():
        statuses[rel] = "A"

    for rel, code in statuses.items():
        if _skip(rel):
            continue
        if code == "D":
            scope.deleted.append(rel)
            old = _git(root, "show", f"{base}:{rel}", check=False)
            scope.old[rel] = old
            continue
        text = _read(root / rel)
        if text is None:
            continue
        scope.new[rel] = text
        if code != "A" and has_head:
            scope.old[rel] = _git(root, "show", f"{base}:{rel}", check=False)

    tracked = _git(root, "ls-files").splitlines() + list(scope.new)
    for rel in tracked:
        if rel in scope.universe or _skip(rel) or rel in scope.deleted:
            continue
        if len(scope.universe) >= MAX_FILES:
            scope.truncated = True
            break
        text = scope.new.get(rel) or _read(root / rel)
        if text is not None:
            scope.universe[rel] = text
    return scope


def _tree(folder: Path) -> dict[str, str]:
    out = {}
    for dirpath, dirnames, filenames in os.walk(folder):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for fn in filenames:
            p = Path(dirpath) / fn
            rel = p.relative_to(folder).as_posix()
            if _skip(rel):
                continue
            text = _read(p)
            if text is not None:
                out[rel] = text
    return out


def from_dirs(before: Path, after: Path) -> Scope:
    old_tree, new_tree = _tree(before), _tree(after)
    scope = Scope(root=after.resolve(), base_label=str(before))
    for rel, text in new_tree.items():
        if old_tree.get(rel) != text:
            scope.new[rel] = text
            if rel in old_tree:
                scope.old[rel] = old_tree[rel]
    for rel, text in old_tree.items():
        if rel not in new_tree:
            scope.deleted.append(rel)
            scope.old[rel] = text
    scope.universe = new_tree
    return scope
