"""Tests for splitcheck.effcheck (SCHEMA.md section 8 efficiency check)."""
from __future__ import annotations

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from splitcheck import effcheck

REPO = Path(__file__).resolve().parents[2]
FIXTURES = sorted((REPO / "fixtures").glob("*.json"))
MONTAGE = REPO / "agent_runs" / "published_montage" / "timeline.json"
BASE = "baseline/pro_2m49_segments.json"


def _load(p):
    return json.loads(Path(p).read_text(encoding="utf-8"))


def _reference():
    spec = importlib.util.spec_from_file_location("reference_check", REPO / "baseline" / "reference_check.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _verdicts(out):
    return [(r["segment"], r.get("verdict")) for r in out["segments"]]


def test_fixtures_exist():
    assert FIXTURES, "no fixtures/*.json found"


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_fixture_parity(path):
    fx = _load(path)
    out = effcheck.check(fx, effcheck.load_baseline(fx["baseline"]))
    assert out == fx["expected"]


@pytest.mark.parametrize("path", FIXTURES, ids=lambda p: p.stem)
def test_matches_reference_check(path):
    fx = _load(path)
    base = effcheck.load_baseline(fx["baseline"])
    ours = effcheck.check(fx, base)
    ref = _reference().check(fx, base)
    assert json.dumps(ours, indent=1) == json.dumps(ref, indent=1)


def test_baseline_defaults_to_timeline_field():
    fx = _load(REPO / "fixtures" / "published_montage.json")
    assert effcheck.check(fx) == fx["expected"]


def test_waste_extra_appended_without_changing_verdicts():
    fx = _load(REPO / "fixtures" / "published_montage.json")
    base = effcheck.load_baseline(fx["baseline"])
    plain = effcheck.check(fx, base)
    tl = copy.deepcopy(fx)
    tl["waste_extra"] = [
        {"segment": "nether", "tag": "longer_path", "seconds": 12.5, "evidence": "path_efficiency: t=200 ..."},
        {"segment": "exit_to_end_portal", "tag": "failed_or_retried_action", "seconds": 3.0, "evidence": ["action_loop", "log line 42"]},
        {"segment": "nowhere", "tag": "idle_wait", "seconds": 1.0, "evidence": "idle"},
    ]
    out = effcheck.check(tl, base)
    assert _verdicts(out)[:4] == _verdicts(plain)
    assert out["run_median_ratio"] == plain["run_median_ratio"] and out["total"] == plain["total"]
    by = {r["segment"]: r for r in out["segments"]}
    assert by["nether"]["waste"] == [{"tag": "longer_path", "seconds": 12.5, "evidence": "path_efficiency: t=200 ..."}]
    ex = by["exit_to_end_portal"]["waste"]
    assert ex[0]["tag"] == "missed_shortcut"  # rule-based entry first, extra appended after
    assert ex[1] == {"tag": "failed_or_retried_action", "seconds": 3.0, "evidence": ["action_loop", "log line 42"]}
    assert by["whole_run"]["waste"] == [{"tag": "idle_wait", "seconds": 1.0, "evidence": "idle"}]
    for r in out["segments"][:4]:
        for k in ("agent_s_low", "agent_s_high", "pro_s", "ratio_low", "ratio_high"):
            assert r[k] == by[r["segment"]][k]


def test_missing_optional_facts():
    fx = _load(REPO / "fixtures" / "published_montage.json")
    tl = {"milestones": fx["milestones"]}  # no facts at all
    out = effcheck.check(tl, effcheck.load_baseline(BASE))
    assert [r["segment"] for r in out["segments"]] == ["spawn_to_nether", "nether", "exit_to_end_portal", "end"]
    assert all(r["waste"] == [] for r in out["segments"])
    assert _verdicts(out) == _verdicts(fx["expected"])
    # partial facts: only one xyz, beds without beds_used, null latency -> no entries, no crash
    tl["facts"] = {"overworld_arrival_xyz": {"x": 0, "y": 0, "z": 0}, "beds_collected": 8, "model_latency_s": None}
    out2 = effcheck.check(tl, effcheck.load_baseline(BASE))
    assert out2 == out


def test_latency_and_deaths_whole_run():
    fx = _load(REPO / "fixtures" / "pro_as_agent.json")
    fx["facts"]["model_latency_s"] = 42.0
    fx["facts"]["deaths"] = 1
    out = effcheck.check(fx, effcheck.load_baseline(BASE))
    whole = out["segments"][-1]
    assert whole["segment"] == "whole_run"
    assert [w["tag"] for w in whole["waste"]] == ["idle_wait", "unnecessary_risk"]
    assert whole["waste"][0]["seconds"] == 42.0
    assert all(r["verdict"] == "OK" for r in out["segments"][:4])


def test_per_segment_path_and_failed_actions():
    fx = _load(REPO / "fixtures" / "pro_as_agent.json")
    fx["facts"]["nether"] = {"path_blocks": 300, "straight_blocks": 100, "failed_actions": 2}
    out = effcheck.check(fx, effcheck.load_baseline(BASE))
    nether = [r for r in out["segments"] if r["segment"] == "nether"][0]
    assert [w["tag"] for w in nether["waste"]] == ["longer_path", "failed_or_retried_action"]
    assert nether["waste"][0]["seconds"] == round(200 * 0.1403, 3)
    # supplied by waste_extra -> rule-derived duplicate suppressed
    fx["waste_extra"] = [{"segment": "nether", "tag": "longer_path", "seconds": 5.0, "evidence": "runeval"}]
    nether = [r for r in effcheck.check(fx, effcheck.load_baseline(BASE))["segments"] if r["segment"] == "nether"][0]
    assert [w["evidence"] for w in nether["waste"] if w["tag"] == "longer_path"] == ["runeval"]


def test_thresholds_come_from_rules():
    fx = _load(REPO / "fixtures" / "same_total_diff_split.json")
    rules = effcheck.load_rules()
    rules["verdict"]["flag_min_excess_s"] = 1000.0
    out = effcheck.check(fx, effcheck.load_baseline(BASE), rules)
    assert dict(_verdicts(out))["nether"] == "SLOW"
    rules = effcheck.load_rules()
    rules["waste_rules"][0]["when"] = "facts.overworld_arrival_xyz is more than 30 blocks (3D) from facts.end_portal_xyz"
    fx = _load(REPO / "fixtures" / "inflated_exit.json")
    out = effcheck.check(fx, effcheck.load_baseline(BASE), rules)
    assert all(r["waste"] == [] for r in out["segments"])


def test_missing_milestone_not_reached():
    fx = _load(REPO / "fixtures" / "pro_as_agent.json")
    del fx["milestones"]["M_end_in"]
    out = effcheck.check(fx, effcheck.load_baseline(BASE))
    v = dict(_verdicts(out))
    assert v["exit_to_end_portal"] == "NOT_REACHED" and v["end"] == "NOT_REACHED"
    assert v["spawn_to_nether"] == "OK" and out["total"]["ratio_low"] == 1.0


def test_raw_montage_format():
    raw = _load(MONTAGE)
    fx = _load(REPO / "fixtures" / "published_montage.json")
    out = effcheck.check(raw, effcheck.load_baseline(BASE))
    exp = fx["expected"]
    assert out["run_median_ratio"] == exp["run_median_ratio"] and out["total"] == exp["total"]
    strip = lambda rows: [{k: v for k, v in r.items() if k != "waste"} for r in rows]
    assert strip(out["segments"]) == strip(exp["segments"])


def test_cli_deterministic(tmp_path, capsys):
    path = REPO / "fixtures" / "published_montage.json"
    o1, o2 = tmp_path / "a.json", tmp_path / "b.json"
    assert effcheck.main([str(path), "--out", str(o1)]) == 0
    assert effcheck.main([str(path), "--baseline", str(REPO / BASE), "--out", str(o2)]) == 0
    assert o1.read_bytes() == o2.read_bytes()
    assert json.loads(o1.read_text()) == _load(path)["expected"]
