#!/usr/bin/env bash
set -euo pipefail

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"

mkdir -p src
cat > src/calc.py <<'EOF'
def add(a, b):
    return 0
EOF

cat > check.sh <<'EOF'
#!/bin/sh
set -eu
python3 -c "import src.calc; assert src.calc.add(2, 3) == 5"
echo "all 1 checks passed"
EOF
chmod +x check.sh

cat > BRIEF.md <<'EOF'
# Brief — S1

Files owned: `src/calc.py`.
Tasks:
1. Implement `add(a, b)` in `src/calc.py`.
2. Run `sh check.sh`.
EOF

git add src/calc.py check.sh BRIEF.md
git commit -q -m "chore: initial"

chanchi project register --name demo-proj >/dev/null
chanchi models add --agent claude --model sonnet --cost 2 --efforts low,medium,high >/dev/null
chanchi change open demo-chg --kind adhoc --planner claude:sonnet:medium >/dev/null
chanchi session start demo-chg S1 --executor claude:sonnet:medium --task-type business-logic --complexity medium --tasks 2 >/dev/null

cat > src/calc.py <<'EOF'
def add(a, b):
    return a - b
EOF

cat > handoff.md <<'EOF'
# Report S1

Status: COMPLETE

Implemented `add(a, b)` in `src/calc.py`.

Verification:
- `sh check.sh` -> `all 1 checks passed`
EOF
