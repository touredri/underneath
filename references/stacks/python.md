---
stack: python
languages: python
---

# Python concepts

Same format as `react.md`. Rules run on each function's source, decorators included.

## Decorators
- id: py.decorator
- detect: regex ^\s*@(?!property\b|staticmethod\b|classmethod\b|dataclass\b|(abc\.)?abstractmethod\b|(dataclasses\.)?dataclass\b)[\w.]+
- fundamental: higher-order-functions
- what: `@deco` above a function replaces it with `deco(function)`, wrapping extra behaviour around it.
- pitfalls: Losing the function's name and docstring without `functools.wraps`; decorator order matters (bottom one applies first).
- relates: py.closure

## Closures
- id: py.closure
- detect: regex \bdef\s+\w+\([^)]*\)[^\n]*:[ \t]*\n(?:.*\n)*?[ \t]+(?:async\s+)?def\s+\w+\(
- fundamental: closures
- what: An inner function keeps access to the variables of the function that created it.
- pitfalls: Late binding in loops (every inner function sees the last loop value); assigning to an outer variable needs `nonlocal`.
- relates: py.decorator

## async / await
- id: py.asyncAwait
- detect: regex \basync\s+def\b
- detect: regex \bawait\b
- fundamental: event-loop
- what: A coroutine pauses at each `await` and lets the event loop run other work meanwhile.
- pitfalls: Calling blocking code (requests, time.sleep, heavy CPU) inside `async def` freezes everything; forgetting `await` returns a coroutine object instead of a result.
- relates: py.gather

## asyncio.gather
- id: py.gather
- detect: regex \b(asyncio\.)?(gather|TaskGroup|create_task)\b
- fundamental: event-loop
- what: Runs several coroutines concurrently and waits for all of them.
- pitfalls: One exception cancels or hides the others unless `return_exceptions=True` or a TaskGroup is used.
- relates: py.asyncAwait

## Context managers
- id: py.contextManager
- detect: regex (?m)^\s*(async\s+)?with\b
- fundamental: exceptions
- what: `with` guarantees setup and teardown (close a file, release a lock, commit or roll back) even if an error occurs.
- pitfalls: Returning a lazy object (generator, query) that is used after the `with` block has already closed the resource.
- relates: py.exceptions

## Generators
- id: py.generator
- detect: regex \byield\b
- fundamental: iterators
- what: A function with `yield` produces values one at a time, on demand, instead of building a whole list.
- pitfalls: A generator can only be consumed once; nothing runs until someone iterates over it.
- relates: py.comprehension

## Comprehensions
- id: py.comprehension
- detect: tree comprehension
- fundamental: iterators
- what: Builds a list, dict, set or generator from an iterable in one expression.
- pitfalls: Nesting them until they are unreadable; using a list comprehension only for its side effects.
- relates: py.generator

## Exceptions
- id: py.exceptions
- detect: regex (?m)^\s*(try:|except\b|raise\b)
- fundamental: exceptions
- what: `raise` stops the normal flow; the nearest matching `except` up the call stack handles it.
- pitfalls: Bare `except:` or `except Exception` that swallows real bugs; losing the original error without `raise ... from e`.
- relates: py.contextManager

## Mutable defaults
- id: py.mutableDefault
- risk: yes
- detect: regex def\s+\w+\([^)]*=\s*(\[\]|\{\}|set\(\)|dict\(\)|list\(\))
- fundamental: mutability
- what: Default values are created once, when the function is defined, not on each call.
- pitfalls: A default `[]` or `{}` is shared by every call and keeps growing. Use `None` and create it inside.
- relates:

## Swallowed exception
- id: py.swallowedException
- detect: tree swallowed-exception
- risk: yes
- fundamental: exceptions
- what: An `except` block that does nothing (`pass`, `...`, `continue`).
- pitfalls: Real bugs vanish with the error you meant to ignore. Catch the narrowest exception, log it, or say in a comment why it is safe.
- relates: py.exceptions

## Query in a loop
- id: py.queryInLoop
- detect: tree query-in-loop
- risk: yes
- fundamental: set-theory
- what: Runs one database query per loop iteration (the N+1 problem).
- pitfalls: 100 rows means 101 round trips. Load them in one query: a join, `IN (...)`, `selectinload` / `select_related`.
- relates: sql.innerJoin

## Dataclasses
- id: py.dataclass
- detect: regex @(dataclasses\.)?dataclass
- fundamental: object-model
- what: Generates `__init__`, `__repr__` and `__eq__` from annotated fields.
- pitfalls: Mutable defaults need `field(default_factory=...)`; `frozen=True` if instances should not change.
- relates: py.dunder

## Inheritance
- id: py.inheritance
- detect: regex (?m)^[ \t]*class\s+\w+\s*\(\s*(?!object\s*\))(?!metaclass\b)[A-Za-z_][\w.]*
- fundamental: object-model
- what: The class gets the attributes and methods of its base and can override them; lookups walk the bases in order (the MRO).
- pitfalls: Forgetting `super().__init__()`, so the base never sets its attributes; deep hierarchies where nobody knows which method actually runs.
- relates: py.abstract, py.dunder

## Abstract base classes
- id: py.abstract
- detect: regex \bABC\b|\bABCMeta\b|@(abc\.)?abstractmethod
- fundamental: object-model
- what: Declares methods every subclass must implement; the base itself cannot be instantiated.
- pitfalls: A subclass that misses one abstract method fails only when instantiated, not at import.
- relates: py.inheritance

## Special methods
- id: py.dunder
- detect: name ^__(?!init__$)\w+__$
- minor: yes
- fundamental: object-model
- what: Methods like `__len__`, `__eq__`, `__iter__` let your objects work with built-in syntax and functions.
- pitfalls: Defining `__eq__` without `__hash__` makes instances unhashable.
- relates: py.dataclass

## Properties
- id: py.property
- detect: regex @property
- fundamental: object-model
- what: Exposes a method as an attribute, so a computed value reads like a field.
- pitfalls: Hiding slow work (a query, a network call) behind what looks like a cheap attribute.
- relates: py.dunder

## *args and **kwargs
- id: py.varargs
- detect: regex def\s+\w+\([^)]*\*\*?\w+
- fundamental: scope
- what: Collects extra positional arguments into a tuple and extra keyword arguments into a dict.
- pitfalls: Swallowing typos in argument names that should have raised an error.
- relates: py.decorator

## Lambda
- id: py.lambda
- detect: regex \blambda\b
- fundamental: higher-order-functions
- what: A one-expression anonymous function, often passed as `key=` to sort, min or max.
- pitfalls: Late binding when created in a loop.
- relates: py.closure
