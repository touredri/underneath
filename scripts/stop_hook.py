#!/usr/bin/env python3
"""Claude Code `Stop` hook: ask the agent for the underneath card when it changed code.

Reads the hook input on stdin and prints nothing (let Claude stop) or
{"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": brief}},
so the agent writes notes.json, renders and shows the card before it finishes.

It stays quiet when:
- `stop_hook_active` is true (the agent is already continuing because of a Stop hook);
- `.underneath/config.json` has `"stop_hook": false`;
- the cwd is not a git repository;
- the transcript shows no file edit (Edit, Write, MultiEdit, NotebookEdit) since the last prompt;
- `extract` says the change is small or there is nothing to map;
- the card for this exact graph was already rendered, or already asked for.

Any failure is silent: a hook must never get in the way of the user.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from datetime import date
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

from ids import change_id  # noqa: E402 - no third-party import: the hook runs on any python3
CLI = HERE / "underneath.py"
EDIT_TOOLS = {"Edit", "Write", "MultiEdit", "NotebookEdit"}
QUIET = ("underneath: small change", "underneath: no supported changes")


def _load(path: Path, default):
    try:
        return json.loads(path.read_text(encoding="utf8"))
    except (OSError, ValueError):
        return default


def edited_this_turn(transcript: str | None) -> bool:
    """True if a file-editing tool ran after the last prompt. True when unsure."""
    if not transcript:
        return True
    try:
        lines = Path(transcript).read_text(encoding="utf8", errors="replace").splitlines()
    except OSError:
        return True
    edited = False
    for line in lines:
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        msg = entry.get("message") or {}
        content = msg.get("content")
        if entry.get("type") == "user" and not entry.get("isMeta"):
            items = content if isinstance(content, list) else [{"type": "text"}]
            is_prompt = any(isinstance(i, dict) and i.get("type") == "text" for i in items) and not any(
                isinstance(i, dict) and i.get("type") == "tool_result" for i in items
            )
            if is_prompt:
                edited = False  # a new prompt: start counting again
        elif entry.get("type") == "assistant" and isinstance(content, list):
            if any(isinstance(i, dict) and i.get("type") == "tool_use" and i.get("name") in EDIT_TOOLS for i in content):
                edited = True
    return edited


def _repo_root(cwd: Path) -> Path | None:
    try:
        r = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cwd, capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.TimeoutExpired):
        return None
    return Path(r.stdout.strip()) if r.returncode == 0 and r.stdout.strip() else None


def decide(hook_input: dict) -> dict | None:
    """The hook's JSON answer, or None to let Claude stop."""
    if hook_input.get("stop_hook_active"):
        return None
    cwd = Path(hook_input.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd())
    root = _repo_root(cwd)
    if root is None:
        return None
    out = root / ".underneath"
    if _load(out / "config.json", {}).get("stop_hook") is False:
        return None
    if not edited_this_turn(hook_input.get("transcript_path")):
        return None

    try:
        r = subprocess.run([sys.executable, str(CLI), "extract"], cwd=root, capture_output=True, text=True, timeout=120)
    except (OSError, subprocess.TimeoutExpired):
        return None
    if r.returncode != 0:
        return _missing_dependency(out) if "needs tree-sitter" in r.stderr + r.stdout else None
    brief = r.stdout.strip()
    if not brief or brief.startswith(QUIET):
        return None

    graph = _load(out / "graph.json", None)
    if not graph:
        return None
    gid = change_id(graph)
    state = _load(out / "hook.json", {})
    if gid in (_load(out / "registry.json", {}).get("last_change"), state.get("asked")):
        return None
    state["asked"] = gid
    try:
        (out / "hook.json").write_text(json.dumps(state), encoding="utf8")
    except OSError:
        return None

    reason = (
        "underneath (Stop hook): you changed code in this turn. Before you finish, give the developer the "
        "underneath card. Follow the underneath skill from step 3: the brief below is the output of "
        "`extract`, so do not run extract again. Write the notes file it names, following "
        f"{HERE.parent / 'references' / 'card-format.md'}, then run `python3 {CLI} render` and show the card "
        "verbatim in a code block, with at most one sentence after it. Do not edit the user's code for this. "
        'If the developer does not want this, they can set "stop_hook": false in .underneath/config.json.\n\n'
        + brief
    )
    # additionalContext keeps Claude going like {"decision": "block"}, with the same loop guards
    # (stop_hook_active, the continuation cap), but shows as "Stop hook feedback", not as an error.
    return {"hookSpecificOutput": {"hookEventName": "Stop", "additionalContext": reason}}


def _missing_dependency(out: Path) -> dict | None:
    """Say once a day how to install tree-sitter, without blocking."""
    state = _load(out / "hook.json", {})
    today = date.today().isoformat()
    if state.get("warned") == today:
        return None
    state["warned"] = today
    try:
        out.mkdir(parents=True, exist_ok=True)
        (out / "hook.json").write_text(json.dumps(state), encoding="utf8")
    except OSError:
        pass
    req = HERE.parent / "requirements.txt"
    return {
        "systemMessage": (
            "underneath: tree-sitter is not installed, so the card is skipped. Install it once with: "
            f"python3 -m venv ~/.underneath/venv && ~/.underneath/venv/bin/pip install -r {req}"
        )
    }


def main() -> int:
    try:
        hook_input = json.loads(sys.stdin.read() or "{}")
    except ValueError:
        return 0
    try:
        answer = decide(hook_input)
    except Exception as e:  # noqa: BLE001 - never break the user's session
        print(f"underneath stop hook: {e}", file=sys.stderr)
        return 0
    if answer:
        print(json.dumps(answer))
    return 0


if __name__ == "__main__":
    sys.exit(main())
