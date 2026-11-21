import importlib.util
import io
import json
import urllib.error
from pathlib import Path

SCRIPT_PATH = Path(__file__).resolve().parents[1] / "scripts" / "fetch_hf_benchmarks.py"


def _load_module():
    spec = importlib.util.spec_from_file_location("fetch_hf_benchmarks", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, body: bytes, status: int = 200):
        self._body = body
        self.status = status

    def read(self) -> bytes:
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _write_map(root: Path, models: dict) -> Path:
    map_path = root / "scripts" / "hf_model_map.json"
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps({"schema_version": 1, "models": models}), encoding="utf-8")
    return map_path


def test_directory_guard_refuses_wrong_directory(tmp_path, monkeypatch, capsys):
    mod = _load_module()
    other = tmp_path / "other"
    other.mkdir()
    monkeypatch.chdir(other)
    code = mod.main([], root=tmp_path)
    out, err = capsys.readouterr()
    assert code == 2
    assert out == ""
    assert str(tmp_path.resolve()) in err


def test_hub_response_mapping_and_token_headers(tmp_path, monkeypatch, capsys):
    mod = _load_module()
    monkeypatch.chdir(tmp_path)
    _write_map(
        tmp_path,
        {
            "opencode:opencode-go/glm-5.3": {"hf_repo": "zai-org/GLM-5.3", "match_quality": "exact"},
            "opencode:opencode-go/vision-x": {"hf_repo": "org/Vision-X", "match_quality": "exact"},
        },
    )

    sample_glm = {
        "_id": "123",
        "id": "zai-org/GLM-5.3",
        "pipeline_tag": "text-generation",
        "evalResults": [
            {
                "filename": ".eval_results/deep-swe.yaml",
                "verified": False,
                "data": {
                    "dataset": {"id": "datacurve/deep-swe", "task_id": "deep_swe"},
                    "value": 66.9,
                    "date": "2026-08-28T15:22:14.000Z",
                    "source": {"url": "https://huggingface.co/zai-org/GLM-5.3", "name": "Model Card"},
                },
            },
            {
                "filename": ".eval_results/terminal-bench-4.1.yaml",
                "verified": False,
                "data": {
                    "dataset": {"id": "harborframework/terminal-bench", "task_id": "terminalbench_4_1"},
                    "value": 41.2,
                    "date": "2026-11-03",
                    "notes": "ignored",
                    "source": {"url": "https://www.tbench.ai/", "name": "TBench", "user": "harborframework"},
                },
                "pullRequest": 35,
            },
            {"filename": ".eval_results/broken.yaml", "error": "Invalid YAML"},
            {"filename": ".eval_results/bad-val.yaml", "data": {"dataset": {"id": "x", "task_id": "y"}, "value": "n/a"}},
        ],
    }
    sample_vision = {"id": "org/Vision-X", "pipeline_tag": "image-text-to-text", "evalResults": []}
    seen_requests = []

    def fake_opener(req, timeout=None):
        seen_requests.append((req.full_url, dict(req.header_items()), timeout))
        if "GLM-5.3" in req.full_url:
            return _FakeResponse(json.dumps(sample_glm).encode("utf-8"))
        return _FakeResponse(json.dumps(sample_vision).encode("utf-8"))

    # Without HF_TOKEN: no Authorization header.
    monkeypatch.delenv("HF_TOKEN", raising=False)
    code = mod.main([], root=tmp_path, opener=fake_opener)
    out, _ = capsys.readouterr()
    assert code == 0
    assert "Authorization" not in seen_requests[0][1]
    assert seen_requests[0][1]["User-agent"] == "chanchi-hf-fetch"
    assert seen_requests[0][2] == 20

    summary = json.loads(out)
    assert summary["failed"] == 0
    assert summary["vision_candidates"] == ["opencode:opencode-go/vision-x"]
    assert summary["models"]["opencode:opencode-go/glm-5.3"]["rows"] == 2
    assert summary["models"]["opencode:opencode-go/glm-5.3"]["rows_changed"] == 2
    # Dry run writes nothing.
    snapshot_path = tmp_path / "src" / "chanchi" / "data" / "hf_snapshot.json"
    assert not snapshot_path.exists()

    # With HF_TOKEN set: sent in header, never leaked in stdout, stderr, or snapshot.
    seen_requests.clear()
    secret = "hf_secret_token_do_not_leak"
    monkeypatch.setenv("HF_TOKEN", secret)
    code = mod.main(["--write"], root=tmp_path, opener=fake_opener)
    out, err = capsys.readouterr()
    assert code == 0
    assert seen_requests[0][1]["Authorization"] == f"Bearer {secret}"
    assert secret not in out and secret not in err
    snapshot_text = snapshot_path.read_text(encoding="utf-8")
    assert secret not in snapshot_text

    snap = json.loads(snapshot_text)
    assert snap["schema_version"] == 1
    assert snap["models"]["opencode:opencode-go/glm-5.3"]["eval_rows"] == [
        {
            "dataset_id": "datacurve/deep-swe",
            "task_id": "deep_swe",
            "value": 66.9,
            "date": "2026-08-28T15:22:14.000Z",
            "source_name": "Model Card",
            "source_url": "https://huggingface.co/zai-org/GLM-5.3",
            "verified": False,
            "pull_request": None,
        },
        {
            "dataset_id": "harborframework/terminal-bench",
            "task_id": "terminalbench_4_1",
            "value": 41.2,
            "date": "2026-11-03",
            "source_name": "TBench",
            "source_url": "https://www.tbench.ai/",
            "verified": False,
            "pull_request": 35,
        },
    ]
    # Output is sorted and stable.
    assert snapshot_text == json.dumps(snap, indent=2, sort_keys=True) + "\n"


