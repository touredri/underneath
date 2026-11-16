CREATE VIEW archived_users AS
SELECT id, email, deleted_at
FROM users
WHERE deleted_at IS NOT NULL;

CREATE VIEW contactable_users AS
SELECT id, COALESCE(phone, email) AS contact
FROM users
WHERE email IS NOT NULL;
