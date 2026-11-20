"""Guard the harness entry points described in AGENTS.md § Harness Entry Points."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAX_WRAPPER_LINES = 20


def test_agents_md_is_the_source_of_truth():
    assert (ROOT / "AGENTS.md").is_file()


def test_claude_md_imports_agents_md_first():
    lines = (ROOT / "CLAUDE.md").read_text().splitlines()
    assert lines[0].strip() == "@AGENTS.md"


def test_claude_md_stays_a_thin_wrapper():
    lines = (ROOT / "CLAUDE.md").read_text().splitlines()
    assert len(lines) <= MAX_WRAPPER_LINES, "move shared rules to AGENTS.md"


def test_no_gemini_md():
    # Antigravity loads AGENTS.md natively; a GEMINI.md would be a second source.
    assert not (ROOT / "GEMINI.md").exists()
