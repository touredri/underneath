CREATE VIEW active_users AS
SELECT u.id, u.name, o.created_at
FROM users u
LEFT JOIN orders o ON o.user_id = u.id
WHERE o.status = 'paid';
