#!/usr/bin/env bash
set -euo pipefail

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"

echo "demo" > README.md
git add README.md
git commit -q -m "chore: initial"

chanchi project register --name demo-proj >/dev/null

cat > notes.md <<'EOF'
# Session notes

Session S1 of change demo-chg completed all 3 tasks cleanly.
Every verification command ran and reproduced on audit with no rework and no rule violations.
EOF
