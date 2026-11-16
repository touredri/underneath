# Changelog

All notable changes to underneath. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

## [0.4.0] - 2026-11-16

### Added

- Ten likely-bug rules, each tied to a fundamental and checked by the agent in the card: `= NULL` in a condition, `NOT IN (SELECT ...)`, `UPDATE`/`DELETE` without `WHERE`; an effect without dependency array that sets state, an async effect, `key={index}` from the map callback; `forEach(async ...)`, an empty `catch`; an `except` that only passes, a database query in a loop body (N+1). Twelve in all with the mutable default and the `WHERE` that undoes a `LEFT JOIN`.
- `detect: tree <flag>` in stack files: structural patterns read from the syntax tree (a missing argument, an empty block, a call inside a loop body), for what a regex cannot see reliably.
- Evaluation: likely-bug recall and false alarms (thresholds: at least 90 %, zero false alarms), six cases with each pattern and its safe version, and 22 more real commits (bulletproof-react, full-stack-fastapi-template, djangoproject.com): 76 cases in all.
- `stop_hook_timeout` in `.underneath/config.json` (20 s by default).
- `evals/tools/import_case.py` redacts key-shaped strings (API keys, tokens, private keys) when it copies a commit, even public test keys.

### Changed

- The Stop hook follows the code, not the tool: a file rewritten through Bash asks for the card; a turn that only read (`git status`) stays quiet. Past the timeout it skips the card and says so once a day. It falls back to `python` where `python3` does not exist.
- Calls are classified by their receiver. A bare call (`render()`) links to a function or a class, never to a method; a call on a local variable or a parameter of unknown type, or on a chain, links nothing by name; a fluent chain of the class's own calls (`self.filter(...).with_latest()`) stays in the class; `Model.objects.m()` goes through the type the class declares for `objects`.

### Fixed

- Django test files (`tests.py`, `tests_*.py`, `conftest.py`) were drawn as code.
- Three kinds of wrong links seen in real code: Django's `render()` to a widget's `render` method, a local `search = partial(...)` to a `search` method, `subscription.unsubscribe()` to another class's `unsubscribe`.

## [0.3.0] - 2026-11-16

### Added

- Classes are nodes. A class shows its decorators, bases and class attributes (its methods stay separate nodes), `extends` and `class A(B)` give an `inherits` edge, and `Cls()` / `new Cls()` link to the class. New concepts: `py.inheritance`, `py.abstract`, `js.class`, `js.inheritance`; `py.dataclass` now fires on the class it decorates.
- Calls are resolved by the receiver's type when the code states it: a parameter annotation, a constructor call, a `self`/`this` attribute set from one of those, or a module-level instance. `cache.get(k)` with `cache: ReportCache` links to `ReportCache.get`, or to the method a base class provides; `super()` goes to the base class.
- SQL inside Python and JS strings: a string passed to `execute`, `text`, `read_sql`, `query`, the `` sql`...` `` tag and the like, or written in uppercase SQL, is read as SQL. Its concepts and risks apply (a `LEFT JOIN` undone by `WHERE` in a backend function is flagged), and the tables it names get a `queries` edge.
- History and `underneath log`: every rendered card is kept in `.underneath/history.jsonl` (locally); `log [--days N]` sums up a period in 5 lines: changes, concepts that came back, new ones, likely bugs, and the concept to look at next.
- 24 evaluation cases from real commits of zustand, httpx, postgres_dba and jaffle-shop-classic, annotated by reading each diff, and `evals/tools/import_case.py` to add more. `evals/run.py --only/--skip`, per-case `limits`.

### Changed

- One tree-sitter query per file collects every node the extractors need, in C: parsing a 2,030-file repository went from 17.9 s to 10.6 s, with identical output.
- Editing only a docstring or whole-line comments no longer marks a function modified.
- A function copied from one that still exists is new, not moved.

### Fixed

- SQL statements starting with `WITH`, and statements inside `BEGIN ... COMMIT`, produced no node at all.
- `sql.subquery` fired on a CTE body.
- Methods called on a chain of unknown type (`self.decompressor.flush()`) or on a generator (`gen.send(x)`) were linked to project methods with the same name.
- The comprehension rule missed `[f(x) for x in xs]`; an `async` JS function without `await` was not async.

