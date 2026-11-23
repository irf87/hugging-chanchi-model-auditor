#!/usr/bin/env bash
set -euo pipefail

cat > README.md <<'EOF'
# Demo App

Project using shared global workflows.
EOF

cat > AGENTS.md <<'EOF'
# Project Rules

Follow `skill-chanchi-global-release-checklist` before tagging a release.
EOF

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"
git add .
git commit -q -m "Initial repository"

chanchi sync init > /dev/null
chanchi project register --name demo-app > /dev/null

SKILL_DIR="$CHANCHI_SYNC/ITEMS/skills/skill-chanchi-global-release-checklist"
mkdir -p "$SKILL_DIR"

cat > "$SKILL_DIR/SKILL.md" <<'EOF'
---
name: skill-chanchi-global-release-checklist
description: Standard release checklist before tagging a version.
metadata:
  version: "0.1.0"
  status: "published"
---

# Release Checklist

1. Confirm `git status` is clean.
2. Run the repository check command and record the last line.
EOF

cat > "$SKILL_DIR/CHANGELOG.md" <<'EOF'
# Changelog

## 0.1.0 — 2026-11-20

- Initial published version.
EOF

ITEM_HASH="$(chanchi items list | python3 -c "import json, sys; items = json.load(sys.stdin)['items']; print(next(i['hash'] for i in items if i['name'] == 'skill-chanchi-global-release-checklist'))")"
printf "\nPublished: 2026-11-20 · audit 1 · audited %s · sha256 %s\n" "$ITEM_HASH" "$ITEM_HASH" >> "$SKILL_DIR/CHANGELOG.md"

chanchi models add --agent claude --model sonnet --cost 2 --efforts low,medium,high > /dev/null
chanchi models add --agent agy --model gemini-4-neon-high --cost 2 --efforts high > /dev/null
chanchi models add --agent opencode --model opencode-go/minimax-m3 --cost 2 > /dev/null
chanchi models add --agent agy --model gemini-4-hydrogen-high --cost 2 --efforts high > /dev/null

FAKEBIN="$(mktemp -d)"
for bin in claude agy opencode; do
  printf '#!/bin/sh\nexit 0\n' > "$FAKEBIN/$bin"
  chmod +x "$FAKEBIN/$bin"
done

COMMIT_SHA="$(git rev-parse HEAD)"
AUDIT_ID="$(PATH="$FAKEBIN:$PATH" chanchi audit open --kind adoption --ref demo-app:skill-chanchi-global-release-checklist --author claude:sonnet:medium --commit "$COMMIT_SHA" --project demo-app | python3 -c "import json, sys; print(json.load(sys.stdin)['audit_id'])")"
rm -rf "$FAKEBIN"

chanchi audit vote "$AUDIT_ID" --round 1 --seat 1 --verdict pass --blocking 0 --major 0 --minor 0 --report r1.md > /dev/null
chanchi audit vote "$AUDIT_ID" --round 1 --seat 2 --verdict pass --blocking 0 --major 0 --minor 0 --report r2.md > /dev/null
chanchi audit vote "$AUDIT_ID" --round 1 --seat 3 --verdict pass --blocking 0 --major 0 --minor 0 --report r3.md > /dev/null
chanchi audit close "$AUDIT_ID" --round 1 > /dev/null

chanchi items decide skill-chanchi-global-release-checklist --decision adopt --version 0.1.0 --reason "adopted initially" --audit "$AUDIT_ID" --project demo-app > /dev/null
chanchi items retire skill-chanchi-global-release-checklist --reason "superseded by local release rules" > /dev/null
chanchi items scan > /dev/null
chanchi items inbox > /dev/null
