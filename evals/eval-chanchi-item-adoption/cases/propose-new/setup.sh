#!/usr/bin/env bash
set -euo pipefail

mkdir -p .agents/skills/release-checklist

cat > README.md <<'EOF'
# Demo App

Local release workflow project.
EOF

cat > AGENTS.md <<'EOF'
# Project Rules

Follow `.agents/skills/release-checklist/SKILL.md` before tagging a release.
EOF

cat > .agents/skills/release-checklist/SKILL.md <<'EOF'
---
name: release-checklist
description: Local release checklist before creating a git tag.
---

# Release Checklist

1. Confirm `git status` is clean.
2. Run `scripts/verify.sh` and record the last line.
3. Verify CHANGELOG.md has an entry for the new version.
EOF

git init -q
git config user.email "dev@example.com"
git config user.name "Dev"
git add .
git commit -q -m "Initial repository"

chanchi sync init > /dev/null
chanchi project register --name demo-app > /dev/null
chanchi items scan > /dev/null

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
3. Verify CHANGELOG.md has an entry for the new version.
EOF

cat > "$SKILL_DIR/CHANGELOG.md" <<'EOF'
# Changelog

## 0.1.0 — 2026-11-20

- Initial published version.
EOF

ITEM_HASH="$(chanchi items list | python3 -c "import json, sys; items = json.load(sys.stdin)['items']; print(next(i['hash'] for i in items if i['name'] == 'skill-chanchi-global-release-checklist'))")"
printf "\nPublished: 2026-11-20 · audit 1 · audited %s · sha256 %s\n" "$ITEM_HASH" "$ITEM_HASH" >> "$SKILL_DIR/CHANGELOG.md"

chanchi items check > /dev/null
chanchi items inbox > /dev/null
