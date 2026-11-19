import json
from pathlib import Path

import pytest

from chanchi import catalog, hfsignals, scoring

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "hf_snapshot_sample.json"


@pytest.fixture
def sample_snapshot(monkeypatch):
    monkeypatch.setattr(hfsignals, "SNAPSHOT_PATH", FIXTURE)
    snapshot, source = hfsignals.load_snapshot()
    assert source == "snapshot"
    return snapshot


@pytest.fixture
def hf_catalog(recorder):
    conn = recorder.conn
    tier1 = (
        "opencode-go/glm-5.3",
        "opencode-go/glm-5.2",
        "opencode-go/kimi-k3",
        "opencode-go/minimax-m3",
        "opencode-go/minimax-m3#thinking",
        "opencode-go/hy3",
        "opencode-go/longcat-2.0",
        "opencode-go/mimo-v2.5",
        "opencode-go/hy4",
        "opencode-go/unmapped-model",
    )
    for model in tier1:
        catalog.add_model(conn, agent="opencode", model=model, cost_tier=1)
    catalog.add_model(conn, agent="opencode", model="opencode-go/tier2-top", cost_tier=2)
    return recorder


def test_canonical_values_filtering_and_date_mean(sample_snapshot):
    values = hfsignals.canonical_values(sample_snapshot)
    # Timestamp 2026-08-28T15:22:14.000Z beats 2026-08-01; 2026-11-10 invalid rows (wrong_task, bad date, 0.669, 451) ignored.
    assert values[("zai-org/GLM-5.3", "datacurve/deep-swe", "deep_swe")] == pytest.approx(72.0)
    # Latest-date mean of 81 and 82.7 is 81.85.
    assert values[("zai-org/GLM-5.2", "harborframework/terminal-bench-2.1", "terminalbench_2_1")] == pytest.approx(81.85)
    # Proxy entry is not in canonical peer values.
    assert ("tencent/Hy4-preview", "datacurve/deep-swe", "deep_swe") not in values


def test_percentiles_ties_shared_repo_and_min_reporters(sample_snapshot):
    values = hfsignals.canonical_values(sample_snapshot)
    pct = hfsignals.percentiles(values)

    # Claw-Eval has only 3 peers (< HF_MIN_REPORTERS=5), so it is omitted.
    assert all(ds != "claw-eval/Claw-Eval" for _, ds, _ in pct)

    # deep-swe has 6 distinct exact/family repos (minimax-m3 and #thinking share one repo; proxy excluded).
    assert pct[("zai-org/GLM-5.3", "datacurve/deep-swe", "deep_swe")] == {"percentile": pytest.approx(1.0), "peers": 6}
    assert pct[("zai-org/GLM-5.2", "datacurve/deep-swe", "deep_swe")] == {"percentile": pytest.approx(0.7), "peers": 6}
    assert pct[("moonshotai/Kimi-K3", "datacurve/deep-swe", "deep_swe")] == {"percentile": pytest.approx(0.7), "peers": 6}
    assert pct[("MiniMaxAI/MiniMax-M3", "datacurve/deep-swe", "deep_swe")] == {"percentile": pytest.approx(0.4), "peers": 6}
    assert pct[("tencent/Hy3", "datacurve/deep-swe", "deep_swe")] == {"percentile": pytest.approx(0.2), "peers": 6}
    assert pct[("meituan-longcat/LongCat-2.0", "datacurve/deep-swe", "deep_swe")] == {"percentile": pytest.approx(0.0), "peers": 6}

    # Shared repo gives both catalog entries the same value and counts as one peer.
    sig_base = hfsignals.signal_for(sample_snapshot, "opencode", "opencode-go/minimax-m3", "bugfix")
    sig_think = hfsignals.signal_for(sample_snapshot, "opencode", "opencode-go/minimax-m3#thinking", "bugfix")
    assert sig_base["value"] == sig_think["value"] == pytest.approx(0.4)
    assert sig_base["benchmarks"][0]["peers"] == 6
    assert sig_think["benchmarks"][0]["peers"] == 6
    assert sig_base["match_quality"] == "exact"
    assert sig_think["match_quality"] == "family"


def test_signal_for_claw_eval_only_proxy_unmapped_and_no_signal_task(sample_snapshot):
    # Claw-Eval-only model gets value: None and benchmarks: [].
    mimo = hfsignals.signal_for(sample_snapshot, "opencode", "opencode-go/mimo-v2.5", "integration")
    assert mimo is not None
    assert mimo["signal"] == "tool-use"
    assert mimo["value"] is None
    assert mimo["benchmarks"] == []

    # Proxy entry gets value: None and benchmarks with peers: None.
    proxy = hfsignals.signal_for(sample_snapshot, "opencode", "opencode-go/hy4", "bugfix")
    assert proxy is not None
    assert proxy["match_quality"] == "proxy"
    assert proxy["value"] is None
    assert len(proxy["benchmarks"]) == 1
    assert proxy["benchmarks"][0]["peers"] is None

    # Task type with no signal -> None; unmapped model -> None.
    assert hfsignals.signal_for(sample_snapshot, "opencode", "opencode-go/glm-5.3", "ui-component") is None
    assert hfsignals.signal_for(sample_snapshot, "claude", "sonnet", "bugfix") is None


