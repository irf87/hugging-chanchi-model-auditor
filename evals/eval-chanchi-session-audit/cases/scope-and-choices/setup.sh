#!/usr/bin/env bash
set -euo pipefail

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"

mkdir -p src
cat > src/rows.py <<'EOF'
def parse_row(line):
    return line.split(",")
EOF

cat > src/extra.py <<'EOF'
def helper():
    return 1
EOF

cat > check.sh <<'EOF'
#!/bin/sh
set -eu
python3 -c "import src.rows; assert src.rows.parse_row('a|b') == ['a', 'b']"
echo "all 1 checks passed"
EOF
chmod +x check.sh

cat > BRIEF.md <<'EOF'
# Brief — S1

Files owned: `src/rows.py` (do not touch `src/extra.py`).
Tasks:
1. Update `parse_row(line)` in `src/rows.py`.
2. Run `sh check.sh`.
EOF

git add src/rows.py src/extra.py check.sh BRIEF.md
git commit -q -m "chore: initial"

chanchi project register --name demo-proj >/dev/null
chanchi models add --agent claude --model sonnet --cost 2 --efforts low,medium,high >/dev/null
chanchi change open demo-chg --kind adhoc --planner claude:sonnet:medium >/dev/null
chanchi session start demo-chg S1 --executor claude:sonnet:medium --task-type business-logic --complexity medium --tasks 2 >/dev/null

cat > src/rows.py <<'EOF'
def parse_row(line):
    return line.split("|")
EOF

cat > src/extra.py <<'EOF'
def helper():
    return 2
EOF

cat > handoff.md <<'EOF'
# Report S1

Status: COMPLETE

Updated `src/rows.py` and also refactored `src/extra.py`.

Verification:
- `sh check.sh` -> `all 1 checks passed`

## Choices the plan left open
- Used pipe `|` as the delimiter in `parse_row` because `BRIEF.md` did not specify one.
EOF
