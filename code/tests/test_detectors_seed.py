"""Seed-aware decision detectors on crafted timelines (deterministic)."""
import pytest

from splitcheck.detectors_seed import (SEED_REGISTRY, SPRINT_BPS, MINE_OBSIDIAN_S, path_legs)
from splitcheck.timeline import Sample, Timeline

CHEST = {"x": 0, "y": 64, "z": 100}
SEED = {
    "chests": [{"x": 0, "y": 64, "z": 100, "dim": "overworld", "source": "test",
                "contents": {"obsidian": 6, "bread": 2}}],
    "entry_portal": {"x": 50, "y": 64, "z": 0, "dim": "overworld", "source": "test",
                     "existing_frame_obsidian": [[50, 63, 0], [51, 63, 0], [52, 63, 0]]},
    "end_portal": {"x": 4000, "y": 30, "z": 0, "dim": "overworld", "source": "test"},
    "village": {"x": -300, "y": 64, "z": 0, "dim": "overworld", "source": "test"},
    "spawn": {"x": 0, "y": 64, "z": 0, "dim": "overworld", "source": "test"},
}


def S(t, line, x, z, inv=None, dim="overworld", action=None, y=64):
    return Sample(t=t, line=line, pos=(x, y, z), dim=dim, inv=inv or {}, action=action)


def tl_of(samples, knowledge=None, events=None, source="agent"):
    return Timeline(source=source, samples=samples, events=events or [], knowledge=knowledge or {},
                    meta={})


def run(code, tl, **ctx):
    ctx.setdefault("seed", SEED)
    return SEED_REGISTRY[code](tl, ctx)


def test_registry_names():
    assert set(SEED_REGISTRY) == {"obsidian_source", "portal_method",
                                  "overworld_travel_when_nether_known", "unneeded_structure_visit",
                                  "stage_time", "path_efficiency"}


# ---------------------------------------------------------------- obsidian_source
def _mining_tl(knowledge):
    return tl_of([S(0, 1, 0, 0), S(10, 2, 0, 0, {"obsidian": 1}, action="mine_obsidian"),
                  S(20, 3, 0, 0, {"obsidian": 2}, action="mine_obsidian"),
                  S(30, 4, 0, 0, {"obsidian": 3}, action="mine_obsidian")], knowledge)


def test_obsidian_mined_while_known_chest_unlooted():
    f = run("obsidian_source", _mining_tl({"chests_0": dict(CHEST, dim="overworld")}))
    assert len(f) == 1
    f = f[0]
    assert f.category == "decision" and f.lines == [2, 3, 4]
    expect = 3 * MINE_OBSIDIAN_S - 200 / SPRINT_BPS  # 100-block chest, round trip
    assert f.cost_s == pytest.approx(expect, abs=0.01)
    assert f.evidence["estimate"] is True and f.evidence["knowledge_basis"] == "disclosed"
    assert f.evidence["knowledge_used"][0]["name"] == "chests_0"


def test_obsidian_no_finding_when_chest_already_looted():
    tl = tl_of([S(0, 1, 0, 100), S(5, 2, 0, 100, {"obsidian": 6}, action="loot chest"),
                S(10, 3, 0, 0, {"obsidian": 7}, action="mine_obsidian")],
               {"chests_0": dict(CHEST, dim="overworld")})
    assert run("obsidian_source", tl) == []


def test_obsidian_empty_knowledge_uses_proximity_only():
    # never came within 32 blocks of the chest -> nothing to judge against
    assert run("obsidian_source", _mining_tl({})) == []
    # passed within 20 blocks of the chest earlier, then mined far away
    tl = tl_of([S(0, 1, 0, 80), S(10, 2, 0, 0, {"obsidian": 2}), S(20, 3, 0, 0, {"obsidian": 4})],
               source="human_poller")
    f = run("obsidian_source", tl)
    assert len(f) == 1 and f[0].evidence["knowledge_basis"] == "proximity_32"
    assert "within 32 blocks" in f[0].message


# ---------------------------------------------------------------- portal_method
def test_portal_full_build_when_site_has_frame():
    k = {"entryPortal": {"x": 50, "y": 64, "z": 0, "dim": "overworld"}}
    tl = tl_of([S(0, 1, 50, 0, {"obsidian": 10}), S(10, 2, 50, 0, {"obsidian": 5}),
                S(20, 3, 50, 0, {"obsidian": 0}), S(25, 4, 50, 0, dim="the_nether")], k,
               events=[{"t": 25, "line": 4, "type": "nether_entered"}])
    f = run("portal_method", tl)
    assert len(f) == 1
    assert f[0].evidence["extra_blocks"] == 3 and f[0].evidence["existing_frame_blocks"] == 3
    assert f[0].cost_s == pytest.approx(3 * 0.5)  # obsidian not mined -> placement time
    assert 4 in f[0].lines


def test_portal_using_frame_is_fine():
    k = {"entryPortal": {"x": 50, "y": 64, "z": 0, "dim": "overworld"}}
    tl = tl_of([S(0, 1, 50, 0, {"obsidian": 7}), S(10, 2, 50, 0, {"obsidian": 0}),
                S(25, 3, 50, 0, dim="the_nether")], k,
               events=[{"t": 25, "line": 3, "type": "nether_entered"}])
    assert run("portal_method", tl) == []


