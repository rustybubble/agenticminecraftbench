"""Regression tests for the reviewer probes on runeval/detectors (fixer pass 2)."""
import json

import pytest

from splitcheck import detectors as D
from splitcheck import detectors_seed as DS
from splitcheck.runeval import _credit_contained, evaluate_run
from splitcheck.timeline import Sample, Timeline, _block_flags


def S(t, line, x, z, inv=None, dim="overworld", y=64.0, hp=None, water=None, lava=None, food=None):
    return Sample(t=t, line=line, pos=(x, y, z), dim=dim, inv=dict(inv or {}), health=hp,
                  in_water=water, in_lava=lava, food=food, kind="position_sample")


def TL(samples, knowledge=None, events=None):
    return Timeline(source="human_poller", samples=samples, events=events or [],
                    knowledge=knowledge or {}, meta={})


def codes(fs):
    return [f.code for f in fs]


# ---- damage_taken: lava cost is per episode, not max-min over the whole run (probe D1)
def test_lava_cost_is_episode_local():
    ss = []
    for i in range(641):  # 320 s at 2 Hz
        t = i * 0.5
        lava = 5 <= t <= 6 or 300 <= t <= 301
        hp = 20.0 - 2 * sum(1 for k in range(i + 1) if 300 <= k * 0.5 <= 301)
        ss.append(S(t, i + 1, 0, 0, hp=hp, lava=lava))
    fs = [f for f in D.damage_taken(TL(ss), {}) if f.evidence["cause"] == "lava"]
    assert fs and all(f.cost_s <= 2.0 for f in fs)


# ---- mining_in_water: eyes only, and only the dig is charged (probes A1, A2, C)
def test_wading_is_not_underwater():
    assert _block_flags({"feet_block": "water", "head_block": "other"}) == (False, False)
    assert _block_flags({"feet_block": "water", "head_block": "water"}) == (True, False)
    assert _block_flags({"feet_block": "water", "head_block": "water", "eye_block": "other"})[0] is False


def test_swim_then_one_block_charges_only_the_dig():
    ss = [S(i * 0.5, i + 1, i * 2.0, 0, water=True) for i in range(81)]  # 40 s swimming, moving
    ss.append(S(40.5, 82, 160.0, 0, {"dirt": 1}, water=True))
    fs = D.mining_in_water(TL(ss), {})
    assert sum(f.cost_s for f in fs) <= 1.0  # one 0.5 s sample of digging, x0.8


def test_stationary_underwater_dig_is_charged():
    ss = [S(i * 0.5, i + 1, 0, 0, water=True) for i in range(10)]  # 4.5 s at one spot
    ss.append(S(5.0, 11, 0, 0, {"clay_ball": 4}, water=True))
    fs = D.mining_in_water(TL(ss), {})
    assert len(fs) == 1 and fs[0].cost_s == pytest.approx(5.0 * 0.8, abs=0.01)


# ---- excess_materials: stone broken while staircasing is incidental (probe C1)
def test_staircase_cobble_not_surplus():
    ss = [S(i, i + 1, i * 0.6, 0, {"cobblestone": i} if i else {}, y=70 - i * 0.5) for i in range(30)]
    assert "excess_materials" not in codes(D.excess_materials(TL(ss), {}))


# ---- oscillation: not in the_end, not while health changes (probes B2, B3)
def _strafe(dim, hp_change=False):
    xs = [0, 1.5, 3, 1.5]
    return [S(i * 0.5, i + 1, xs[i % 4] * 2, 0, {"white_bed": 8}, dim=dim,
              hp=(20 - (i % 3) if hp_change else 20)) for i in range(58)]


def test_oscillation_skips_end_and_combat():
    assert D.oscillation(TL(_strafe("the_end")), {}) == []
    assert D.oscillation(TL(_strafe("the_nether", hp_change=True)), {}) == []
    assert D.oscillation(TL(_strafe("the_nether")), {})  # pure dithering is still flagged


# ---- excess_food: peaceful comes from the seed features (probe B / B2)
def test_peaceful_from_seed_ctx():
    ss = [S(i, i + 1, 0, 0, {"bread": i}, food=20) for i in range(8)] + [S(30, 9, 0, 0, {})]
    fs = D.excess_food(TL(ss), {"seed": {"difficulty": "peaceful"}})
    assert fs and all("peaceful" in f.message for f in fs)


# ---- overshoot: a side trip that loots another known target is not overshoot (probe O1)
def test_productive_side_trip_not_overshoot():
    k = {"entryPortal": {"x": -285, "y": 67, "z": 259, "dim": "overworld"},
         "chest": {"x": -290, "y": 68, "z": 253, "dim": "overworld"}}
    path = [(-285, 259)] * 2 + [(-287, 257), (-289, 255), (-291.5, 252), (-291.5, 252),
                                (-289, 255), (-287, 257), (-285, 259)]
    ss = []
    for i, (x, z) in enumerate(path):
        inv = {"obsidian": 11} if i >= 5 else {}
        ss.append(S(i * 1.0, i + 1, x, z, inv))
    assert D.overshoot_waypoint(TL(ss, k), {}) == []


