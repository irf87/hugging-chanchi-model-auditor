-- 004_lessons: project registration and the lessons store (continuous improvement, stage 1).
-- No seed rows: the default writer role is applied in code. Enum sets (target_kind, generality,
-- severity, status, reason_code, site state, locator kind) are validated in taxonomy.py and
-- lessons.py, not in CHECK constraints, so they can change without rebuilding a table.

ALTER TABLE projects ADD COLUMN registered_at TEXT;

CREATE TABLE project_locators (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER NOT NULL REFERENCES projects(id),
  kind        TEXT NOT NULL,            -- 'path' in stages 1-4 (validated in taxonomy)
  value       TEXT NOT NULL,            -- canonical absolute path (symlinks resolved)
  created_at  TEXT NOT NULL,
  UNIQUE (kind, value)
);

CREATE TABLE writer_roles (
  id          INTEGER PRIMARY KEY,
  project_id  INTEGER REFERENCES projects(id),   -- NULL = global scope
  role        TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX writer_roles_scope ON writer_roles (COALESCE(project_id, 0), role);

CREATE TABLE lessons (
  id                        INTEGER PRIMARY KEY,
  origin_project_id         INTEGER REFERENCES projects(id),   -- NULL = global origin
  author_role               TEXT NOT NULL,
  author_agent              TEXT NOT NULL,
  author_model_raw          TEXT NOT NULL,
  author_model_id           INTEGER REFERENCES models(id),
  author_effort             TEXT,
  author_conversation       TEXT NOT NULL,
  git_head                  TEXT,
  change_id                 INTEGER REFERENCES changes(id),
  session_id                INTEGER REFERENCES sessions(id),
  target_kind               TEXT NOT NULL,
  target                    TEXT NOT NULL,
  what_happened             TEXT NOT NULL,
  evidence                  TEXT NOT NULL,
  cause                     TEXT NOT NULL,
  prevention                TEXT NOT NULL,
  proposal                  TEXT NOT NULL,
  general_rule              TEXT NOT NULL,
  generality                TEXT NOT NULL,
  severity                  TEXT NOT NULL,
  particular_justification  TEXT,
  occurrences               INTEGER NOT NULL DEFAULT 1 CHECK (occurrences >= 1),
  tags                      TEXT NOT NULL DEFAULT '',
  status                    TEXT NOT NULL DEFAULT 'pending',
  reviewed_at               TEXT,
  reviewed_by_role          TEXT,
  review_conversation       TEXT,
  decision_reason           TEXT,
  reason_code               TEXT,
  duplicate_of              INTEGER REFERENCES lessons(id),
  created_at                TEXT NOT NULL,
  updated_at                TEXT NOT NULL,
  CHECK (length(trim(what_happened)) > 0 AND length(trim(evidence)) > 0
         AND length(trim(cause)) > 0 AND length(trim(prevention)) > 0
         AND length(trim(proposal)) > 0 AND length(trim(general_rule)) > 0
         AND length(trim(target)) > 0),
  CHECK (generality <> 'particular'
         OR (severity IN ('high', 'critical')
             AND particular_justification IS NOT NULL
             AND length(trim(particular_justification)) > 0)),
  CHECK (status <> 'duplicate' OR (duplicate_of IS NOT NULL AND duplicate_of <> id)),
  CHECK (status = 'pending' OR reviewed_at IS NOT NULL)
);

CREATE TABLE lesson_sites (
  id                    INTEGER PRIMARY KEY,
  lesson_id             INTEGER NOT NULL REFERENCES lessons(id),
  site                  TEXT NOT NULL,                       -- 'global' | 'project'
  project_id            INTEGER REFERENCES projects(id),
  state                 TEXT NOT NULL,                       -- applied | declined | not_applicable | retired
  where_                TEXT,
  reason                TEXT,
  decided_conversation  TEXT NOT NULL,
  decided_at            TEXT NOT NULL,
  CHECK ((site = 'global' AND project_id IS NULL) OR (site = 'project' AND project_id IS NOT NULL)),
  CHECK (state NOT IN ('applied', 'retired') OR (where_ IS NOT NULL AND length(trim(where_)) > 0))
);
CREATE UNIQUE INDEX lesson_sites_place ON lesson_sites (lesson_id, site, COALESCE(project_id, 0));

CREATE TABLE lesson_replaces (
  lesson_id    INTEGER NOT NULL REFERENCES lessons(id),
  replaced_id  INTEGER NOT NULL REFERENCES lessons(id),
  PRIMARY KEY (lesson_id, replaced_id),
  CHECK (lesson_id <> replaced_id)
);

CREATE TABLE lesson_incidents (
  lesson_id    INTEGER NOT NULL REFERENCES lessons(id),
  incident_id  INTEGER NOT NULL REFERENCES incidents(id),
  PRIMARY KEY (lesson_id, incident_id)
);

CREATE TABLE lesson_events (
  id               INTEGER PRIMARY KEY,
  lesson_id        INTEGER NOT NULL REFERENCES lessons(id),
  site             TEXT,                                   -- 'global' | 'project' | NULL
  site_project_id  INTEGER REFERENCES projects(id),       -- set when site = 'project'
  at            TEXT NOT NULL,
  actor_role    TEXT NOT NULL,
  actor_agent   TEXT NOT NULL,
  conversation  TEXT NOT NULL,
  action        TEXT NOT NULL,
  from_state    TEXT,
  to_state      TEXT,
  note          TEXT NOT NULL DEFAULT ''
);

CREATE INDEX lessons_by_status     ON lessons (status, generality, severity);
CREATE INDEX lessons_by_origin     ON lessons (origin_project_id);
CREATE INDEX lesson_sites_by_place ON lesson_sites (site, project_id, state);
CREATE INDEX lesson_events_by_lesson ON lesson_events (lesson_id, id);