# ---------------------------------------------------------------- overworld travel
def test_overworld_travel_flagged_when_nether_known():
    k = {"entryPortal": {"x": 50, "y": 64, "z": 0, "dim": "overworld"},
         "endPortal": {"x": 4000, "y": 30, "z": 0, "dim": "overworld"}}
    samples = [S(i * 10, i + 1, i * 71.27, 0, {"flint_and_steel": 1, "obsidian": 17})
               for i in range(41)]  # 2850 blocks east, 400 s, portal lightable (7 entry + 10 exit)
    f = run("overworld_travel_when_nether_known", tl_of(samples, k))
    assert len(f) == 1
    ev = f[0].evidence
    assert ev["overworld_toward_blocks"] == pytest.approx(2850.8, abs=0.5)
    nether_s = (50 + 3950 / 8) / SPRINT_BPS + 8 + 10 * 0.5  # portal + /8 + 2x4 s transfers + exit frame
    assert f[0].cost_s == pytest.approx(400 - nether_s, abs=0.1)
    assert {x["name"] for x in ev["knowledge_used"]} == {"endPortal", "entryPortal"}


def test_overworld_travel_not_flagged_before_portal_usable():
    k = {"entryPortal": {"x": 50, "y": 64, "z": 0, "dim": "overworld"},
         "endPortal": {"x": 4000, "y": 30, "z": 0, "dim": "overworld"}}
    samples = [S(i * 10, i + 1, i * 71.27, 0) for i in range(41)]  # no flint_and_steel, no entry
    assert run("overworld_travel_when_nether_known", tl_of(samples, k)) == []


def test_overworld_travel_not_flagged_without_known_portal():
    k = {"endPortal": {"x": 4000, "y": 30, "z": 0, "dim": "overworld"}}
    samples = [S(i * 10, i + 1, i * 71.27, 0) for i in range(41)]
    assert run("overworld_travel_when_nether_known", tl_of(samples, k)) == []


# ---------------------------------------------------------------- unneeded visit
def test_unneeded_structure_visit():
    k = {"entryPortal": {"x": 50, "y": 64, "z": 0, "dim": "overworld"}}
    samples = [S(t, t + 1, -300 + (t % 3), 0) for t in range(0, 41)]  # 40 s at the village
    f = run("unneeded_structure_visit", tl_of(samples, k))
    assert [x.evidence["feature"]["name"] for x in f] == ["village"]
    assert f[0].evidence["dwell_s"] == pytest.approx(40)
    assert f[0].cost_s == pytest.approx(40 - 32 / SPRINT_BPS, abs=0.01)


def test_visit_to_known_feature_not_flagged():
    k = {"village": {"x": -300, "y": 64, "z": 0, "dim": "overworld"}}
    samples = [S(t, t + 1, -300, 0) for t in range(0, 41)]
    assert run("unneeded_structure_visit", tl_of(samples, k)) == []


# ---------------------------------------------------------------- stage_time
def test_stage_time_report_only():
    ev = [{"t": 0, "line": 1, "type": "start"}, {"t": 300, "line": 50, "type": "nether_entered"},
          {"t": 400, "line": 90, "type": "nether_exited"}]
    pro = [{"split": "nether_entry", "time_s": 100}, {"split": "nether_exit", "time_s": 200}]
    f = run("stage_time", tl_of([], events=ev), pro_splits=pro)
    assert len(f) == 1 and f[0].evidence["stage"] == "start->nether_entry"
    assert f[0].evidence["excess_s"] == 200 and f[0].cost_s == 0 and f[0].lines == [1, 50]
    assert run("stage_time", tl_of([], events=ev)) == []


# ---------------------------------------------------------------- path_efficiency
def test_path_efficiency_flags_zigzag_only():
    k = {"entryPortal": {"x": 50, "y": 64, "z": 0, "dim": "overworld"}}
    straight = [S(i, i + 1, i * 5, 0) for i in range(11)]
    assert run("path_efficiency", tl_of(straight, k)) == []
    legs = path_legs(tl_of(straight, k), {"seed": SEED})
    assert legs and legs[0]["path_ratio"] == pytest.approx(1.0, abs=0.01)
    zig = [S(i, i + 1, i * 5, 40 if i % 2 else 0) for i in range(11)]
    f = run("path_efficiency", tl_of(zig, k))
    assert len(f) == 1 and f[0].evidence["path_ratio"] > 2.0
    assert f[0].cost_s == pytest.approx((f[0].evidence["path_blocks"] - 50) / SPRINT_BPS, abs=0.01)


def test_deterministic_and_pure():
    k = {"chests_0": dict(CHEST, dim="overworld")}
    tl = _mining_tl(k)
    a = [repr(x) for c in sorted(SEED_REGISTRY) for x in run(c, tl)]
    b = [repr(x) for c in sorted(SEED_REGISTRY) for x in run(c, tl)]
    assert a == b and tl.knowledge == {"chests_0": dict(CHEST, dim="overworld")}
