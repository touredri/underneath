---
stack: sql
languages: sql
---

# SQL concepts

Same format as `react.md`. Rules run on each statement's text, case-insensitively.

## Inner join
- id: sql.innerJoin
- detect: regex (?<!LEFT )(?<!RIGHT )(?<!FULL )(?<!OUTER )(?<!CROSS )\bJOIN\b
- fundamental: set-theory
- what: Keeps only the rows that have a match on both sides.
- pitfalls: Rows without a match silently disappear; joining on a non-unique column multiplies rows.
- relates: sql.outerJoin

## Outer join
- id: sql.outerJoin
- detect: regex \b(LEFT|RIGHT|FULL)(\s+OUTER)?\s+JOIN\b
- fundamental: set-theory
- what: Keeps every row of one side, filling the other side with NULL when there is no match.
- pitfalls: A `WHERE` condition on the right table turns a LEFT JOIN back into an inner join; put it in `ON` instead.
- relates: sql.null

## LEFT JOIN undone by WHERE
- id: sql.leftJoinWhere
- risk: yes
- detect: regex \bLEFT\s+(?:OUTER\s+)?JOIN\s+[\w.]+\s+(?:AS\s+)?(\w+)\b[\s\S]*?\bWHERE\b[^;]*?\b\1\.\w+\s*(?:=|<>|!=|>|<|\bIN\b|\bLIKE\b)
- fundamental: three-valued-logic
- what: A WHERE condition on the optional side of a LEFT JOIN removes the rows where that side is NULL.
- pitfalls: The query silently becomes an inner join; rows the LEFT JOIN was meant to keep disappear. Move the condition into ON.
- relates: sql.outerJoin, sql.null

## Aggregation
- id: sql.aggregation
- detect: regex \bGROUP\s+BY\b
- detect: regex \b(COUNT|SUM|AVG|MIN|MAX)\s*\(
- fundamental: aggregation
- what: Collapses many rows into one per group and computes totals, counts or averages.
- pitfalls: Filtering aggregates needs `HAVING`, not `WHERE`; `COUNT(column)` skips NULLs, `COUNT(*)` does not.
- relates: sql.window

## Window functions
- id: sql.window
- detect: regex \bOVER\s*\(
- fundamental: aggregation
- what: Computes over a set of related rows (rank, running total) without collapsing them.
- pitfalls: Forgetting `PARTITION BY` computes over the whole table; frame defaults differ between `ROWS` and `RANGE`.
- relates: sql.aggregation

## Common table expressions
- id: sql.cte
- detect: regex ^\s*WITH\b
- detect: regex \bWITH\s+RECURSIVE\b
- fundamental: set-theory
- what: Names an intermediate result with `WITH name AS (...)` so the query reads top to bottom.
- pitfalls: A recursive CTE without a stopping condition never ends.
- relates: sql.subquery

## Subqueries
- id: sql.subquery
- detect: regex (?<!\bAS\s)(?<!\bAS)\(\s*SELECT\b
- fundamental: set-theory
- what: A query inside another query, used as a value, a list or a table.
- pitfalls: A correlated subquery runs once per outer row and can be very slow; `NOT IN` with a NULL in the list returns nothing.
- relates: sql.cte, sql.null

## NULL handling
- id: sql.null
- detect: regex \bIS\s+(NOT\s+)?NULL\b
- detect: regex \b(COALESCE|NULLIF|IFNULL)\s*\(
- fundamental: three-valued-logic
- what: NULL means unknown; any comparison with it is unknown, not true or false.
- pitfalls: `= NULL` never matches; use `IS NULL`. Arithmetic with NULL gives NULL.
- relates: sql.outerJoin

## Indexes
- id: sql.index
- detect: regex \bCREATE\s+(UNIQUE\s+)?INDEX\b
- fundamental: btree-indexes
- what: A sorted structure that lets the database find rows without scanning the whole table.
- pitfalls: Column order matters in a multi-column index; every index slows writes; a function on the column (`LOWER(email)`) skips a plain index.
- relates: sql.foreignKey

## Foreign keys
- id: sql.foreignKey
- detect: regex \bREFERENCES\b
- fundamental: set-theory
- what: Guarantees that a value points to an existing row in another table.
- pitfalls: Foreign key columns are not indexed automatically in PostgreSQL; `ON DELETE CASCADE` can delete far more than expected.
- relates: sql.index

## Comparison with NULL
- id: sql.equalsNull
- detect: regex \b(WHERE|HAVING|WHEN|JOIN)\b(?:(?!\bSET\b)[^;])*?(?<![<>!=:])(?:=|<>|!=)\s*NULL\b
- risk: yes
- fundamental: three-valued-logic
- what: `x = NULL` is never true, not even when x is NULL: the comparison is unknown.
- pitfalls: The filter silently matches nothing. Use `IS NULL` / `IS NOT NULL`.
- relates: sql.null

## NOT IN with a subquery
- id: sql.notInNull
- detect: regex \bNOT\s+IN\s*\(\s*SELECT\b
- risk: yes
- fundamental: three-valued-logic
- what: Keeps rows whose value is not in the subquery's result.
- pitfalls: If the subquery returns a single NULL, NOT IN is unknown for every row and the query returns nothing. Use `NOT EXISTS`, or filter the NULLs out.
- relates: sql.subquery, sql.null

## UPDATE or DELETE without WHERE
- id: sql.updateNoWhere
- detect: regex \bUPDATE\s+[\w."]+\s+SET\b(?![^;]*\bWHERE\b)
- detect: regex \bDELETE\s+FROM\s+[\w."]+(?![^;]*\bWHERE\b)
- risk: yes
- fundamental: transactions
- what: Changes or deletes every row of the table.
- pitfalls: Usually a forgotten WHERE. If it is intended (a migration), say so; run it in a transaction you can roll back.
- relates: sql.transaction

## Constraints
- id: sql.constraints
- detect: regex \b(PRIMARY\s+KEY|UNIQUE|CHECK\s*\(|(?<!\bIS\s)NOT\s+NULL)\b
- fundamental: set-theory
- what: Rules the database enforces on every write, whatever the application does.
- pitfalls: Adding a constraint to a large table can lock it while existing rows are checked.
- relates: sql.foreignKey

## Upsert
- id: sql.upsert
- detect: regex \bON\s+CONFLICT\b
- detect: regex \bMERGE\s+INTO\b
- detect: regex \bON\s+DUPLICATE\s+KEY\b
- fundamental: transactions
- what: Inserts a row, or updates it if it already exists, in one atomic statement.
- pitfalls: Needs a unique constraint on the conflict columns.
- relates: sql.constraints

## Transactions
- id: sql.transaction
- detect: regex \b(BEGIN|START\s+TRANSACTION|COMMIT|ROLLBACK)\b
- fundamental: transactions
- what: Groups statements so they all succeed or none do.
- pitfalls: Long transactions hold locks and block others; the default isolation level may still allow some anomalies.
- relates: sql.upsert

## Set operations
- id: sql.setOps
- detect: regex \bUNION(\s+ALL)?\b|\bINTERSECT\b|\bEXCEPT\b
- fundamental: set-theory
- what: Combines the results of two queries with the same columns.
- pitfalls: `UNION` removes duplicates (and sorts to do it); `UNION ALL` is faster when duplicates are fine.
- relates:

## Distinct
- id: sql.distinct
- detect: regex \bSELECT\s+DISTINCT\b
- fundamental: set-theory
- what: Removes duplicate rows from the result.
- pitfalls: Often hides a join that multiplies rows instead of fixing it.
- relates: sql.innerJoin
