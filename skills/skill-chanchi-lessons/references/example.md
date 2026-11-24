# Example: recording a lesson

```bash
chanchi lesson add --as planner --author claude:opus:high --conversation <conversation-id-or-label> --json - <<'EOF'
{
  "what_happened": "An executor reported a passing test suite that had never run in its worktree.",
  "evidence": "Report S1 says 'pytest: 412 passed'. The audit re-ran pytest in the same worktree and got a collection error in tests/test_export.py.",
  "cause": "The session protocol asked for the verification result but not for the command and its output.",
  "prevention": "The executor's report must name the exact verification command and paste the last line it printed.",
  "proposal": "Add to the executor role: report each verification as the command plus its last output line.",
  "general_rule": "Report a verification result only with the exact command that produced it and that command's last output line.",
  "target_kind": "role",
  "target": "role executor",
  "generality": "project",
  "severity": "medium",
  "tags": ["verification", "reporting"]
}
EOF
```
