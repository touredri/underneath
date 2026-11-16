---
name: underneath
description: After you write or change code (TypeScript/React, JavaScript, Python, SQL), show the developer a 5-line card and a visual map of the functions you generated, how they connect, the key concepts they use (hooks, async, joins…) and the language fundamental underneath. Use once at the end of a coding task that added or changed real code, or when the user says /underneath, "what did you just write", "map the changes" or "explain the concepts in this diff".
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

- `/underneath deeper <id>`: run `python3 SKILL_DIR/scripts/underneath.py deeper <id>` with a fundamental id (`closures`) or a concept id (`react.useEffect`) and show the output. Then relate it to the user's code in two or three sentences.
- `/underneath known <concept id>`: run `… underneath.py known <id>`. The concept will be drawn compact from now on.
- "since <ref>": rerun step 2 with `--base <ref>`.

## Language

Write the notes in English, unless `.underneath/config.json` contains `"language": "<code>"`, in which case write `summary`, `here`, `watch` and `fundamental.text` in that language.

## Do not

- Do not edit the user's code as part of this skill. If a watch item is a real bug, mention it in your one sentence and offer to fix it.
- Do not paste the brief, `graph.json` or the notes into the conversation.
- Do not run it in a loop or on every file save.
