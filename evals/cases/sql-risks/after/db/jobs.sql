CREATE VIEW active_users AS
SELECT id, email FROM users WHERE deleted_at = NULL;

CREATE VIEW never_ordered AS
SELECT id FROM users WHERE id NOT IN (SELECT user_id FROM orders);

UPDATE users SET email = lower(email);

DELETE FROM sessions;