def test_failures_preserve_previous_rows_and_drop_unmapped(tmp_path, monkeypatch, capsys):
    mod = _load_module()
    monkeypatch.chdir(tmp_path)
    _write_map(
        tmp_path,
        {
            "opencode:opencode-go/r401": {"hf_repo": "org/R401", "match_quality": "exact"},
            "opencode:opencode-go/r404": {"hf_repo": "org/R404", "match_quality": "exact"},
            "opencode:opencode-go/rtimeout": {"hf_repo": "org/RTimeout", "match_quality": "exact"},
            "opencode:opencode-go/rbadjson": {"hf_repo": "org/RBadJson", "match_quality": "exact"},
            "opencode:opencode-go/rnewfail": {"hf_repo": "org/RNewFail", "match_quality": "exact"},
        },
    )
    snapshot_path = tmp_path / "src" / "chanchi" / "data" / "hf_snapshot.json"
    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    prev_row = {
        "dataset_id": "datacurve/deep-swe",
        "task_id": "deep_swe",
        "value": 55.0,
        "date": "2026-10-01",
        "source_name": "Old",
        "source_url": "https://example.com/old",
        "verified": False,
        "pull_request": None,
    }
    previous_snapshot = {
        "schema_version": 1,
        "generated_at": "2026-10-01T00:00:00Z",
        "models": {
            "opencode:opencode-go/r401": {
                "hf_repo": "org/R401",
                "match_quality": "exact",
                "fetched_at": "2026-10-01T00:00:00Z",
                "last_error": None,
                "pipeline_tag": "text-generation",
                "eval_rows": [prev_row],
            },
            "opencode:opencode-go/r404": {
                "hf_repo": "org/R404",
                "match_quality": "exact",
                "fetched_at": "2026-10-01T00:00:00Z",
                "last_error": None,
                "pipeline_tag": "text-generation",
                "eval_rows": [prev_row],
            },
            "opencode:opencode-go/rtimeout": {
                "hf_repo": "org/RTimeout",
                "match_quality": "exact",
                "fetched_at": "2026-10-01T00:00:00Z",
                "last_error": None,
                "pipeline_tag": "text-generation",
                "eval_rows": [prev_row],
            },
            "opencode:opencode-go/rbadjson": {
                "hf_repo": "org/RBadJson",
                "match_quality": "exact",
                "fetched_at": "2026-10-01T00:00:00Z",
                "last_error": None,
                "pipeline_tag": "text-generation",
                "eval_rows": [prev_row],
            },
            "opencode:opencode-go/removed": {
                "hf_repo": "org/Removed",
                "match_quality": "exact",
                "fetched_at": "2026-10-01T00:00:00Z",
                "last_error": None,
                "pipeline_tag": "text-generation",
                "eval_rows": [prev_row],
            },
        },
    }
    snapshot_path.write_text(json.dumps(previous_snapshot), encoding="utf-8")

    def failing_opener(req, timeout=None):
        url = req.full_url
        if "R401" in url:
            raise urllib.error.HTTPError(url, 401, "Unauthorized", {}, io.BytesIO(b""))
        if "R404" in url:
            raise urllib.error.HTTPError(url, 404, "Not Found", {}, io.BytesIO(b""))
        if "RTimeout" in url:
            raise TimeoutError("timed out")
        if "RBadJson" in url:
            return _FakeResponse(b"{bad json")
        return _FakeResponse(b"server error", status=500)

    code = mod.main(["--write"], root=tmp_path, opener=failing_opener)
    out, _ = capsys.readouterr()
    assert code == 1
    summary = json.loads(out)
    assert summary["failed"] == 5

    written = json.loads(snapshot_path.read_text(encoding="utf-8"))
    assert "opencode:opencode-go/removed" not in written["models"]
    assert written["generated_at"] != "2026-10-01T00:00:00Z"

    for key in ("opencode:opencode-go/r401", "opencode:opencode-go/r404", "opencode:opencode-go/rtimeout", "opencode:opencode-go/rbadjson"):
        entry = written["models"][key]
        assert entry["eval_rows"] == [prev_row]
        assert entry["fetched_at"] == "2026-10-01T00:00:00Z"
        assert entry["pipeline_tag"] == "text-generation"
        assert entry["last_error"]

    new_fail = written["models"]["opencode:opencode-go/rnewfail"]
    assert new_fail["eval_rows"] == []
    assert new_fail["pipeline_tag"] is None
    assert new_fail["fetched_at"] is None
    assert new_fail["last_error"]


def test_fetch_script_has_forbidden_imports_absent():
    source = SCRIPT_PATH.read_text(encoding="utf-8")
    for forbidden in ("subprocess", "sqlite3", "import chanchi", "from chanchi"):
        assert forbidden not in source, forbidden
