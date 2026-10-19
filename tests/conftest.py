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
