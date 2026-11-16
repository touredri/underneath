# underneath: context for Claude Code

Open-source Agent Skill that helps developers keep their fundamentals while AI generates code faster than they can read it. After a coding task it shows a 5-line card and an HTML map of the functions the agent generated, how they connect, the concepts they use, and the language fundamental underneath.

## Decisions already made (do not reopen without the maintainer)

- Name: `underneath`. License MIT. Output language: English by default (`.underneath/config.json` can set another).
- First stacks: React/TS/JS, Python, SQL.
- **No quizzes.** The maintainer rejected them. The value is concept hints + relations, not tests.
- Two-tier output because people do not read: 5-line terminal card, then the visual map. Budgets: card ≤ 5 lines; map ≤ 7 changed functions, ≤ 3 context functions, ≤ 5 concepts, 1 fundamental; node label ≤ 18 chars; panel summary ≤ 140 chars.
- **The syntax tree decides, the model explains.** Nodes, calls and concepts come from tree-sitter + `references/stacks/*.md` rules. The agent only writes `notes.json`; `render` drops anything that does not exist in `graph.json`.
- Edges are `extracted` (solid) or `inferred` (dashed purple, max 4). Idea borrowed from Graphify (github.com/Graphify-Labs/graphify): Graphify maps a codebase for the agent, underneath maps a change for the human.
- Each concept points to a fundamental (closures, reference equality, event loop, three-valued logic…). That "one floor down" link is the differentiator.
- `risk: yes` concepts (mutable default, WHERE undoing a LEFT JOIN) are always drawn and must be checked by the agent.
- Test files are not drawn as nodes; they become "tested by N tests" on the function.
- Code moved or extracted elsewhere in the diff is `moved` (dotted), never `new`.
- **Precision before recall.** Zero invented concepts and zero false links, enforced by `evals/` in CI. When in doubt, do not link and do not detect.
- The Stop hook answers with `hookSpecificOutput.additionalContext`, not `{"decision": "block"}` (same loop guards, but Claude Code does not show it as an error). Approved by the maintainer.
- `map` and `gaps` budgets: card ≤ 5 lines; map ≤ 7 fundamentals × 4 concepts; gaps ≤ 5 lines.
- Local only, no network, no telemetry. `.underneath/` writes its own `.gitignore`.

## Layout

```
SKILL.md                      instructions the agent follows (also the plugin's skill)
.claude-plugin/               plugin.json (version) and marketplace.json
hooks/hooks.json              Stop hook -> scripts/stop_hook.py
scripts/underneath.py         CLI: extract | render | map | gaps | deeper | known (re-runs itself in a venv)
scripts/diffscope.py          git diff (or --before/--after folders), project scope, git grep scans
scripts/parse.py              tree-sitter: top-level symbols, calls, member-only calls, JSX renders, decorators, SQL refs
scripts/concepts.py           loads stacks/*.md and fundamentals.md, detects concepts (comments, Python strings removed)
scripts/graph.py              neighbour files, statuses (moved), name resolution, ranking, hub, context, concepts
scripts/render.py             notes validation, layout, SVG/HTML, card, registry
scripts/project.py            whole-project scan with per-file cache (map, gaps)
scripts/render_map.py         map/gaps cards and map.html
scripts/stop_hook.py          the Stop hook; scripts/ids.py: change_id shared with render
references/stacks/*.md        concept catalogues (the contribution unit)
references/fundamentals.md    fundamentals with a short example each
references/card-format.md     notes.json schema, writing rules, config.json keys
examples/*/before|after       fixtures, each with the notes.json an agent would write
evals/                        cases/*/expected.json, run.py (precision, recall, false links), thresholds.json
tests/test_examples.py        end-to-end tests (includes the evals)
.github/workflows/ci.yml      tests + evals on Linux (3.10, 3.13) and macOS
```

## Commands

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt   # the CLI finds .venv by itself
python3 tests/test_examples.py          # must stay green
python3 evals/run.py                    # must stay at 0 invented, 0 false links
claude plugin validate .                # plugin manifest
python3 scripts/underneath.py extract --before examples/react-search/before --after examples/react-search/after --out /tmp/demo
cp examples/react-search/notes.json /tmp/demo/ && python3 scripts/underneath.py render --out /tmp/demo
```

Inside a real git repo: `python3 <this folder>/scripts/underneath.py extract`, write `.underneath/notes.json`, then `render`.

## Status

v0.2.0 (2026-11-16), see CHANGELOG.md. Dogfooded on a private 2,000-file React + FastAPI repo: a diff takes 1.5 to 4 s, `map` 5 s cold and under 1 s warm. Plugin and Stop hook tested in real `claude -p --plugin-dir` sessions. 16 tests and 17 eval cases green (100 % precision and recall, 0 false links), also on Python 3.10. Not yet published: the GitHub repo `touredri/underneath` is prepared (README, badge, CHANGELOG links) but not created or pushed.

Known limits: name-based call resolution (same class, same file, imports as hints), and built-in method names (`get`, `push`…) on other objects are never linked; only top-level functions and methods (no class nodes); SQL inside strings not parsed; regex-based concept rules.

Frictions seen while dogfooding and not fixed yet:
- Context slots go to utilities called everywhere (`cn`, `Button`); prefer callers, skip high fan-in leaves.
- Trivial concepts (Event handler props, Special methods for `__init__`) can outrank useful ones (useEffect, cleanup); weight concepts, not only count them.

## Next steps (in order)

1. Publish: create the GitHub repo, push `main` and tags `v0.1.0`, `v0.2.0`, check the Action runs green, then try the marketplace install from GitHub.
2. The two open frictions above, each with an eval case.
3. v0.3: optional Graphify `graph.json` for callers outside the scan; classes as nodes; a larger eval set (cases from real diffs).
4. v0.4: more stacks (Vue, Django, Go).

## Conventions

- Keep the card and map budgets. If something needs more text, it goes in the click panel.
- Every new detection rule comes with a fixture and an assertion: an `evals/cases/` case (with a trap that must not match) or an `examples/` folder plus a test.
- Bump the version in three places together: `scripts/underneath.py` (`__version__`), `.claude-plugin/plugin.json`, `CHANGELOG.md` (a test checks it).
- User-facing strings in English, sentence case.
