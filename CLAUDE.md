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
- Local only, no network, no telemetry. `.underneath/` writes its own `.gitignore`.

## Layout

```
SKILL.md                      instructions the agent follows
scripts/underneath.py         CLI: extract | render | deeper | known
scripts/diffscope.py          git diff (or --before/--after folders)
scripts/parse.py              tree-sitter: top-level symbols, calls, JSX renders, decorators, SQL refs
scripts/concepts.py           loads stacks/*.md and fundamentals.md, detects concepts
scripts/graph.py              statuses, name resolution, ranking, hub, context, concept selection
scripts/render.py             notes validation, layout, SVG/HTML, card, registry
references/stacks/*.md        concept catalogues (the contribution unit)
references/fundamentals.md    fundamentals with a short example each
references/card-format.md     notes.json schema and writing rules
examples/*/before|after       fixtures, each with the notes.json an agent would write
tests/test_examples.py        end-to-end tests
```

## Commands

```bash
pip install -r requirements.txt
python3 tests/test_examples.py          # must stay green
python3 scripts/underneath.py extract --before examples/react-search/before --after examples/react-search/after --out /tmp/demo
cp examples/react-search/notes.json /tmp/demo/ && python3 scripts/underneath.py render --out /tmp/demo
```

Inside a real git repo: `python3 <this folder>/scripts/underneath.py extract`, write `.underneath/notes.json`, then `render`.

## Status

v0.1 done and tested on the 3 examples plus two real repos (zustand, httpx): extraction under 0.5 s.

Known limits: name-based call resolution (same class, same file, imports as hints); only top-level symbols; SQL inside strings not parsed; regex-based concept rules.

## Next steps (in order)

1. Dogfood: install as `~/.claude/skills/underneath`, use it on a real project, fix what feels wrong.
2. Publish the GitHub repo (README is ready; replace `<you>` in the clone URL).
3. v0.2: `underneath map` (whole-project concept skeleton) and `underneath gaps` (concepts present but never marked known).
4. v0.3: Claude Code plugin with a `Stop` hook. The hook runs `extract`; if not skipped, it returns `{"decision": "block", "reason": "Produce the underneath card…"}`. Check `stop_hook_active` to avoid loops.
5. v0.4: public eval set (diffs + expected concepts, zero invented concepts), more stacks.

## Conventions

- Keep the card and map budgets. If something needs more text, it goes in the click panel.
- Every new detection rule comes with a fixture in `examples/` and an assertion in `tests/`.
- User-facing strings in English, sentence case.
