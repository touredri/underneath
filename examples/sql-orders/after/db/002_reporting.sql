CREATE INDEX idx_orders_user_created ON orders (user_id, created_at);

CREATE VIEW user_order_stats AS
SELECT
  u.id AS user_id,
  u.name,
  COUNT(o.id) AS order_count,
  COALESCE(SUM(o.total), 0) AS lifetime_value
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE o.status = 'paid'
GROUP BY u.id, u.name;

CREATE VIEW top_customers AS
SELECT
  user_id,
  name,
  lifetime_value,
  RANK() OVER (ORDER BY lifetime_value DESC) AS rank
FROM user_order_stats
WHERE lifetime_value > 0;
