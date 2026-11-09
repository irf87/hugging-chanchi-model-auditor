-- 002_more_task_types: two more task types (architecture design, unit tests).
-- INSERT OR IGNORE so a database that already holds one of these codes keeps its own row.

INSERT OR IGNORE INTO task_types (code, description) VALUES
  ('architecture-design', 'Define or change module boundaries, layering, dependency direction or public interfaces'),
  ('unit-tests', 'Write or repair isolated unit tests (use tests for integration, device or end-to-end work)');