## [0.2.1] - 2026-11-16

### Fixed

- `map.html` hid likely bugs when they rested on a rarely used fundamental: the chip said "4 likely bugs" but no amber dot was drawn. A fundamental with a likely bug now always gets its row (still 7 rows at most), and the likely bug comes first in it.
- Context slots went to utilities used all over the project (`cn`, `Button`, `Badge`) instead of what the change depends on. A callee named in more than 10 files now weighs a tenth as much; callers still come first.
- Basic concepts that are everywhere (event handler props, list keys, special methods) took the place of telling ones (useEffect, effect cleanup). They are now marked `minor: yes` in the stack files and drawn only when nothing more telling is left; they stay listed under "also present". A Python `__init__` alone no longer counts as a special method. In `gaps` and in each row of `map.html`, minor concepts come after the others.

### Added

- `evals/`: an 18th case, and a `context` check (expected and unwanted context functions) with its threshold.
- `minor: yes` in stack files.

## [0.2.0] - 2026-11-16

### Added

- `underneath map`: the whole project's concepts, grouped by the fundamental they rest on, with use counts and main files. A 5-line card in the terminal, then `.underneath/map.html` in the same style as the diff map. Results are cached per file, so later runs only parse what changed.
- `underneath gaps`: the concepts in your code you never marked known, most used first, each with its `deeper` command. 5 lines at most.
- Claude Code plugin: `.claude-plugin/plugin.json`, a marketplace manifest, and a `Stop` hook that asks the agent for the card when a turn changed code. It asks once per change, never loops (`stop_hook_active`), stays quiet when nothing was edited, and is switched off per project with `"stop_hook": false` in `.underneath/config.json`.
- Moved code: a function moved to another file, renamed with its file, or pulled out of a bigger function is marked `moved` (dotted border) instead of new, and its lines no longer count as added.
- Evaluation set: `evals/` holds 17 diffs with human-written expected concepts and links, and `evals/run.py` measures concept precision (an invented concept is any one not expected), recall, edge recall and false links. Thresholds in `evals/thresholds.json` make it a CI gate.
- GitHub Action running the tests and the evals on Linux (Python 3.10, 3.13) and macOS.
- `--version`, and `--root` for `map` and `gaps`.

### Changed

- Extraction parses only the changed files and the files that can connect to them, found with `git grep`. On a 2,000-file repository a diff takes 1.5 to 4 s instead of 21 s, with the same graph.
- Test functions are no longer drawn. They show as "N tests" in the card and as "tested by N" on the functions they call; their concepts are not counted.
- The CLI finds its dependencies in `<skill>/.venv` or `~/.underneath/venv` by itself, since recent macOS and Linux refuse `pip install` into the system Python.

### Fixed

- The same diff could give a different map from one run to the next (ties broken by set order).
- Python strings and docstrings triggered concepts ("await" in a docstring counted as async code).
- A decorated Python method counted as a closure.
- `IS NOT NULL` in a query counted as a NOT NULL constraint.
- Any variable named `signal` counted as an AbortController.
- Calls on built-in collections and promises (`rows.get(k)`, `items.push(x)`) were linked to project methods with the same name.
- Two concepts with the same label (Python and JavaScript `async / await`) could not be told apart in `map` and `gaps`.

## [0.1.0] - 2026-11-16

### Added

- First release: `extract`, `render`, `deeper`, `known`. A 5-line card and an HTML map of the functions an agent changed, how they connect, the concepts they use and the fundamental underneath, for React/TypeScript/JavaScript, Python and SQL.

[0.4.0]: https://github.com/touredri/underneath/compare/v0.3.0...v0.4.0
[0.3.0]: https://github.com/touredri/underneath/compare/v0.2.1...v0.3.0
[0.2.1]: https://github.com/touredri/underneath/compare/v0.2.0...v0.2.1
[0.2.0]: https://github.com/touredri/underneath/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/touredri/underneath/releases/tag/v0.1.0
