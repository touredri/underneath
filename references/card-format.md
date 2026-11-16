# Notes format

After `underneath.py extract`, the agent writes `.underneath/notes.json`. `underneath.py render` checks it against `graph.json`, drops anything that does not match, and builds the card and the map.

The agent only explains. It never adds functions or concepts: those come from the syntax tree.

## Schema

```json
{
  "nodes": {
    "<node id from graph.json>": {
      "summary": "One sentence about what this does here. Max 140 characters."
    }
  },
  "concepts": {
    "<concept id from graph.json>": {
      "here": "How this concept works in this code. Max 160 characters."
    }
  },
  "inferred_edges": [
    { "from": "<node or concept id>", "to": "<node or concept id>", "label": "triggers" }
  ],
  "watch": [
    { "node": "<node id>", "line": 22, "text": "What to look at and whether it is handled. Max 90 characters." }
  ],
  "fundamental": {
    "id": "<one id from graph.json fundamental_candidates>",
    "text": "One or two sentences linking it to this exact code. Max 220 characters."
  }
}
```

## Rules

- Write about this code, not the concept in general. "Waits 300 ms after the last keystroke" beats "Debounces a value".
- `summary`: present tense, no "This function". Start with a verb.
- `inferred_edges`: at most 4. Only relations a reader cannot see from the call graph: what triggers what, what cancels what, what invalidates what. Labels are one or two words: `triggers`, `cancels`, `re-renders`, `invalidates`, `reads`, `writes`.
- `watch`: when the brief marks a concept `LIKELY BUG`, look at the code: if the bug is real, it takes the first watch slot; if it is harmless here, say why in that concept's `here`. Otherwise, at most 2, only for a pitfall from the concept's `pitfalls` list that is actually present or actually avoided in the diff. Say which one: "guarded by …" or "missing …". Never invent a risk to fill the slot. An empty list is fine.
- `fundamental`: exactly one. Choose the candidate that explains the most of this change.
- Skip any field you have nothing true to say about. Missing summaries fall back to the signature.
- Write in English unless `.underneath/config.json` sets another `language`.

## config.json

`.underneath/config.json` is optional. All keys:

```json
{
  "language": "fr",
  "stop_hook": false,
  "limits": { "changed": 7, "context": 3, "concepts": 5, "min_lines": 8 }
}
```

- `language`: language of the notes (default English).
- `stop_hook`: `false` turns off the Claude Code plugin's Stop hook for this project (default on).
- `limits`: map budgets; `min_lines` is the size under which a change with nothing new is skipped.
