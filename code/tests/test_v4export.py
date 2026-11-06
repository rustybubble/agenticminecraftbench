import json
from pathlib import Path

import pytest

from splitcheck.timeline import load_timeline
from splitcheck.v4export import CODE_TO_TAG, MILESTONE_IDS, WASTE_TAGS, main, to_json, to_timeline

RUNS = Path(__file__).parent / "fixtures" / "runs"
LOGS = sorted(RUNS.glob("*.jsonl"))
SEGMENTS = ("spawn_to_nether", "nether", "exit_to_end_portal", "end")


@pytest.fixture(scope="module")
def exported():
    return {p.name: to_timeline(p) for p in LOGS}


def test_fixture_logs_cover_both_formats():
    names = [p.name for p in LOGS]
    assert any(n.startswith("agent_") for n in names)
    assert any(n.startswith("human_poller") for n in names)


@pytest.mark.parametrize("log", LOGS, ids=lambda p: p.stem)
def test_shape_and_monotonic_milestones(exported, log):
    d = exported[log.name]
    assert d["kind"] == "agent_timeline"
    assert d["run_id"] == log.stem
    ms = d["milestones"]
    assert tuple(ms) == MILESTONE_IDS
    assert ms["M_start"]["low"] == 0.0
    times = []
    for mid in MILESTONE_IDS:
        m = ms[mid]
        if mid == "M_finish" and m["low"] is None:  # death / poller runs stop in the End
            assert m["reached"] is False and "unfinished" in m["note"]
            assert d["finish_flag"] == "unfinished"
            continue
        assert m["low"] is not None, mid  # every fixture run reaches the End
        assert m["low"] == m["high"]
        times.append(m["low"])
    assert times == sorted(times)
    assert times[1] > 0


@pytest.mark.parametrize("log", LOGS, ids=lambda p: p.stem)
def test_facts_present(exported, log):
    f = exported[log.name]["facts"]
    for k in ("overworld_arrival_xyz", "end_portal_xyz", "beds_collected", "beds_used",
              "model_latency_s", "deaths"):
        assert k in f, k
    for k in ("x", "y", "z"):
        assert isinstance(f["overworld_arrival_xyz"][k], float)
        assert isinstance(f["end_portal_xyz"][k], float)
    if exported[log.name]["milestones"]["M_finish"]["low"] is None:
        assert f["beds_used"] is None and "unknown" in f["beds_used_note"]
    else:
        assert f["beds_used"] <= f["beds_collected"]
    for seg in SEGMENTS:
        assert set(f[seg]) >= {"path_blocks", "straight_blocks", "failed_actions"}
        assert f[seg]["path_blocks"] >= 0
    if log.name.startswith("agent_"):
        assert f["model_latency_s"] > 0
        assert "knownSeed" in f["end_portal_source"]
    else:
        assert f["model_latency_s"] is None
        assert "not disclosed" in f["end_portal_source"]


@pytest.mark.parametrize("log", LOGS, ids=lambda p: p.stem)
def test_waste_extra_tags_and_evidence(exported, log):
    d = exported[log.name]
    for w in d["waste_extra"]:
        assert w["tag"] in WASTE_TAGS
        assert w["segment"] in SEGMENTS
        assert w["lines"], w
        assert w["runeval_code"] in w["evidence"]
        assert "line" in w["evidence"]
        assert w["seconds"] >= 0


def test_mapping_only_targets_allowed_tags():
    assert set(CODE_TO_TAG.values()) <= set(WASTE_TAGS)


def test_clean_agent_run(exported):
    d = exported["agent_clean.jsonl"]
    assert d["milestones"]["M_finish"]["evidence"] == "game_won event"
    assert "note" not in d["milestones"]["M_finish"]
    f = d["facts"]
    assert (f["beds_collected"], f["beds_used"], f["deaths"]) == (8, 6, 0)
    assert f["overworld_arrival_xyz"] == {"x": -1129.5, "y": 24.0, "z": 837.5}
    assert f["end_portal_xyz"] == {"x": -1130.0, "y": 34.0, "z": 856.0}


def test_death_run_unfinished_and_risk(exported):
    d = exported["agent_breath_cloud_death.jsonl"]
    assert "unfinished" in d["milestones"]["M_finish"]["note"]
    assert d["facts"]["deaths"] == 1
    risk = [w for w in d["waste_extra"] if w["tag"] == "unnecessary_risk"]
    assert risk and risk[0]["segment"] == "end"


def test_water_mining_maps_to_failed_action_in_first_segment(exported):
    d = exported["agent_mining_in_water_lost_drop.jsonl"]
    tags = {(w["runeval_code"], w["tag"], w["segment"]) for w in d["waste_extra"]}
    assert ("mining_in_water", "failed_or_retried_action", "spawn_to_nether") in tags
    assert ("lost_drop", "failed_or_retried_action", "spawn_to_nether") in tags
    h = exported["human_poller_water_mining_detour.jsonl"]
    assert any(w["runeval_code"] == "mining_in_water" for w in h["waste_extra"])


def test_obsidian_source_is_wrong_order(exported):
    d = exported["agent_mined_obsidian_ignoring_chests.jsonl"]
    assert any(w["runeval_code"] == "obsidian_source" and w["tag"] == "wrong_order"
               for w in d["waste_extra"])


def test_deterministic_and_timeline_input():
    p = RUNS / "agent_peaceful_food_tools.jsonl"
    a, b = to_json(to_timeline(p)), to_json(to_timeline(p))
    assert a == b
    assert to_json(to_timeline(load_timeline(p))) == a


def test_findings_override():
    p = RUNS / "agent_clean.jsonl"
    fake = [{"code": "idle", "t_start": 120.0, "cost_s": 2.0, "lines": [200], "message": "m"},
            {"code": "stage_time", "t_start": 1.0, "cost_s": 3.0, "lines": [5], "message": "x"}]
    d = to_timeline(p, findings={"findings": fake})
    assert [(w["tag"], w["segment"], w["seconds"]) for w in d["waste_extra"]] == [("idle_wait", "nether", 2.0)]
    assert d["waste_extra_unmapped_codes"] == {"stage_time": 1}


def test_missing_milestones(tmp_path):
    src = (RUNS / "agent_clean.jsonl").read_text(encoding="utf-8").splitlines()
    cut = tmp_path / "early.jsonl"
    cut.write_text("\n".join(src[:60]) + "\n", encoding="utf-8")
    d = to_timeline(cut)
    ms = d["milestones"]
    assert ms["M_portal_in"]["reached"] is False and ms["M_portal_in"]["low"] is None
    assert "unfinished" in ms["M_finish"]["note"]
    assert "overworld_arrival_xyz" not in d["facts"]


def test_cli_writes_file(tmp_path):
    out = tmp_path / "x" / "timeline.json"
    assert main([str(RUNS / "human_poller_clean.jsonl"), "--out", str(out)]) == 0
    d = json.loads(out.read_text(encoding="utf-8"))
    assert d["kind"] == "agent_timeline" and d["source"] == "human_poller"
