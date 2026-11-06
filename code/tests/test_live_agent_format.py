"""live_agent format (live/agent events.jsonl): timeline loader, claims detectors, server cross-check."""
import json
from pathlib import Path

import pytest

from splitcheck.detectors import (inventory_loss_without_effect, run_all, self_report_contradiction)
from splitcheck.evaluate import server_crosscheck
from splitcheck.timeline import load_timeline, parse_item_list

REPO = Path(__file__).resolve().parents[2]
AGENT01 = REPO / "agent_runs" / "agent-01" / "events.jsonl"
SERVER01 = REPO / "agent_runs" / "agent-01" / "server_events.jsonl"


def _ts(s):
    return f"2026-11-06T18:00:{s:06.3f}Z"


def _events():
    loot = ["obsidianx4", "breadx1", "obsidianx2"]
    return [
        {"ts": _ts(0), "type": "spawn", "pos": {"x": 0, "y": 64, "z": 0}, "dimension": "overworld"},
        {"ts": _ts(0.1), "type": "route_start", "route": [{"step": "chest_a", "x": 10, "y": 64, "z": 0}]},
        {"ts": _ts(0.2), "type": "skill_start", "skill": "goto", "args": {}},
        {"ts": _ts(5), "type": "skill_result", "ok": True, "skill": "goto", "args": {}, "ms": 4800,
         "result": {"ok": True, "pos": {"x": 10, "y": 64, "z": 0}}},
        {"ts": _ts(5.1), "type": "skill_start", "skill": "loot_chest", "args": {}},
        {"ts": _ts(5.5), "type": "skill_result", "ok": True, "skill": "loot_chest", "args": {}, "ms": 400,
         "result": {"ok": True, "got": loot}},
        {"ts": _ts(5.5), "type": "route_loot", "result": {"ok": True, "got": loot}},
        {"ts": _ts(6), "type": "skill_start", "skill": "build_portal", "args": {}},
        {"ts": _ts(9), "type": "skill_result", "ok": False, "skill": "build_portal", "args": {}, "ms": 3000,
         "result": {"ok": False, "error": "frame incomplete", "frame": {"placed": 0, "failed": [{}]}}},
        {"ts": _ts(9.1), "type": "route_inventory", "items": ["obsidianx3", "breadx1"]},
        {"ts": _ts(12), "type": "summary", "elapsedS": 12, "actions": 3, "failures": 0, "deaths": 0,
         "splits": [], "finalSplit": None, "positions": {"x": 10, "y": 64, "z": 1}},
    ]


@pytest.fixture
def small_log(tmp_path):
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in _events()), encoding="utf-8")
    return p


def test_parse_item_list_sums_duplicates():
    assert parse_item_list(["obsidianx1", "obsidianx4", "breadx2", "flint_and_steelx1"]) == \
        {"bread": 2, "flint_and_steel": 1, "obsidian": 5}


def test_small_log_timeline(small_log):
    tl = load_timeline(small_log)
    assert tl.source == "live_agent"
    assert len(tl.samples) == 11
    assert tl.samples[0].t == 0.0 and tl.samples[0].pos == (0.0, 64.0, 0.0)
    assert tl.samples[0].dim == "overworld"
    goto = tl.samples[3]
    assert goto.action == "goto" and goto.action_failed is False and goto.pos == (10.0, 64.0, 0.0)
    # loot counted once (route_loot echoes the skill_result)
    assert tl.samples[6].inv == {"bread": 1, "obsidian": 6}
    fail = tl.samples[8]
    assert fail.action == "build_portal" and fail.action_failed is True
    assert tl.samples[9].inv == {"bread": 1, "obsidian": 3}  # authoritative snapshot
    assert tl.samples[10].pos == (10.0, 64.0, 1.0)
    assert tl.knowledge == {"chest_a": {"x": 10.0, "y": 64.0, "z": 0.0, "dim": "overworld"}}
    assert [e["type"] for e in tl.events] == ["start"]


def test_small_log_claims(small_log):
    tl = load_timeline(small_log)
    fs = self_report_contradiction(tl, {})
    by = {f.evidence["field"]: f for f in fs}
    assert set(by) == {"failures"}  # actions 3 == 3 skill results, deaths 0, splits 0
    f = by["failures"]
    assert f.category == "claim" and f.severity == "high" and f.cost_s == 0
    assert f.lines == [11, 9]
    il = inventory_loss_without_effect(tl, {})
    assert len(il) == 1 and il[0].evidence["before"] == 6 and il[0].evidence["after"] == 3
    assert 9 in il[0].lines and 10 in il[0].lines


def test_dimension_change_is_milestone(tmp_path):
    ev = _events()[:4] + [{"ts": _ts(7), "type": "route_portal", "dimension": "the_nether", "result": {}},
                          {"ts": _ts(8), "type": "summary", "actions": 1, "failures": 0, "deaths": 0,
                           "splits": [], "finalSplit": None}]
    p = tmp_path / "events.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in ev), encoding="utf-8")
    tl = load_timeline(p)
    assert [e["type"] for e in tl.events] == ["start", "nether_entered"]
    fields = {f.evidence["field"] for f in self_report_contradiction(tl, {})}
    assert fields == {"splits", "finalSplit"}


def test_existing_formats_not_live(tmp_path):
    p = tmp_path / "e.jsonl"
    p.write_text(json.dumps({"time": _ts(0), "type": "start", "source": "rcon_poller"}) + "\n"
                 + json.dumps({"time": _ts(1), "type": "position_sample", "player": "P",
                               "position": [0, 64, 0], "dimension": "overworld", "inventory": {}}) + "\n")
    assert load_timeline(p).source == "human_poller"


@pytest.mark.skipif(not AGENT01.exists(), reason="agent-01 log not present")
def test_real_agent01():
    tl = load_timeline(AGENT01)
    assert tl.source == "live_agent"
    assert len(tl.samples) >= 30
    bp = [s for s in tl.samples if s.action == "build_portal"]
    assert len(bp) == 1 and bp[0].action_failed is True
    fs = [f for f in run_all(tl) if f.code == "self_report_contradiction"]
    fail = [f for f in fs if f.evidence["field"] == "failures"]
    assert len(fail) == 1 and fail[0].evidence["claimed"] == 0 and fail[0].evidence["logged"] == 1
    assert fail[0].lines[0] == 32 and bp[0].line in fail[0].lines
    il = [f for f in run_all(tl) if f.code == "inventory_loss_without_effect"]
    assert il and il[0].evidence["before"] == 21 and il[0].evidence["after"] == 17


@pytest.mark.skipif(not (AGENT01.exists() and SERVER01.exists()), reason="agent-01 logs not present")
def test_real_agent01_server_coverage():
    x = server_crosscheck(load_timeline(AGENT01), load_timeline(SERVER01))
    c = x["coverage"]
    assert c["server_last_t_s"] < 48.0  # server log ends before the portal result
    assert 27 in c["snapshots_without_server_sample"]
    assert any("build_portal" in n for n in c["notes"])
