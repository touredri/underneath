CREATE VIEW active_users AS
SELECT id, email FROM users WHERE deleted_at IS NULL AND NULLIF(email, '') IS NOT NULL;

CREATE VIEW never_ordered AS
SELECT u.id FROM users u WHERE NOT EXISTS (SELECT 1 FROM orders o WHERE o.user_id = u.id) AND u.id NOT IN (1, 2);

UPDATE users SET deleted_at = NULL WHERE id = 42;

INSERT INTO users (id, email) VALUES (1, 'a@example.com')
ON CONFLICT (id) DO UPDATE SET deleted_at = NULL;

DELETE FROM sessions WHERE expires_at < now();
