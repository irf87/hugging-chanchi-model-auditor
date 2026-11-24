#!/usr/bin/env bash
set -euo pipefail

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"

echo "demo" > README.md
git add README.md
git commit -q -m "chore: initial"

chanchi project register --name demo-proj >/dev/null

chanchi lesson add --as planner --author claude:sonnet:medium --conversation conv-1 --json - >/dev/null <<'EOF'
{
  "what_happened": "An executor committed a 4 MB binary asset into the repository.",
  "evidence": "git show --stat showed assets/blob.bin (4.2 MB).",
  "cause": "Nothing blocked large binary files from being committed.",
  "prevention": "Reject commits containing files over 1 MB.",
  "proposal": "Add a line to the executor role: never commit a file over 1 MB.",
  "general_rule": "Never commit a file over 1 MB.",
  "target_kind": "role",
  "target": "role executor",
  "generality": "project",
  "severity": "medium"
}
EOF

chanchi lesson repeat 1 --as planner --author claude:sonnet:medium --conversation conv-2 --evidence "A second 2.5 MB archive was committed in S4." >/dev/null
