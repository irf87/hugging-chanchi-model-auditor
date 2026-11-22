-- 005_audits_and_families: model families and the redundant-audit store (global items, phase 1).
-- Design: docs/designs/global-items.md, "Data model (migration 005)". The lessons design reserved
-- 005 for its stage 3; that stage is not built, so it takes the next free number when it is.
-- Enum sets (subject kind, verdict, severity, decision, outcome, escalation, seat status) are
-- validated in taxonomy.py, not in CHECK constraints. models.family is seeded below with the same
-- rule as taxonomy.family_for(): the last slash-separated segment of the model id, lowercased,
-- matched by prefix. tests/test_db.py holds the two implementations equal.

ALTER TABLE models ADD COLUMN family TEXT;

WITH RECURSIVE seg(id, s) AS (
  SELECT id, lower(model) FROM models
  UNION ALL
  SELECT id, substr(s, instr(s, '/') + 1) FROM seg WHERE instr(s, '/') > 0
)
UPDATE models SET family = (
  SELECT CASE
    WHEN s LIKE 'claude%' OR s LIKE 'opus%' OR s LIKE 'sonnet%' OR s LIKE 'haiku%'
      OR s LIKE 'fable%' THEN 'anthropic'
    WHEN s LIKE 'gemini%' THEN 'google'
    WHEN s LIKE 'gpt%' THEN 'openai'
    WHEN s LIKE 'minimax%' THEN 'minimax'
    WHEN s LIKE 'deepseek%' THEN 'deepseek'
    WHEN s LIKE 'glm%' THEN 'zhipu'
    WHEN s LIKE 'kimi%' THEN 'moonshot'
    WHEN s LIKE 'qwen%' THEN 'alibaba'
    WHEN s LIKE 'grok%' THEN 'xai'
    WHEN s LIKE 'mimo%' THEN 'xiaomi'
    ELSE NULL
  END
  FROM seg WHERE seg.id = models.id AND instr(seg.s, '/') = 0
);

CREATE TABLE audits (
  id           INTEGER PRIMARY KEY,
  subject_kind TEXT NOT NULL,
  subject_ref  TEXT NOT NULL,
  project_id   INTEGER REFERENCES projects(id),
  change_id    INTEGER REFERENCES changes(id),
  author_raw   TEXT NOT NULL,
  author_model_id INTEGER REFERENCES models(id),
  outcome      TEXT,
  opened_at    TEXT NOT NULL,
  closed_at    TEXT
);

CREATE TABLE audit_rounds (
  id          INTEGER PRIMARY KEY,
  audit_id    INTEGER NOT NULL REFERENCES audits(id),
  round       INTEGER NOT NULL CHECK (round BETWEEN 1 AND 3),
  subject_at  TEXT NOT NULL,
  degraded    INTEGER NOT NULL DEFAULT 0,
  outcome     TEXT,
  escalation  TEXT,
  opened_at   TEXT NOT NULL,
  closed_at   TEXT,
  UNIQUE (audit_id, round)
);

CREATE TABLE audit_seats (
  id          INTEGER PRIMARY KEY,
  round_id    INTEGER NOT NULL REFERENCES audit_rounds(id),
  seat        INTEGER NOT NULL CHECK (seat BETWEEN 1 AND 3),
  model_id    INTEGER NOT NULL REFERENCES models(id),
  effort      TEXT,
  status      TEXT NOT NULL,
  verdict     TEXT,
  blocking    INTEGER NOT NULL DEFAULT 0,
  major       INTEGER NOT NULL DEFAULT 0,
  minor       INTEGER NOT NULL DEFAULT 0,
  report      TEXT,
  reason      TEXT,
  created_at  TEXT NOT NULL,
  updated_at  TEXT NOT NULL
);
CREATE UNIQUE INDEX audit_seats_active ON audit_seats (round_id, seat) WHERE status != 'unavailable';

CREATE TABLE audit_dissents (
  id          INTEGER PRIMARY KEY,
  seat_id     INTEGER NOT NULL REFERENCES audit_seats(id),
  finding     TEXT NOT NULL,
  severity    TEXT NOT NULL,
  decision    TEXT NOT NULL,
  evidence    TEXT NOT NULL,
  created_at  TEXT NOT NULL
);
