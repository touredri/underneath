---
stack: react
languages: tsx, jsx, ts, js
---

# React concepts

Each concept is one `##` section. The fields are read by `scripts/concepts.py`.

- `id`: stable identifier, `stack.name`
- `detect`: one or more rules, any of which matches
  - `call NAME`: the function calls `NAME(...)` (read from the syntax tree)
  - `regex PATTERN`: Python regex searched in the function's source
  - `name PATTERN`: Python regex matched against the function's own name
- `requires`: another concept id that must also be present in the same function
- `fundamental`: id from `references/fundamentals.md`
- `what`: one sentence, what it does
- `pitfalls`: the classic mistakes, separated by `;`
- `relates`: other concept ids it usually works with
- `risk`: `yes` when a match is itself a likely bug; such concepts are always drawn and offered as a watch item
- `minor`: `yes` for basics that are everywhere (list keys, event handler props); they are drawn only when nothing more telling is left

## useState
- id: react.useState
- detect: call useState
- fundamental: closures
- what: Holds a value across renders; calling the setter schedules a new render.
- pitfalls: Reading the state right after setting it still gives the old value; mutating an object or array in place does not trigger a render; deriving state that could be computed from props.
- relates: react.useEffect

## useEffect
- id: react.useEffect
- detect: call useEffect
- fundamental: closures
- what: Runs a side effect after render, and again whenever a dependency changes.
- pitfalls: A missing dependency leaves a stale value inside the effect; setting state that is also a dependency causes a loop; fetching without cancelling lets an old answer overwrite a newer one.
- relates: react.useState, react.effectCleanup

## Effect cleanup
- id: react.effectCleanup
- detect: regex return\s*\(\s*\)\s*=>
- detect: regex return\s+function\s*\(
- requires: react.useEffect
- fundamental: closures
- what: The function returned by an effect runs before the next run of that effect and when the component unmounts.
- pitfalls: Forgetting to clear timers, subscriptions or listeners; cleaning up something created in a different render.
- relates: react.useEffect, web.AbortController

## useMemo
- id: react.useMemo
- detect: call useMemo
- fundamental: reference-equality
- what: Recomputes a value only when its dependencies change.
- pitfalls: Used on cheap computations it costs more than it saves; with the React Compiler enabled it is often unnecessary; a missing dependency returns a stale value.
- relates: react.useCallback, react.memo

## useCallback
- id: react.useCallback
- detect: call useCallback
- fundamental: reference-equality
- what: Keeps the same function identity between renders until a dependency changes.
- pitfalls: Pointless unless the function is passed to a memoized child or used as a dependency; a missing dependency freezes old values inside the callback.
- relates: react.useMemo, react.memo

## useRef
- id: react.useRef
- detect: call useRef
- fundamental: reference-equality
- what: A mutable box that survives renders; changing `.current` does not re-render.
- pitfalls: Reading `ref.current` during render; using a ref where state is needed, so the screen never updates.
- relates: react.useEffect

## useContext
- id: react.useContext
- detect: call useContext
- fundamental: scope
- what: Reads a value provided higher in the tree without passing props down every level.
- pitfalls: Every consumer re-renders when the provided value changes; a new object literal as value re-renders all consumers each time.
- relates: react.useMemo

## useReducer
- id: react.useReducer
- detect: call useReducer
- fundamental: immutability
- what: Moves state updates into a pure function `(state, action) => newState`.
- pitfalls: Mutating `state` inside the reducer; side effects inside the reducer.
- relates: react.useState

## Custom hook
- id: react.customHook
- detect: name ^use[A-Z]
- fundamental: closures
- what: A function whose name starts with `use` and that calls other hooks, to reuse stateful logic.
- pitfalls: Calling hooks conditionally or inside loops; assuming two components share the same state (each call has its own).
- relates: react.useState, react.useEffect

## memo
- id: react.memo
- detect: call memo
- fundamental: reference-equality
- what: Skips re-rendering a component when its props are shallowly equal.
- pitfalls: New objects, arrays or functions in props defeat it on every render.
- relates: react.useCallback, react.useMemo

## List keys
- id: react.keys
- minor: yes
- detect: regex \.map\([\s\S]*?key=\{
- fundamental: reference-equality
- what: `key` tells React which list item is which between renders.
- pitfalls: Using the array index as key when items can be reordered, inserted or removed.
- relates:

## Event handler props
- id: react.callbackProps
- minor: yes
- detect: regex <[A-Z][\w.]*\b[^>]*\bon[A-Z]\w*=\{
- fundamental: higher-order-functions
- what: The parent passes a function to a child component; the child calls it to send information back up.
- pitfalls: Calling the function during render (`onClick={f()}`) instead of passing it (`onClick={f}`).
- relates: react.useCallback

## Data fetching
- id: web.fetch
- detect: call fetch
- fundamental: promises
- what: Starts an HTTP request and returns a promise of the response.
- pitfalls: `fetch` does not reject on 404 or 500, check `response.ok`; unhandled rejections; no cancellation.
- relates: web.AbortController, react.useEffect

## Classes
- id: js.class
- detect: regex (?m)^\s*(export\s+(default\s+)?)?(abstract\s+)?class\s+[A-Za-z_$]
- fundamental: object-model
- what: A constructor and methods shared through the prototype; `this` is the instance the method is called on.
- pitfalls: Passing `obj.method` as a callback loses `this`; fields initialised in the constructor run before subclass fields.
- relates: js.inheritance

## Class inheritance
- id: js.inheritance
- detect: regex \bclass\s+[\w$]+(\s*<[^>]*>)?\s+extends\s+[\w$.]+
- fundamental: object-model
- what: The class reuses its parent's methods through the prototype chain and can override them.
- pitfalls: Using `this` before calling `super()` in a constructor throws; overriding without calling `super.method()` drops the parent's behaviour.
- relates: js.class

## AbortController
- id: web.AbortController
- detect: regex new\s+AbortController
- detect: regex \bAbortSignal\b
- detect: regex \.signal\b
- detect: regex \bsignal\.(aborted|reason|throwIfAborted|addEventListener)\b
- detect: regex \bfetch\s*\([^;]*?\bsignal\b
- fundamental: promises
- what: Cancels an in-flight request so an old answer cannot overwrite a newer one.
- pitfalls: Setting state after the request was aborted; not treating the AbortError as a normal outcome.
- relates: web.fetch, react.effectCleanup

## Timers
- id: web.timers
- detect: call setTimeout
- detect: call setInterval
- fundamental: event-loop
- what: Schedules a callback for later, after the current code has finished.
- pitfalls: Not clearing the timer on unmount; assuming the delay is exact.
- relates: react.effectCleanup

## Promise.all
- id: js.promiseAll
- detect: regex Promise\.(all|allSettled|race|any)\(
- fundamental: promises
- what: Waits for several promises at once instead of one after the other.
- pitfalls: `Promise.all` rejects as soon as one fails; use `allSettled` to keep the others.
- relates: web.fetch

## async / await
- id: js.asyncAwait
- detect: regex \bawait\b
- fundamental: promises
- what: Writes promise-based code as if it were sequential.
- pitfalls: Awaiting in a loop when the calls could run in parallel; forgetting `try/catch` around awaited calls.
- relates: js.promiseAll