def test_allowlisted_fields_only_and_pull_request_flag(sample_snapshot):
    allowed_top = {"signal", "value", "hf_repo", "match_quality", "fetched_at", "verified", "benchmarks"}
    allowed_bench = {"dataset_id", "task_id", "value", "date", "pull_request", "peers"}

    for model in ("opencode-go/glm-5.3", "opencode-go/glm-5.2", "opencode-go/hy4"):
        task = "infra-config-ci" if model == "opencode-go/glm-5.2" else "bugfix"
        sig = hfsignals.signal_for(sample_snapshot, "opencode", model, task)
        assert set(sig) == allowed_top
        assert sig["verified"] is False
        for bench in sig["benchmarks"]:
            assert set(bench) == allowed_bench
        serialized = json.dumps(sig)
        assert "IGNORE" not in serialized
        assert "source_name" not in serialized
        assert "source_url" not in serialized
        assert "example.com" not in serialized

    tb_sig = hfsignals.signal_for(sample_snapshot, "opencode", "opencode-go/glm-5.2", "infra-config-ci")
    assert tb_sig["benchmarks"][0]["value"] == pytest.approx(81.85)
    assert tb_sig["benchmarks"][0]["pull_request"] is True


def test_load_snapshot_states_and_recommend_metadata(hf_catalog, tmp_path, monkeypatch):
    # Missing file -> missing.
    res_missing = scoring.recommend(
        hf_catalog.conn,
        task_type="bugfix",
        complexity="medium",
        available=["opencode:opencode-go/glm-5.3"],
    )
    assert res_missing["explore_signal_source"] == "missing"
    assert res_missing["explore_signal_generated_at"] is None
    assert res_missing["explore"][0]["external_signals"] is None

    # Corrupt JSON -> missing.
    bad_json = tmp_path / "bad.json"
    bad_json.write_text("{not valid json", encoding="utf-8")
    assert hfsignals.load_snapshot(bad_json) == (None, "missing")

    # Wrong schema_version -> schema_mismatch.
    wrong_ver = tmp_path / "wrong_ver.json"
    wrong_ver.write_text(json.dumps({"schema_version": 2, "models": {}}), encoding="utf-8")
    assert hfsignals.load_snapshot(wrong_ver) == (None, "schema_mismatch")

    # Valid fixture -> snapshot with explore_signal_generated_at matching fixture.
    monkeypatch.setattr(hfsignals, "SNAPSHOT_PATH", FIXTURE)
    res_ok = scoring.recommend(
        hf_catalog.conn,
        task_type="bugfix",
        complexity="medium",
        available=["opencode:opencode-go/glm-5.3"],
    )
    assert res_ok["explore_signal_source"] == "snapshot"
    assert res_ok["explore_signal_generated_at"] == "2026-11-18T12:00:00Z"


def test_explore_ordering_with_signals(hf_catalog, monkeypatch):
    # Without snapshot, order matches Phase 1 (cost_tier, -n_task_type, spec).
    available = [
        "opencode:opencode-go/longcat-2.0",   # tier 1, swe=0.0 (bucket 0)
        "opencode:opencode-go/unmapped-model",  # tier 1, no signal
        "opencode:opencode-go/minimax-m3",    # tier 1, swe=0.4 (bucket 1)
        "opencode:opencode-go/glm-5.3",       # tier 1, swe=1.0 (bucket 3)
        "opencode:opencode-go/tier2-top",     # tier 2, no signal
    ]
    no_snap = scoring.recommend(
        hf_catalog.conn, task_type="bugfix", complexity="medium", available=available
    )
    assert [e["spec"] for e in no_snap["explore"]] == [
        "opencode:opencode-go/glm-5.3",
        "opencode:opencode-go/longcat-2.0",
        "opencode:opencode-go/minimax-m3",
    ]

    # With snapshot: bucket 3 (glm-5.3), bucket 1 (minimax-m3), no signal (unmapped) before bucket 0 (longcat-2.0).
    monkeypatch.setattr(hfsignals, "SNAPSHOT_PATH", FIXTURE)
    with_snap = scoring.recommend(
        hf_catalog.conn, task_type="bugfix", complexity="medium", available=available
    )
    assert [e["spec"] for e in with_snap["explore"]] == [
        "opencode:opencode-go/glm-5.3",
        "opencode:opencode-go/minimax-m3",
        "opencode:opencode-go/unmapped-model",
    ]

    # Bucket 0 still ranks ahead of tier 2 (cost_tier sorts before signal bucket).
    tier_vs_bucket = scoring.recommend(
        hf_catalog.conn,
        task_type="bugfix",
        complexity="medium",
        available=[
            "opencode:opencode-go/tier2-top",
            "opencode:opencode-go/longcat-2.0",
            "opencode:opencode-go/unmapped-model",
        ],
    )
    assert [e["spec"] for e in tier_vs_bucket["explore"]] == [
        "opencode:opencode-go/unmapped-model",
        "opencode:opencode-go/longcat-2.0",
        "opencode:opencode-go/tier2-top",
    ]


def test_explain_reports_external_signals(monkeypatch, tmp_path):
    # explain() is static and never reads SNAPSHOT_PATH.
    monkeypatch.setattr(hfsignals, "SNAPSHOT_PATH", tmp_path / "does-not-exist.json")
    explained = scoring.explain()
    ext = explained["external_signals"]
    assert ext["min_reporters"] == hfsignals.HF_MIN_REPORTERS
    assert ext["task_signals"] == hfsignals.TASK_SIGNALS
    assert len(ext["benchmarks"]) == len(hfsignals.HF_BENCHMARKS)
    assert "bucket 1" in ext["rule"] and "bucket 0" in ext["rule"]


def test_committed_snapshot_if_present_has_schema_version_one():
    committed = Path(__file__).resolve().parents[1] / "src" / "chanchi" / "data" / "hf_snapshot.json"
    if not committed.exists():
        pytest.skip("src/chanchi/data/hf_snapshot.json not yet created")
    data = json.loads(committed.read_text(encoding="utf-8"))
    assert data["schema_version"] == 1
