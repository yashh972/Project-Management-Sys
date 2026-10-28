-- Phase 0 intelligence-layer tables (SQLite)

CREATE TABLE IF NOT EXISTS model_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  model_name TEXT NOT NULL,
  version TEXT NOT NULL,
  trained_at DATETIME NOT NULL,
  train_start DATE DEFAULT NULL,
  train_end DATE DEFAULT NULL,
  rows_count INTEGER NOT NULL DEFAULT 0,
  metrics_json TEXT DEFAULT NULL,
  artifact_path TEXT DEFAULT NULL,
  dataset_hash TEXT DEFAULT NULL,
  is_active INTEGER NOT NULL DEFAULT 1,
  created_by INTEGER DEFAULT NULL,
  created_date DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS model_run_name_active ON model_run (model_name, is_active);
CREATE INDEX IF NOT EXISTS model_run_trained ON model_run (trained_at);

CREATE TABLE IF NOT EXISTS prediction (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  issue_id INTEGER NOT NULL,
  kind TEXT NOT NULL,
  model_run_id INTEGER DEFAULT NULL,
  value REAL DEFAULT NULL,
  p50 REAL DEFAULT NULL,
  p85 REAL DEFAULT NULL,
  explanation_json TEXT DEFAULT NULL,
  features_json TEXT DEFAULT NULL,
  features_hash TEXT DEFAULT NULL,
  computed_at DATETIME NOT NULL,
  expires_at DATETIME DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS prediction_issue_kind ON prediction (issue_id, kind, computed_at);
CREATE INDEX IF NOT EXISTS prediction_model ON prediction (model_run_id);

CREATE TABLE IF NOT EXISTS suggestion_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  user_id INTEGER DEFAULT NULL,
  issue_id INTEGER DEFAULT NULL,
  kind TEXT NOT NULL,
  payload_json TEXT DEFAULT NULL,
  model_run_id INTEGER DEFAULT NULL,
  shown_at DATETIME NOT NULL,
  action TEXT DEFAULT NULL,
  acted_at DATETIME DEFAULT NULL,
  outcome_json TEXT DEFAULT NULL,
  outcome_at DATETIME DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS suggestion_issue ON suggestion_log (issue_id, shown_at);
CREATE INDEX IF NOT EXISTS suggestion_user ON suggestion_log (user_id, shown_at);
CREATE INDEX IF NOT EXISTS suggestion_action ON suggestion_log (action);

CREATE TABLE IF NOT EXISTS forecast_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  sprint_id INTEGER NOT NULL,
  created_by INTEGER DEFAULT NULL,
  created_at DATETIME NOT NULL,
  simulations INTEGER NOT NULL DEFAULT 0,
  assumptions_json TEXT DEFAULT NULL,
  probability_on_time REAL DEFAULT NULL,
  p50_date DATE DEFAULT NULL,
  p85_date DATE DEFAULT NULL,
  p95_date DATE DEFAULT NULL,
  expected_days REAL DEFAULT NULL,
  drivers_json TEXT DEFAULT NULL,
  model_run_id INTEGER DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS forecast_sprint ON forecast_run (sprint_id, created_at);

CREATE TABLE IF NOT EXISTS assignment_run (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  sprint_id INTEGER DEFAULT NULL,
  issue_id INTEGER DEFAULT NULL,
  created_by INTEGER DEFAULT NULL,
  created_at DATETIME NOT NULL,
  objective TEXT DEFAULT NULL,
  constraints_json TEXT DEFAULT NULL,
  result_json TEXT DEFAULT NULL,
  baseline_json TEXT DEFAULT NULL,
  model_run_id INTEGER DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS assignment_sprint ON assignment_run (sprint_id, created_at);

CREATE TABLE IF NOT EXISTS assignment_item (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  run_id INTEGER NOT NULL,
  issue_id INTEGER NOT NULL,
  user_id INTEGER DEFAULT NULL,
  score REAL DEFAULT NULL,
  reason_json TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS assignment_item_run ON assignment_item (run_id);
CREATE INDEX IF NOT EXISTS assignment_item_issue ON assignment_item (issue_id);

CREATE TABLE IF NOT EXISTS user_skill (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  user_id INTEGER NOT NULL,
  skill TEXT NOT NULL,
  level INTEGER NOT NULL DEFAULT 3,
  created_date DATETIME NOT NULL,
  UNIQUE (user_id, skill)
);

CREATE TABLE IF NOT EXISTS user_availability (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  user_id INTEGER NOT NULL,
  date DATE NOT NULL,
  hours REAL NOT NULL DEFAULT 0,
  kind TEXT NOT NULL DEFAULT 'leave',
  note TEXT DEFAULT NULL,
  UNIQUE (user_id, date)
);

CREATE TABLE IF NOT EXISTS holiday (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  date DATE NOT NULL,
  name TEXT NOT NULL,
  UNIQUE (date)
);

CREATE TABLE IF NOT EXISTS git_installation (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  provider TEXT NOT NULL,
  installation_id TEXT NOT NULL,
  account TEXT DEFAULT NULL,
  token_enc TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL,
  UNIQUE (provider, installation_id)
);

CREATE TABLE IF NOT EXISTS issue_link (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  issue_id INTEGER NOT NULL,
  provider TEXT NOT NULL,
  repo TEXT NOT NULL,
  kind TEXT NOT NULL,
  external_id TEXT NOT NULL,
  url TEXT DEFAULT NULL,
  state TEXT DEFAULT NULL,
  meta_json TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL,
  UNIQUE (provider, kind, external_id)
);
CREATE INDEX IF NOT EXISTS issue_link_issue ON issue_link (issue_id);

CREATE TABLE IF NOT EXISTS dora_event (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  repo TEXT NOT NULL,
  kind TEXT NOT NULL,
  external_id TEXT NOT NULL,
  occurred_at DATETIME NOT NULL,
  value REAL DEFAULT NULL,
  meta_json TEXT DEFAULT NULL,
  UNIQUE (repo, kind, external_id)
);
CREATE INDEX IF NOT EXISTS dora_event_time ON dora_event (occurred_at);

CREATE TABLE IF NOT EXISTS audit_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  workspace_id INTEGER DEFAULT NULL,
  actor_id INTEGER DEFAULT NULL,
  action TEXT NOT NULL,
  entity TEXT NOT NULL,
  entity_id TEXT DEFAULT NULL,
  before_json TEXT DEFAULT NULL,
  after_json TEXT DEFAULT NULL,
  ip TEXT DEFAULT NULL,
  user_agent TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL,
  hash_prev TEXT DEFAULT NULL,
  hash TEXT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS audit_created ON audit_log (created_at);
CREATE INDEX IF NOT EXISTS audit_entity ON audit_log (entity, entity_id);

CREATE TABLE IF NOT EXISTS job (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  queue TEXT NOT NULL DEFAULT 'default',
  payload_json TEXT NOT NULL,
  status TEXT NOT NULL DEFAULT 'queued',
  attempts INTEGER NOT NULL DEFAULT 0,
  available_at DATETIME NOT NULL,
  locked_at DATETIME DEFAULT NULL,
  error TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL,
  updated_at DATETIME NOT NULL
);
CREATE INDEX IF NOT EXISTS job_queue_status ON job (queue, status, available_at);

CREATE TABLE IF NOT EXISTS event_outbox (
  id INTEGER PRIMARY KEY AUTOINCREMENT NOT NULL,
  type TEXT NOT NULL,
  payload_json TEXT NOT NULL,
  created_at DATETIME NOT NULL,
  published_at DATETIME DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS event_outbox_pending ON event_outbox (published_at, created_at);

ALTER TABLE issue ADD COLUMN version INTEGER NOT NULL DEFAULT 1;

CREATE INDEX IF NOT EXISTS issue_status_owner ON issue (status, owner_id);
CREATE INDEX IF NOT EXISTS issue_sprint_status ON issue (sprint_id, status);
CREATE INDEX IF NOT EXISTS issue_due_status ON issue (due_date, status);

UPDATE config SET value = '26.10.28' WHERE attribute = 'version';