# ---- decision detectors: proximity-only knowledge is report-only (probe G1)
def test_proximity_findings_cost_zero():
    seed = {"chests": [{"x": 0, "y": 64, "z": 100, "dim": "overworld", "source": "t",
                        "contents": {"obsidian": 6}}]}
    ss = [S(0, 1, 0, 80), S(10, 2, 0, 75), S(20, 3, 20, 75, {"obsidian": 10})]
    fs = DS.SEED_REGISTRY["obsidian_source"](TL(ss), {"seed": seed})
    assert fs and all(f.cost_s == 0 and f.evidence["report_only"] for f in fs)
    assert "known chest" not in fs[0].message


# ---- portal_method: essential_existing (3), and 8-9 placed is flagged (probes H1, 9)
def _portal_tl(placed):
    k = {"entryPortal": {"x": -285, "y": 67, "z": 259, "dim": "overworld", "essential_existing": 3,
                         "existing_frame_obsidian": [[0, 0, 0]] * 8}}
    ss = [S(0, 1, -284.5, 259.5, {"obsidian": 21, "flint_and_steel": 1}),
          S(5, 2, -284.5, 259.5, {"obsidian": 21 - placed, "flint_and_steel": 1}),
          S(10, 3, 0, 0, {"obsidian": 21 - placed}, dim="the_nether")]
    return TL(ss, k, events=[{"t": 10, "line": 3, "type": "nether_entered"}])


def test_portal_method_uses_essential_existing():
    f10 = DS.SEED_REGISTRY["portal_method"](_portal_tl(10), {"seed": {}})
    assert f10[0].evidence["existing_frame_blocks"] == 3 and f10[0].evidence["extra_blocks"] == 3
    f9 = DS.SEED_REGISTRY["portal_method"](_portal_tl(9), {"seed": {}})
    assert f9[0].evidence["extra_blocks"] == 2
    assert DS.SEED_REGISTRY["portal_method"](_portal_tl(7), {"seed": {}}) == []


# ---- overworld travel: needs obsidian for the frames (probe E2)
def test_overworld_travel_needs_obsidian():
    k = {"entryPortal": {"x": 50, "y": 64, "z": 0, "dim": "overworld"},
         "endPortal": {"x": 4000, "y": 30, "z": 0, "dim": "overworld"}}
    ss = [S(i * 10, i + 1, i * 71.27, 0, {"flint_and_steel": 1}) for i in range(41)]
    assert DS.SEED_REGISTRY["overworld_travel_when_nether_known"](TL(ss, k), {"seed": {}}) == []


# ---- path_efficiency is credited for the micro findings inside its leg (probe P2)
def test_path_efficiency_credited_for_contained_oscillation():
    fs = [{"code": "path_efficiency", "t_start": 0.0, "t_end": 57.0, "cost_s": 12.1, "evidence": {}},
          {"code": "oscillation", "t_start": 22.5, "t_end": 52.5, "cost_s": 30.0, "evidence": {}}]
    _credit_contained(fs)
    assert fs[0]["cost_s"] == 0.0 and fs[0]["evidence"]["contained_micro_credit_s"] == 30.0


# ---- runeval: seed mismatch disables seed features; Sample keeps selected_item (probes D, 14)
def _poller_log(path, seed):
    rows = [{"type": "start", "time": "2026-11-06T15:00:00.000Z", "source": "rcon_poller",
             "seed": seed, "player": "p"}]
    invs = [{"obsidian": 21, "flint_and_steel": 1}] * 3 + [{"obsidian": 11, "flint_and_steel": 1}] * 3
    for i, inv in enumerate(invs):
        rows.append({"type": "position_sample", "time": f"2026-11-06T15:00:0{i}.000Z", "player": "p",
                     "position": [-284.5, 67.0, 259.5], "dimension": "overworld", "inventory": inv,
                     "health": 20.0, "food": 20, "selected_item": "minecraft:obsidian",
                     "feet_block": "other", "head_block": "other"})
    rows.append({"type": "position_sample", "time": "2026-11-06T15:00:08.000Z", "player": "p",
                 "position": [-35.0, 70.0, 32.0], "dimension": "the_nether", "inventory": invs[-1],
                 "health": 20.0, "food": 20, "selected_item": None, "feet_block": "other",
                 "head_block": "other"})
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return path


def test_seed_mismatch_skips_seed_features(tmp_path):
    rep = evaluate_run(_poller_log(tmp_path / "bad.jsonl", "Seed: [12345]"))
    assert rep["coverage"]["seed_match"] is False and "mismatch" in rep["coverage"]["seed_error"]
    assert rep["coverage"]["seed_features"] == []
    ok = evaluate_run(_poller_log(tmp_path / "ok.jsonl", "Seed: [8398967436125155523]"))
    assert ok["coverage"]["seed_match"] is True


def test_selected_item_kept(tmp_path):
    from splitcheck.timeline import load_timeline
    tl = load_timeline(_poller_log(tmp_path / "s.jsonl", "Seed: [8398967436125155523]"))
    assert tl.samples[0].selected_item == "obsidian"
