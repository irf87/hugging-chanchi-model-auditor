#!/usr/bin/env bash
set -euo pipefail

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"

echo "demo" > README.md
git add README.md
git commit -q -m "chore: initial"

chanchi project register --name demo-proj >/dev/null

chanchi lesson add --as planner --author claude:sonnet:medium --conversation conv-prev --json - >/dev/null <<'EOF'
{
  "what_happened": "An executor reported passing checks that had never run in the worktree.",
  "evidence": "Report S1 said checks passed; re-running sh check.sh failed.",
  "cause": "The brief asked for verification results without requiring the exact command and last output line.",
  "prevention": "Require the exact command and last output line for every verification claim.",
  "proposal": "Add to the brief template: report each verification as the command plus its last output line.",
  "general_rule": "Require the exact command and last output line for every verification result.",
  "target_kind": "role",
  "target": "role executor",
  "generality": "project",
  "severity": "medium"
}
EOF

cat > notes.md <<'EOF'
# Session notes

In change demo-chg-2 (session S2), the executor's report again claimed all checks passed without running them.
Re-running `sh check.sh` failed. The brief still only asked for "verification results" without requiring the exact command and its last output line.
We fixed the bug and re-ran `sh check.sh` to green.
EOF
