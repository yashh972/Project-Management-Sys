-- In-app notification center (SQLite)
CREATE TABLE IF NOT EXISTS notification (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  user_id INTEGER NOT NULL,
  actor_id INTEGER DEFAULT NULL,
  issue_id INTEGER DEFAULT NULL,
  kind TEXT NOT NULL DEFAULT 'issue',
  message TEXT NOT NULL,
  url TEXT DEFAULT NULL,
  created_date DATETIME NOT NULL,
  read_date DATETIME DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS notification_user_unread ON notification (user_id, read_date, created_date);
CREATE INDEX IF NOT EXISTS notification_issue ON notification (issue_id);

UPDATE config SET value = '26.10.30' WHERE attribute = 'version';
