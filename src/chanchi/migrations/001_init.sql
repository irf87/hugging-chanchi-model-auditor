-- 001_init: initial schema plus seed rows (human planner, task types).

CREATE TABLE models (
  id          INTEGER PRIMARY KEY,
  agent       TEXT NOT NULL,
  model       TEXT NOT NULL,
  cost_tier   INTEGER NOT NULL CHECK (cost_tier BETWEEN 1 AND 3),
  efforts     TEXT,
  active      INTEGER NOT NULL DEFAULT 1,
  notes       TEXT,
  created_at  TEXT NOT NULL,
  UNIQUE (agent, model)
);

CREATE TABLE projects (
  id          INTEGER PRIMARY KEY,
  slug        TEXT NOT NULL UNIQUE,
  path        TEXT,
  created_at  TEXT NOT NULL
);

CREATE TABLE task_types (
  code        TEXT PRIMARY KEY,
  description TEXT NOT NULL
);

CREATE TABLE changes (
  id                    INTEGER PRIMARY KEY,
  project_id            INTEGER NOT NULL REFERENCES projects(id),
  ref                   TEXT NOT NULL,
  kind                  TEXT NOT NULL,
  planner_model_id      INTEGER NOT NULL REFERENCES models(id),
  planner_effort        TEXT,
  orchestrator_model_id INTEGER NOT NULL REFERENCES models(id),
  orchestrator_effort   TEXT,
  opened_at             TEXT NOT NULL,
  closed_at             TEXT,
  UNIQUE (project_id, ref)
);

CREATE TABLE sessions (
  id                INTEGER PRIMARY KEY,
  change_id         INTEGER NOT NULL REFERENCES changes(id),
  session_ref       TEXT NOT NULL,
  attempt           INTEGER NOT NULL DEFAULT 1,
  retry_reason      TEXT,
  executor_model_id INTEGER NOT NULL REFERENCES models(id),
  executor_effort   TEXT,
  task_type         TEXT NOT NULL REFERENCES task_types(code),
  complexity        TEXT NOT NULL,
  tags              TEXT,
  groups            TEXT,
  tasks_total       INTEGER NOT NULL CHECK (tasks_total > 0),
  started_at        TEXT NOT NULL,
  ended_at          TEXT,
  reported_status   TEXT,
  verdict           TEXT,
  audited_at        TEXT,
  notes             TEXT,
  UNIQUE (change_id, session_ref, attempt)
);

CREATE TABLE incidents (
  id           INTEGER PRIMARY KEY,
  change_id    INTEGER NOT NULL REFERENCES changes(id),
  session_id   INTEGER REFERENCES sessions(id),
  code         TEXT NOT NULL,
  role         TEXT NOT NULL,
  severity     TEXT NOT NULL,
  task_ref     TEXT,
  detected_by  TEXT NOT NULL,
  description  TEXT NOT NULL,
  evidence     TEXT NOT NULL,
  created_at   TEXT NOT NULL,
  voided_at    TEXT,
  void_reason  TEXT
);

CREATE INDEX idx_changes_project ON changes(project_id);
CREATE INDEX idx_sessions_change ON sessions(change_id);
CREATE INDEX idx_incidents_change ON incidents(change_id);
CREATE INDEX idx_incidents_session ON incidents(session_id);

INSERT INTO models (agent, model, cost_tier, efforts, active, notes, created_at)
VALUES ('human', 'human', 1, NULL, 1, 'The human, as planner or orchestrator of adhoc changes', '2026-10-18T00:00:00Z');

INSERT INTO task_types (code, description) VALUES
  ('ui-component', 'Build or change a reusable or screen-level UI component'),
  ('ui-layout-styling', 'Layout, spacing, theming or styling with no new behaviour'),
  ('api-endpoint', 'Add or change an HTTP/RPC endpoint and its contract'),
  ('business-logic', 'Domain rules, use cases or application services'),
  ('db-schema-migration', 'Database schema, migrations or persistence mapping'),
  ('refactor', 'Restructure code without changing behaviour'),
  ('bugfix', 'Fix incorrect behaviour'),
  ('tests', 'Write or repair tests, including device or end-to-end passes'),
  ('infra-config-ci', 'Build, configuration, CI or tooling'),
  ('docs', 'Documentation, spec sync or archive steps'),
  ('integration', 'Integrate an external SDK, service or API');
