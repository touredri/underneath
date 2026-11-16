# underneath

[![ci](https://github.com/touredri/underneath/actions/workflows/ci.yml/badge.svg)](https://github.com/touredri/underneath/actions/workflows/ci.yml)

**See what the AI just wrote, and what it rests on.**

Coding agents write more code than anyone can read. Day after day you accept diffs you only half understand, and the basics (closures, joins, the event loop) quietly fade.

`underneath` is an [Agent Skill](https://agentskills.io) and a Claude Code plugin that runs at the end of a coding task and gives you, in ten seconds:

1. **A 5-line card** in your terminal: what changed, the function everything flows through, the new concepts, the one thing to watch.
2. **A visual map** (`.underneath/latest.html`): the generated functions, how they call each other, the concepts each one uses, and the language fundamental underneath. Click anything for a two-line explanation.

```
underneath · 4 new · 1 modified · 5 new concepts · 1 to watch
  hub   App → SearchUsers → useDebounce, searchUsers, sortUsers
  new   Effect cleanup, useEffect, useState   ↓ closures
  ⚠     src/components/SearchUsers.tsx:21  setResults after abort: guarded by signal.aborted, OK
  map   .underneath/latest.html
```

![The map for a React change](docs/map-react.png)

## Why

In a randomized controlled trial, Anthropic found that developers learning a new library with AI assistance scored 17% lower on a comprehension quiz than those coding by hand, with the largest gap in debugging. Developers who asked conceptual questions while using AI kept most of their understanding ([Anthropic, 2026](https://www.anthropic.com/research/AI-assistance-coding-skills)).

`underneath` makes that conceptual step automatic, without quizzes and without slowing the agent down.

## What makes it different

- **The syntax tree decides, the model explains.** Functions, calls and concepts come from [tree-sitter](https://tree-sitter.github.io/), not from the model. The agent can only describe what is there. Notes that mention anything else are rejected.
- **Read from the code vs inferred.** Solid lines are extracted from the source. Dashed purple lines ("triggers", "aborts") are the agent's interpretation, and look like it.
- **One floor down.** Every concept points to the language fundamental it rests on: `useEffect` → closures, `useMemo` → reference equality, `LEFT JOIN` → three-valued logic. `/underneath deeper closures` shows a 10-line example.
- **Built for people who won't read.** 5 lines of text. At most 7 changed functions, 3 context functions and 5 concepts on the map. Everything else is one click away.
- **Honest about what changed.** Code moved to another file, or pulled out of a big function, is marked *moved*, not new. Editing only a docstring is no change. Tests are not drawn: they become "tested by N" on the functions they call.
- **Links you can trust.** `cache.get(k)` links to `ReportCache.get` when the code says `cache: ReportCache`; `rows.get(k)` on a dict links to nothing. Classes, `extends` and `super()` are followed; SQL written in Python or JS strings is read as SQL.
- **Likely bugs surface by themselves.** Twelve rules are marked `risk`, each tied to the fundamental that explains it: `= NULL`, `NOT IN (SELECT …)`, an `UPDATE` without `WHERE`, a `WHERE` that undoes a `LEFT JOIN`; an effect without dependencies that sets state, an async effect, `key={index}`; `forEach(async …)`, an empty `catch`; an `except` that only passes, a query in a loop (N+1), a mutable default argument. They are always drawn, the agent must say whether each one is real or guarded, and the evaluation set counts false alarms as failures.
- **It remembers what you know.** A local registry counts the concepts you have seen. New ones get a thick border; familiar ones fade out. `/underneath gaps` lists the ones you never marked as known.
- **Measured.** 76 diffs, 46 of them real commits of open-source projects, check that no concept is invented, no false link is drawn and no likely bug is raised for nothing (see [Evaluation](#evaluation)).
- **Local.** No network, no telemetry. `.underneath/` ignores itself in git.

![The fundamental panel for a SQL change, dark mode](docs/map-sql-dark.png)

## Install

Requires Python 3.10+ and git. Install the parser once, in a virtualenv the script finds by itself (macOS and recent Linux refuse `pip install` into the system Python):

```bash
python3 -m venv ~/.underneath/venv
~/.underneath/venv/bin/pip install tree-sitter tree-sitter-language-pack
```

### Claude Code (plugin, with the automatic card)

In Claude Code:

```
/plugin marketplace add touredri/underneath
/plugin install underneath@underneath
```

The plugin adds the skill and a `Stop` hook: when a turn changed code, the agent shows the card before it finishes. The hook asks once per change, never loops, and stays quiet when the code did not change during the turn (it follows the code, so a file rewritten through Bash counts) or the change is tiny. If `extract` takes longer than 20 seconds, it skips the card and says so. To turn it off for a project, put `{"stop_hook": false}` in `.underneath/config.json`.

### Any agent (skill only)

```bash
git clone https://github.com/touredri/underneath
```

Then put the folder where your agent looks for skills:

| Agent | Location |
|---|---|
| Claude Code | `~/.claude/skills/underneath` (all projects) or `.claude/skills/underneath` (one project) |
| Codex, Cursor, Gemini CLI, Copilot and other Agent Skills clients | `.agents/skills/underneath` |

A `.venv` inside the cloned folder works too.

## Use

Work as usual. At the end of a task the agent runs the skill and shows the card. You can also ask:

- `/underneath`: map the uncommitted changes
- `/underneath since main`: map everything since `main`
- `/underneath map`: the whole project's concept skeleton
- `/underneath gaps`: concepts in your code you never marked as known
- `/underneath log`: what the cards of the last 7 days showed (`--days N` for another period)
- `/underneath deeper closures`: the fundamental, with a minimal example
- `/underneath known react.useState`: stop highlighting a concept you know

### The project map

`/underneath map` reads every file once and groups the concepts of your code by the fundamental they rest on: one row per fundamental, its concepts most used first, each with its use count and main files. Here it is on the `examples/` folder of this repository:

```
underneath map · 48 files · 76 functions · 29 concepts on 14 fundamentals
  top   event loop 19 · closures 14 · higher-order functions 9
  ⚠     Mutable defaults ×2 · first at project-map/api/app/services.py:4 (+1 other)
  gaps  29 never marked known · /underneath gaps
  map   .underneath/map.html
```

![The project map](docs/map-project.png)

`/underneath gaps` turns it into a reading list:

```
underneath gaps · 29 of 29 concepts in your code never marked known, most used first
  async / await (py)  16×  /underneath deeper py.asyncAwait
  Decorators           7×  /underneath deeper py.decorator
  useState             6×  /underneath deeper react.useState
  Context managers     4×  /underneath deeper py.contextManager
```

### Run it yourself

```bash
python3 scripts/underneath.py extract            # brief for the agent + .underneath/graph.json
python3 scripts/underneath.py render             # card + .underneath/latest.html
python3 scripts/underneath.py map                # card + .underneath/map.html
python3 scripts/underneath.py gaps
python3 scripts/underneath.py log --days 30
python3 scripts/underneath.py deeper three-valued-logic
```

### Try it without an agent

```bash
python3 scripts/underneath.py extract --before examples/sql-orders/before --after examples/sql-orders/after --out /tmp/demo
cp examples/sql-orders/notes.json /tmp/demo/
python3 scripts/underneath.py render --out /tmp/demo
open /tmp/demo/latest.html
```

### Configuration

`.underneath/config.json` is optional:

```json
{ "language": "fr", "stop_hook": false, "stop_hook_timeout": 20, "limits": { "changed": 7, "context": 3, "concepts": 5, "min_lines": 8 } }
```

`language` sets the language of the agent's notes, `stop_hook` turns the plugin's hook off, `stop_hook_timeout` is how long it waits for `extract`, `limits` changes the map budgets.

## How it works

```
git diff ──▶ tree-sitter ──▶ graph.json ──▶ agent writes notes.json ──▶ render
             (functions,     (ranked, ≤10     (summaries, inferred       (card.md,
              calls, SQL      nodes, concepts   edges, watch items,        latest.html,
              references)     from stacks/)     one fundamental)           registry)
```

1. **Scope.** Changed files against `HEAD` (or `--base`), untracked files included.
2. **Extract.** Top-level functions, classes, methods, components, hooks, SQL tables, views, indexes, in the changed files and in the files that can connect to them (found with `git grep`, so a large repository is not parsed whole). Calls, JSX renders, decorators, base classes and SQL references (in `.sql` files and in SQL strings) become edges; a method call is resolved through its receiver's type when the code states it. Each symbol is new, modified, moved or context.
3. **Rank.** Changed symbols are scored by status, connections, entry point (exported component, route, view) and size. The best-connected one is the hub. Callers outside the diff become context; test files become "tested by N tests" instead of nodes.
4. **Concepts.** Rules from `references/stacks/*.md` run on each symbol (comments and Python strings removed). Risk rules first, then one concept per function, then the rest.
5. **Explain.** The agent reads a compact brief and writes `notes.json` (format in `references/card-format.md`).
6. **Render.** Notes are checked against the graph, then the card, the map and the registry are written.

On a 2,000-file React + Python repository, a diff takes 1.5 to 4 seconds; the project map takes about 5 seconds the first time and under one second after that.

## Evaluation

`evals/` holds diffs with the concepts and links a human expects. `python3 evals/run.py` reports:

- **concept precision**: a detected concept that is neither expected nor allowed is *invented*. The target is zero, and CI fails otherwise;
- **concept recall**: expected concepts that were found;
- **edge recall** and **false links**: expected calls found, and edges that should not be there;
- **wrong context**: an unchanged function drawn when it should not be (a utility used everywhere), or missing when it should be (a caller).

76 cases. 30 written for the purpose: the examples, a few changes per stack, each likely bug next to its safe version, and traps such as a docstring that says "await", `IS NOT NULL`, a variable named `signal`, `dict.get` next to a class with a `get` method, `cn` used in every page. 46 real commits of [zustand](https://github.com/pmndrs/zustand), [httpx](https://github.com/encode/httpx), [postgres_dba](https://github.com/NikolayS/postgres_dba), [jaffle-shop-classic](https://github.com/dbt-labs/jaffle-shop-classic), [bulletproof-react](https://github.com/alan2207/bulletproof-react), [full-stack-fastapi-template](https://github.com/fastapi/full-stack-fastapi-template) and [djangoproject.com](https://github.com/django/djangoproject.com), annotated by reading the diff before running the tool (licenses in `evals/third_party/`).

| On the same 76 cases | v0.3.0 | v0.4.0 |
|---|---|---|
| Concept precision | 99.0% (2 invented) | 100% (0 invented) |
| Concept recall | 94.5% | 100% |
| Edge recall | 95.2% | 98.6% |
| False links | 3 | 0 |
| Likely-bug rules | 2 | 12 |
| Likely bugs found / false alarms | | 100% / 0 |

The two links still missed need Django's runtime (`self.model`, a loop over `Model.__subclasses__()`). Each version is measured on cases that exposed its predecessor's mistakes, so read 100% as "fixed what this set exposed": the set keeps growing. To add a commit: `python3 evals/tools/import_case.py <repo> <sha> <name>`, fill `expected.json` from the diff, then `python3 evals/run.py --show <name>` prints what the tool sees.

## Add a stack

A stack is one Markdown file in `references/stacks/`. Each concept is a section:

```markdown
## useEffect
- id: react.useEffect
- detect: call useEffect
- fundamental: closures
- what: Runs a side effect after render, and again whenever a dependency changes.
- pitfalls: A missing dependency leaves a stale value; setting state that is also a dependency causes a loop.
- relates: react.useState, react.effectCleanup
```

`detect` accepts `call NAME` (from the syntax tree), `regex PATTERN` (on the function's source, comments and Python strings removed) and `name PATTERN` (on the function's name). Add `requires: <id>` for concepts that only make sense together, `risk: yes` when a match is itself a likely bug, and `minor: yes` for basics that are everywhere (they are drawn only when nothing more telling is left).

Point `fundamental` to an entry in `references/fundamentals.md`, or add one there with a short, runnable example.

Then add a case under `evals/cases/` (or an example under `examples/` with a test in `tests/test_examples.py`), including one that should *not* match. Run `python3 tests/test_examples.py` and `python3 evals/run.py`.

Stacks we would love to see: Vue, Svelte, Next.js server components, Django ORM, FastAPI, Go, Rust, Kotlin, Flutter.

## Limits (v0.4)

- A method call is linked through its receiver's type only when the code states the type (annotation, constructor, attribute set from one of those). Otherwise it falls back to the name, with same-class, same-file and import hints; built-in method names (`get`, `push`, `map`…) and calls on a chain (`self.x.m()`) are then not linked at all.
- Nested functions are folded into their parent. TypeScript interfaces and types are not nodes.
- SQL in strings is read only when passed to a known sink or written in uppercase SQL; SQL assembled from pieces is not.
- Likely-bug rules look at one function at a time: a query in a loop is seen when both are in the same function, not when the loop calls a helper that queries.
- Concept rules are pattern-based. The evaluation set keeps them honest, but it is small.
- The map is regenerated each time. There is no history yet.

## Roadmap

- **v0.5**: optional reading of a [Graphify](https://github.com/Graphify-Labs/graphify) `graph.json` for callers outside the repo scan; more real commits in the evaluation set.
- **v0.6**: more stacks (Vue, Django ORM, Go).
- **v1.0**: team mode, with a shared project registry as living onboarding documentation.

## Credits

The split between extracted and inferred edges, and the idea of a "god node" everything flows through, come from [Graphify](https://github.com/Graphify-Labs/graphify). Graphify maps a codebase for the agent; `underneath` maps a change for the human.

## License

MIT
