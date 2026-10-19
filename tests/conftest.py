import pytest


@pytest.fixture
def db_env(tmp_path, monkeypatch):
    """Point chanchi at a throwaway operational database."""
    path = tmp_path / "data" / "chanchi.db"
    monkeypatch.setenv("CHANCHI_DB", str(path))
    return path


@pytest.fixture
def conn(db_env):
    from chanchi import db

    connection = db.open_operational()
    yield connection
    connection.close()


@pytest.fixture
def git_repo(tmp_path, monkeypatch):
    """A temporary git repository named demo-app, used as the current directory."""
    import subprocess

    repo = tmp_path / "demo-app"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    monkeypatch.chdir(repo)
    return repo


@pytest.fixture
def seeded(conn):
    """The operational connection with a small model catalog."""
    from chanchi import catalog

    all_efforts = ["low", "medium", "high", "xhigh", "max"]
    catalog.add_model(conn, agent="claude", model="opus", cost_tier=3, efforts=all_efforts)
    catalog.add_model(conn, agent="claude", model="sonnet", cost_tier=2, efforts=all_efforts)
    catalog.add_model(conn, agent="claude", model="haiku", cost_tier=1, efforts=all_efforts)
    catalog.add_model(
        conn, agent="agy", model="gemini-3.8-flash-high", cost_tier=1, efforts=["low", "medium", "high"]
    )
    catalog.add_model(conn, agent="opencode", model="openrouter/qwen/qwen3-coder:free", cost_tier=1)
    return conn


@pytest.fixture
def recorder(seeded, git_repo):
    from helpers import Recorder

    return Recorder(seeded)
