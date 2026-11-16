# Changelog

All notable changes to underneath. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/); versions follow [Semantic Versioning](https://semver.org/).

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

[0.2.0]: https://github.com/touredri/underneath/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/touredri/underneath/releases/tag/v0.1.0
