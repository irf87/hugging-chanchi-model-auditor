-- 006_items: the project item inventory, item proposals and adoption decisions (global items, phase 3).
-- Design: docs/designs/global-items.md, "Data model (migration 006)".
-- project_item_dirs, project_items and item_proposals are written from phase 3 on. item_decisions
-- stays empty until phase 4. Enum sets (project item kind, proposal status) are validated in
-- taxonomy.py, not in CHECK constraints.

CREATE TABLE project_item_dirs (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  path        TEXT NOT NULL,
  UNIQUE (project_id, path)
);

CREATE TABLE project_items (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  kind        TEXT NOT NULL,
  name        TEXT NOT NULL,
  path        TEXT NOT NULL,
  sha256      TEXT NOT NULL,
  lines       INTEGER NOT NULL,
  description TEXT,
  scanned_at  TEXT NOT NULL,
  UNIQUE (project_id, path)
);

CREATE INDEX project_items_name ON project_items (kind, name);

CREATE TABLE item_proposals (
  id             INTEGER PRIMARY KEY,
  kind           TEXT NOT NULL,
  name           TEXT NOT NULL,
  evidence       TEXT NOT NULL,
  uses           INTEGER NOT NULL,
  owner_promoted INTEGER NOT NULL DEFAULT 0,
  status         TEXT NOT NULL,
  global_item    TEXT,
  created_at     TEXT NOT NULL,
  updated_at     TEXT NOT NULL
);

CREATE UNIQUE INDEX item_proposals_open ON item_proposals (kind, name) WHERE status = 'open';

CREATE TABLE item_decisions (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  global_item TEXT NOT NULL,
  version     TEXT NOT NULL,
  hash        TEXT NOT NULL,
  decision    TEXT NOT NULL,
  local_item  TEXT,
  reason      TEXT NOT NULL,
  audit_id    INTEGER REFERENCES audits(id),
  decided_at  TEXT NOT NULL
);
