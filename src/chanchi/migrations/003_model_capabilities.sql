CREATE TABLE model_capabilities (
  model_id    INTEGER NOT NULL REFERENCES models(id),
  capability  TEXT NOT NULL,
  value       TEXT NOT NULL,      -- 'yes' | 'no', validated in taxonomy.py, no CHECK
  set_at      TEXT NOT NULL,
  PRIMARY KEY (model_id, capability)
);
