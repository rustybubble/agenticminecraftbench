"""Regression tests for the v4 fixer pass (unfinished runs, respawns, multiple Nether trips,
bed counting, report waste cap, timer basis, path-independent outputs)."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

from splitcheck import effcheck
from splitcheck import evaluate as ev
from splitcheck.v4export import to_timeline

RUNS = Path(__file__).parent / "fixtures" / "runs"
T0 = datetime(2026, 11, 6, 15, 0, 0, tzinfo=timezone.utc)
PORTAL_OW = (-1129.5, 24.0, 837.5)  # ~21 blocks from the End portal (-1130, 34, 856)
SEED_EP = {"endPortal": {"x": -1130, "y": 34, "z": 856}}


def _ts(t):
    return (T0 + timedelta(seconds=t)).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"


def write_log(path, plan, events=(), step=0.5):
    """plan = [(t_until, dim, pos, inv, health)]: samples every `step` s up to t_until (exclusive)."""
    rows = [{"type": "start", "source": "rcon_poller", "player": "p", "time": _ts(0)}]
    t = 0.0
    for until, dim, pos, inv, hp in plan:
        while t < until - 1e-9:
            rows.append({"type": "position_sample", "time": _ts(t), "dimension": dim,
                         "position": list(pos), "inventory": dict(inv or {}), "health": hp, "food": 20})
            t = round(t + step, 3)
    for et, typ, extra in events:
        rows.append({"type": typ, "time": _ts(et), **(extra or {})})
    rows.sort(key=lambda r: (r["time"], r["type"] != "position_sample"))
    rows.append({"type": "stop", "time": _ts(t)})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    return path


def export(path, **kw):
    return to_timeline(path, findings=[], **kw)


def eff_of(tl):
    return effcheck.check(tl, effcheck.load_baseline("baseline/pro_2m49_segments.json"), effcheck.load_rules())


def seg(eff, name):
    return next(s for s in eff["segments"] if s["segment"] == name)


OW, NE, END = "overworld", "the_nether", "the_end"


# ---- finding 1: unfinished runs and respawns are not finishes
def test_death_in_end_respawn_is_not_a_finish(tmp_path):
    log = write_log(tmp_path / "end_death_respawn.jsonl",
                    [(30, OW, (0, 70, 0), {}, 20), (60, NE, (-141, 70, 104), {}, 20),
                     (62, OW, PORTAL_OW, {}, 20), (70.5, END, (100, 49, 0), {}, 20),
                     (75, OW, (0, 70, 0), {}, 20)],
                    events=[(70.4, "death_suspected", {"note": "respawn"})])
    tl = export(log)
    m = tl["milestones"]["M_finish"]
    assert m["low"] is None and m["reached"] is False and "unfinished" in m["note"]
    assert tl["finish_flag"] == "unfinished"
    e = eff_of(tl)
    assert seg(e, "end")["verdict"] == "NOT_REACHED"
    assert e["total"]["agent_s_low"] is None and e["total"]["ratio_low"] is None
    assert e["flags"] and "not reached" in e["flags"][0]


def test_breath_cloud_death_no_longer_beats_clean_run():
    tl = to_timeline(RUNS / "agent_breath_cloud_death.jsonl")
    e = eff_of(tl)
    assert seg(e, "end")["verdict"] == "NOT_REACHED"
    assert e["total"]["ratio_low"] is None
    assert tl["facts"]["beds_used"] is None  # died before the bed fight: no extra_items charge
    assert not any(w["tag"] == "extra_items" for s in e["segments"] for w in s["waste"])


def test_real_exit_portal_counts_and_dragon_kill_is_flagged_proxy(tmp_path):
    plan = [(30, OW, (0, 70, 0), {}, 20), (60, NE, (-141, 70, 104), {}, 20),
            (62, OW, PORTAL_OW, {}, 20), (100, END, (100, 49, 0), {}, 20)]
    tl = export(write_log(tmp_path / "exit.jsonl", plan + [(105, OW, (0, 70, 0), {}, 20)]))
    assert tl["milestones"]["M_finish"]["low"] == 100.0 and tl["finish_flag"] is None
    assert "flags" not in eff_of(tl)
    tl = export(write_log(tmp_path / "dragon.jsonl", plan, events=[(95.0, "dragon_killed", {})]))
    m = tl["milestones"]["M_finish"]
    assert m["low"] == 95.0 and m["proxy"] is True and tl["finish_flag"] == "proxy_finish_dragon_killed"
    assert "proxy" in eff_of(tl)["flags"][0]


# ---- finding 2: a Nether death/respawn is not M_portal_out
def test_death_in_nether_does_not_end_nether_segment(tmp_path):
    log = write_log(tmp_path / "death_in_nether.jsonl",
                    [(30.5, OW, (0, 70, 0), {}, 20), (50, NE, (-141, 70, 104), {}, 20),
                     (70.5, OW, (0, 70, 0), {}, 20), (100.5, NE, (-141, 70, 104), {}, 20),
                     (105.5, OW, PORTAL_OW, {}, 20), (120, END, (100, 49, 0), {}, 20),
                     (125, OW, (0, 70, 0), {}, 20)],
                    events=[(49.9, "death_suspected", {})])
    tl = export(log, seed_dir=None)
    assert tl["milestones"]["M_portal_out"]["low"] == 100.5
    assert tl["facts"]["overworld_arrival_xyz"] == {"x": -1129.5, "y": 24.0, "z": 837.5}


# ---- finding 3: multiple trips use the last exit before the End
def test_multi_trip_uses_last_exit_and_lists_round_trip(tmp_path):
    log = write_log(tmp_path / "multi_trip.jsonl",
                    [(30.5, OW, (0, 70, 0), {}, 20), (35.5, NE, (-5, 70, 3), {}, 20),
                     (40.5, OW, (-40, 70, 20), {}, 20), (70.5, NE, (-141, 70, 104), {}, 20),
                     (72.5, OW, PORTAL_OW, {}, 20), (90, END, (100, 49, 0), {}, 20),
                     (95, OW, (0, 70, 0), {}, 20)])
    tl = export(log)
    ms = tl["milestones"]
    assert (ms["M_portal_in"]["low"], ms["M_portal_out"]["low"], ms["M_end_in"]["low"]) == (30.5, 70.5, 72.5)
    assert tl["facts"]["overworld_arrival_xyz"]["x"] == -1129.5
    trips = [w for w in tl["waste_extra"] if w["runeval_code"] == "extra_nether_round_trip"]
    assert len(trips) == 1 and trips[0]["tag"] == "wrong_order" and trips[0]["seconds"] == 5.0
    assert trips[0]["segment"] == "nether"


# ---- finding 5: re-picking a placed bed is not a new bed
def test_beds_count_max_held(tmp_path):
    bed = lambda n: {"white_bed": n} if n else {}
    log = write_log(tmp_path / "beds.jsonl",
                    [(5, OW, (0, 70, 0), bed(0), 20), (10, OW, (0, 70, 0), bed(3), 20),
                     (15, OW, (0, 70, 0), bed(2), 20), (20, OW, (0, 70, 0), bed(3), 20),
                     (25, OW, (0, 70, 0), bed(2), 20), (30.5, OW, (0, 70, 0), bed(3), 20),
                     (60, NE, (-141, 70, 104), bed(3), 20), (62, OW, PORTAL_OW, bed(3), 20),
                     (80, END, (100, 49, 0), bed(3), 20), (100, END, (100, 49, 0), bed(0), 20),
                     (105, OW, (0, 70, 0), bed(0), 20)])
    f = export(log)["facts"]
    assert (f["beds_collected"], f["beds_used"]) == (3, 3)


# ---- finding 4: report waste column capped at the segment's excess
def test_report_waste_capped_at_excess(tmp_path):
    res = ev.evaluate(RUNS / "agent_long_approach_timeouts.jsonl", outdir=tmp_path, write=False)
    s = seg(res["efficiency"], "spawn_to_nether")
    cap = round(s["agent_s_low"] - s["pro_s"], 3)
    raw = round(sum(w["seconds"] for w in s["waste"] if isinstance(w["seconds"], (int, float))), 3)
    assert raw > cap
    assert f"| {cap} (raw {raw}) |" in res["texts"]["report.md"]


# ---- finding 6: total vs pro RTA and the IGT/RTA gap are reported
def test_report_has_rta_line():
    res = ev.evaluate(RUNS / "agent_clean.jsonl", write=False)
    md = res["texts"]["report.md"]
    assert "## Timer basis" in md and "pro RTA" in md and "174.545" in md
    assert "exit_to_end_portal" in md.split("## Timer basis")[1].split("##")[0]


# ---- finding 8: relative and absolute log paths give byte-identical outputs
def test_outputs_do_not_depend_on_path_spelling(tmp_path):
    p = RUNS / "agent_clean.jsonl"
    rel = os.path.relpath(p, os.getcwd())
    a = ev.evaluate(rel, run_id="x", write=False)["texts"]
    b = ev.evaluate(str(p.resolve()), run_id="x", write=False)["texts"]
    assert a == b
