CREATE VIEW monthly_revenue AS
WITH monthly AS (
  SELECT c.country, DATE_TRUNC('month', o.created_at) AS month, SUM(o.amount) AS revenue
  FROM orders o
  JOIN customers c ON c.id = o.customer_id
  GROUP BY c.country, DATE_TRUNC('month', o.created_at)
)
SELECT country, month, revenue,
       revenue - LAG(revenue) OVER (PARTITION BY country ORDER BY month) AS growth
FROM monthly;

CREATE VIEW big_customers AS
SELECT DISTINCT c.name
FROM customers c
WHERE c.id IN (SELECT customer_id FROM orders WHERE amount > 1000)
UNION
SELECT name FROM customers WHERE country = 'FR';
