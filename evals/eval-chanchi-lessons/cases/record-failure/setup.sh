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

During change demo-chg (session S1), the executor's report claimed all checks passed.
When we re-ran `sh check.sh` in the worktree, it failed immediately with a syntax error.
The brief only asked for "verification results" and did not ask for the exact command and its last output line.
We fixed the syntax error in `src/app.py` and re-ran `sh check.sh` to green.
EOF
