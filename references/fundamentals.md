# Fundamentals

The language-level ideas that framework concepts rest on. Each stack concept points to one of these ids with its `fundamental:` field.

`one-liner` is shown on the map when the agent gives nothing better. `/underneath deeper <id>` uses the whole section.

## Closures
- id: closures
- one-liner: A function remembers the variables that existed where it was created, even after that scope has finished.

```js
function counter() {
  let n = 0;
  return () => ++n;      // the arrow keeps access to n
}
const next = counter();
next(); // 1
next(); // 2
// React: each render creates new closures. An effect sees the values of the
// render that created it; the dependency array says when to create a new one.
```

## Reference equality
- id: reference-equality
- one-liner: Two objects with the same content are still different objects; `===` compares identity, not content.

```js
[1, 2] === [1, 2];            // false: two different arrays
const a = { x: 1 }; a === a;  // true: same object
// React compares props and dependencies by identity, so a new object or
// function created on every render counts as "changed" every time.
```

## Event loop
- id: event-loop
- one-liner: One thread runs your code; callbacks and resumed coroutines wait in a queue until the current code has finished.

```python
import asyncio
async def job(name, delay):
    await asyncio.sleep(delay)   # gives control back to the loop
    print(name)
async def main():
    await asyncio.gather(job("slow", 2), job("fast", 1))
asyncio.run(main())  # prints fast, then slow: total about 2 s, not 3
```

## Promises
- id: promises
- one-liner: A promise is a placeholder for a value that will arrive later, or an error that will.

```js
const p = fetch("/api/users");   // returns immediately
p.then(r => r.json())            // runs later, when the answer arrives
 .catch(err => console.error(err));
// await is the same thing written top to bottom:
// const r = await fetch("/api/users");
```

## Scope
- id: scope
- one-liner: Where a name is visible decides which value code sees when it uses that name.

```python
x = "global"
def f():
    x = "local"      # a new x, the global one is untouched
    def g():
        return x     # looks outward: finds f's x
    return g()
f()  # "local"
```

## Higher-order functions
- id: higher-order-functions
- one-liner: Functions are values: they can be passed in, returned, and wrapped by other functions.

```python
def logged(fn):
    def wrapper(*args):
        print("calling", fn.__name__)
        return fn(*args)
    return wrapper

@logged            # same as add = logged(add)
def add(a, b): return a + b
```

## Immutability
- id: immutability
- one-liner: Instead of changing a value in place, build a new one; then "did it change?" is a cheap identity check.

```js
const next = { ...state, count: state.count + 1 };  // new object
// state.count++  would change the old object, and React could not
// tell anything happened.
```

## Mutability
- id: mutability
- one-liner: Some values (lists, dicts, objects) can change in place, and every name pointing to them sees the change.

```python
a = [1]
b = a          # same list, two names
b.append(2)
print(a)       # [1, 2]
```

## Iterators
- id: iterators
- one-liner: An iterator hands out values one at a time when asked; `for` just keeps asking until it is told to stop.

```python
def evens(limit):
    n = 0
    while n < limit:
        yield n      # pause here, hand out n
        n += 2
list(evens(7))  # [0, 2, 4, 6]
```

## Exceptions
- id: exceptions
- one-liner: An error travels up the call stack until some caller handles it; cleanup code must run on that path too.

```python
try:
    f = open("data.txt")
    process(f)
except FileNotFoundError:
    print("missing")
finally:
    f.close()   # what `with open(...)` does for you
```

## Object model
- id: object-model
- one-liner: Built-in syntax calls special methods: `len(x)` calls `x.__len__()`, `a == b` calls `a.__eq__(b)`.

```python
class Bag:
    def __init__(self, items): self.items = items
    def __len__(self): return len(self.items)
len(Bag([1, 2, 3]))  # 3
```

## Set theory
- id: set-theory
- one-liner: Tables are sets of rows; joins, unions and filters combine and narrow those sets.

```sql
-- inner join = rows present on both sides
-- left join  = every left row, matched or not
SELECT u.name, o.id
FROM users u
LEFT JOIN orders o ON o.user_id = u.id;   -- users without orders keep o.id = NULL
```

## Three-valued logic
- id: three-valued-logic
- one-liner: In SQL a condition is true, false, or unknown (NULL), and WHERE only keeps the true ones.

```sql
SELECT NULL = NULL;     -- NULL, not true
SELECT 1 WHERE NULL;    -- no row
SELECT * FROM t WHERE x IS NULL;  -- the right way to test
```

## Aggregation
- id: aggregation
- one-liner: Grouping folds many rows into one per key; WHERE filters rows before, HAVING filters groups after.

```sql
SELECT user_id, COUNT(*) AS n
FROM orders
WHERE status = 'paid'        -- rows first
GROUP BY user_id
HAVING COUNT(*) > 5;         -- then groups
```

## B-tree indexes
- id: btree-indexes
- one-liner: An index is a sorted copy of some columns, so finding a value takes a few steps instead of reading every row.

```sql
CREATE INDEX idx_orders_user_date ON orders (user_id, created_at);
-- helps: WHERE user_id = 7 AND created_at > '2026-01-01'
-- helps: WHERE user_id = 7
-- does not help much: WHERE created_at > '2026-01-01'  (leftmost column missing)
```

## Transactions
- id: transactions
- one-liner: A transaction makes several changes all-or-nothing, and hides half-done work from other sessions.

```sql
BEGIN;
UPDATE accounts SET balance = balance - 100 WHERE id = 1;
UPDATE accounts SET balance = balance + 100 WHERE id = 2;
COMMIT;   -- or ROLLBACK, and neither update happened
```
