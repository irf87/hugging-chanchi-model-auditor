#!/usr/bin/env bash
set -euo pipefail

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"

mkdir -p src
cat > src/sort.py <<'EOF'
def sort_items(items):
    return list(items)
EOF

cat > design.md <<'EOF'
# Design

Add `sort_items(items)` to return the items in sorted order.
EOF

cat > BRIEF.md <<'EOF'
# Brief — S1

Tasks:
1. Read `design.md`.
2. Update `src/sort.py` to implement `sort_items(items)`.
3. Verify the output order.
EOF

git add src/sort.py design.md BRIEF.md
git commit -q -m "chore: initial"

chanchi project register --name demo-proj >/dev/null
chanchi models add --agent claude --model sonnet --cost 2 --efforts low,medium,high >/dev/null
chanchi change open demo-chg --kind adhoc --planner claude:sonnet:medium >/dev/null
chanchi session start demo-chg S1 --executor claude:sonnet:medium --task-type business-logic --complexity medium --tasks 3 >/dev/null

cat > handoff.md <<'EOF'
# Report S1

Status: STOPPED
Task: 3

Stopped at task 3 because `design.md` does not define the sort order for items (ascending by name or by id). No files were modified.
EOF
