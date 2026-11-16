---
name: underneath
description: After you write or change code (TypeScript/React, JavaScript, Python, SQL), show the developer a 5-line card and a visual map of the functions you generated, how they connect, the key concepts they use (hooks, async, joins…) and the language fundamental underneath. Use once at the end of a coding task that added or changed real code, or when the user says /underneath, "what did you just write", "map the changes" or "explain the concepts in this diff". Also maps the whole project's concepts (/underneath map, "what concepts does this codebase rest on") lists the ones the user never marked known (/underneath gaps, "what should I learn in this code") and sums up the recent cards (/underneath log, "what did I learn this week").
---

# underneath

The developer cannot read everything you generate. This skill gives them, in ten seconds, what changed, how it fits together and what it rests on, so they stay in control of their own code.

You do not decide what is in the map. The syntax tree does. You only explain.

## When to run it

- Once, at the end of a coding task that added or changed code in `.ts .tsx .js .jsx .py .sql` files. Not after every edit.
- When the user asks for it (`/underneath`, "map what you did", "what concepts does this use").
- Skip it for renames, formatting, typo fixes, or when the user is clearly in a hurry and said so.

## Steps

`SKILL_DIR` below is the folder that contains this file.

1. **Check the dependency** (first run only): `python3 SKILL_DIR/scripts/underneath.py deeper closures`.
   If it says tree-sitter is missing, install it in a virtualenv next to the skill (the script uses it by itself):
   `python3 -m venv SKILL_DIR/.venv && SKILL_DIR/.venv/bin/pip install -r SKILL_DIR/requirements.txt`.

2. **Extract**, from the project root:
   ```
   python3 SKILL_DIR/scripts/underneath.py extract
   ```
   By default it compares the working tree with `HEAD` (uncommitted work, new files included). If the user names a branch or commit ("since main"), add `--base main`.
   If the output starts with `underneath: small change` or `underneath: no supported changes`, stop. Say nothing about it unless the user asked for the map.

3. **Read the brief** it prints: nodes with fixed ids (`n1`, `n2`…), their code, the concepts detected, and the fundamental candidates. Do not show the brief to the user.

4. **Write `.underneath/notes.json`** (the path is printed in the brief). Follow `references/card-format.md` exactly. In short:
   - Only ids that appear in the brief. Never add a function, a concept or a relation the brief does not contain, except up to 4 `inferred_edges` between existing ids.
   - Write about this code, not the concept in general.
   - A concept marked `LIKELY BUG`: read the code. If the bug is real, it takes the first `watch` slot. If not, explain why in its `here`.
   - `watch`: at most 2, only what is actually present or actually guarded in this diff. An empty list is fine.
   - `fundamental`: one id from the candidates, linked to this exact code.

5. **Render**:
   ```
   python3 SKILL_DIR/scripts/underneath.py render
   ```
   It prints the card and writes `.underneath/latest.html`. Lines starting with `note:` on stderr mean part of your notes was rejected; fix the notes and render again if the card lost something important.

6. **Show the card** to the user, verbatim, in a code block. Add at most one short sentence after it (for example, that the map can be opened). Do not repeat or explain the card in prose: the point is that it is short.

   Open the map in a browser (`open`, `xdg-open` or `start`) only if the user asks.

## Other commands

- `/underneath map`: the whole project's concept skeleton. Run `python3 SKILL_DIR/scripts/underneath.py map` from the project root and show the card verbatim in a code block, plus at most one sentence. It writes `.underneath/map.html`: one row per fundamental, the concepts of the code that rest on it, most used first. The first run parses every file (a few seconds on a large repository); later runs only re-read what changed. Do not write notes for it: there is nothing to explain, only to show.
- `/underneath gaps`: run `… underneath.py gaps` and show its lines verbatim: the concepts present in the code that the user never marked known, most used first, each with its `deeper` command. If the user picks one, run `deeper` on it (below). If they say they know one, run `known` on it.
- `/underneath log` (or "what did I learn this week"): run `… underneath.py log` (add `--days N` if the user names a period) and show its lines verbatim: how many cards, the concepts that came back most, the new ones, the likely bugs flagged, and the one concept to look at next. Every rendered card is kept in `.underneath/history.jsonl`, locally.
- `/underneath deeper <id>`: run `python3 SKILL_DIR/scripts/underneath.py deeper <id>` with a fundamental id (`closures`) or a concept id (`react.useEffect`) and show the output. Then relate it to the user's code in two or three sentences.
- `/underneath known <concept id>`: run `… underneath.py known <id>`. The concept will be drawn compact from now on.
- "since <ref>": rerun step 2 with `--base <ref>`.

## Language

Write the notes in English, unless `.underneath/config.json` contains `"language": "<code>"`, in which case write `summary`, `here`, `watch` and `fundamental.text` in that language.

## When the Stop hook asks for the card

Installed as a Claude Code plugin, underneath has a `Stop` hook. When a turn edited code, the hook runs `extract` and sends you its brief with the instruction to produce the card. Follow it from step 3 of the steps above (do not run extract again), render, show the card, and stop. The hook asks once per change and never while you are already answering it.

If the user says they do not want the card at the end of each task, set `"stop_hook": false` in `.underneath/config.json` (create the file if needed; keep its other keys). `/underneath` still works by hand.

## Do not

- Do not edit the user's code as part of this skill. If a watch item is a real bug, mention it in your one sentence and offer to fix it.
- Do not paste the brief, `graph.json` or the notes into the conversation.
- Do not run it in a loop or on every file save.
