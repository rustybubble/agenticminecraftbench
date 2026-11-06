"""Each micro/safety detector fires on a minimal crafted timeline and is silent on a clean one."""
from pathlib import Path

import pytest

from splitcheck import detectors as D
from splitcheck.timeline import Sample, Timeline, load_timeline

FX = Path(__file__).parent / "fixtures" / "events"
BASE_INV = {"oak_planks": 4}


def S(t, line, pos=(0.0, 64.0, 0.0), inv=None, **kw):
    kw.setdefault("dim", "overworld")
    return Sample(t=t, line=line, pos=pos, inv=dict(BASE_INV if inv is None else inv), **kw)


def TL(samples, events=None, knowledge=None, meta=None, source="agent"):
    return Timeline(source=source, samples=samples, events=events or [], knowledge=knowledge or {},
                    meta=meta or {"duration_s": samples[-1].t if samples else 0.0})


def walk(n=6, dt=2.0, step=10.0, start_line=1, **kw):
    """Steady straight walk, inventory unchanged: the clean baseline."""
    return [S(i * dt, start_line + i, pos=(i * step, 64.0, 0.0), **kw) for i in range(n)]


def act(t_dec, t_res, line, action, pos0, pos1, inv0=None, inv1=None, failed=False, desc=None, **kw):
    """decision sample + result sample pair (agent log shape)."""
    d = S(t_dec, line, pos=pos0, inv=inv0, kind="decision", action=action, health=20.0, food=20.0)
    r = S(t_res, line + 1, pos=pos1, inv=inv1 if inv1 is not None else inv0, kind="result", action=action,
          action_failed=failed, action_desc=desc or action, result="FAILED x" if failed else "done", **kw)
    return [d, r]


CLEAN = TL(walk())


def codes(fs):
    return [f.code for f in fs]


@pytest.mark.parametrize("code", sorted(set(D.REGISTRY) & {
    "failed_action", "no_progress", "idle", "action_loop", "oscillation", "place_then_recover",
    "mining_in_water", "lost_drop", "excess_food", "excess_tools", "excess_materials",
    "overshoot_waypoint", "damage_taken", "death"}))
def test_silent_on_clean(code):
    assert D.REGISTRY[code](CLEAN, {}) == []


def test_finding_shape_and_thresholds():
    assert "idle_min_s" in D.THRESHOLDS and D.THRESHOLDS["loop_min"] == 3
    tl = TL(act(0.0, 4.0, 1, "mine_log", (0, 64, 0), (5, 64, 0), failed=True))
    f = D.failed_action(tl, {})[0]
    assert (f.code, f.category, f.cost_s, f.lines, f.t_start, f.t_end) == ("failed_action", "micro", 4.0,
                                                                            [2], 0.0, 4.0)


def test_failed_action():
    tl = TL(act(1.0, 26.0, 1, "build_portal", (0, 64, 0), (0, 64, 0), failed=True))
    fs = D.failed_action(tl, {})
    assert codes(fs) == ["failed_action"] and fs[0].cost_s == 25.0 and fs[0].severity == "medium"


def test_no_progress():
    tl = TL(act(1.0, 4.0, 1, "go_somewhere", (0, 64, 0), (0, 64, 0)))
    fs = D.no_progress(tl, {})
    assert codes(fs) == ["no_progress"] and fs[0].cost_s == 3.0 and fs[0].lines == [1, 2]
    # world-effect actions (portal lighting) are not "no progress"
    assert D.no_progress(TL(act(1.0, 4.0, 1, "light_portal", (0, 64, 0), (0, 64, 0))), {}) == []


def test_idle_excludes_api_wait():
    # human: standing still 0..6 s
    tl = TL([S(t, i + 1) for i, t in enumerate([0, 2, 4, 6])] + [S(8, 5, pos=(10, 64, 0))], source="human_poller")
    fs = D.idle(tl, {})
    assert codes(fs) == ["idle"] and fs[0].cost_s == 6.0 and fs[0].lines == [1, 4]
    # agent: result at 1, model answered at 6 (5 s API wait), result 7 -> only 1 s of player idle
    a = act(0.0, 1.0, 1, "look", (0, 64, 0), (0, 64, 0)) + act(6.0, 7.0, 3, "look2", (0, 64, 0), (0, 64, 0))
    assert D.idle(TL(a), {}) == []
    # explicit wait action
    w = D.idle(TL(act(0.0, 5.0, 1, "wait_for_planner", (0, 64, 0), (0, 64, 0))), {})
    assert any(f.evidence.get("explicit_wait") for f in w)


def test_action_loop():
    s = []
    for k in range(3):
        s += act(k * 4.0, k * 4.0 + 3.0, 1 + 2 * k, "collect_drop", (0, 64, 0), (0, 64, 0), failed=k != 1)
    fs = D.action_loop(TL(s), {})
    assert codes(fs) == ["action_loop"] and fs[0].evidence["count"] == 3 and fs[0].cost_s == 9.0
    # three productive repeats are fine
    ok = []
    for k in range(3):
        ok += act(k * 4.0, k * 4.0 + 3.0, 1 + 2 * k, "walk", (k * 10, 64, 0), (k * 10 + 10, 64, 0))
    assert D.action_loop(TL(ok), {}) == []


def test_oscillation():
    xs = [0.5, 6, 0.5, 6, 0.5, 6]
    tl = TL([S(i * 2.0, i + 1, pos=(x, 64.0, 0.5)) for i, x in enumerate(xs)], source="human_poller")
    fs = D.oscillation(tl, {})
    assert codes(fs) == ["oscillation"] and fs[0].evidence["visits"] == 3 and fs[0].cost_s == 8.0


def test_place_then_recover():
    inv_t = {"crafting_table": 1, "oak_planks": 4}
    s = (act(0, 1, 1, "place_crafting_table", (0, 64, 0), (0, 64, 0), inv0=inv_t, inv1={"oak_planks": 4})
         + act(2, 3, 3, "craft_pickaxe", (0, 64, 0), (0, 64, 0), inv0={"oak_planks": 4},
               inv1={"oak_planks": 1, "wooden_pickaxe": 1})
         + act(4, 8, 5, "mine_crafting_table", (0, 64, 0), (0, 64, 0), inv0={"oak_planks": 1, "wooden_pickaxe": 1},
               inv1={"oak_planks": 1, "wooden_pickaxe": 1, "crafting_table": 1}))
    fs = D.place_then_recover(TL(s), {})
    assert codes(fs) == ["place_then_recover"] and fs[0].lines == [2, 6] and fs[0].cost_s == 4.0
    # a crafted second table is not a recovery
    s2 = act(0, 1, 1, "place_crafting_table", (0, 64, 0), (0, 64, 0), inv0=inv_t, inv1={"oak_planks": 4}) + \
        act(2, 3, 3, "craft_table", (0, 64, 0), (0, 64, 0), inv0={"oak_planks": 4}, inv1={"crafting_table": 1})
    assert D.place_then_recover(TL(s2), {}) == []


def test_mining_in_water_flag_and_text():
    s = [S(0, 1, inv={}), S(1, 2, inv={"oak_log": 1}, in_water=True), S(2, 3, inv={"oak_log": 2}, in_water=True)]
    fs = D.mining_in_water(TL(s, source="human_poller"), {})
    assert codes(fs) == ["mining_in_water"] and fs[0].lines == [2, 3] and fs[0].cost_s == 1.6
    # same gains on dry land: silent
    dry = [S(0, 1, inv={}), S(1, 2, inv={"oak_log": 1}, in_water=False)]
    assert D.mining_in_water(TL(dry, source="human_poller"), {}) == []
    # agent without in_water: action text mentions water + failed collect
    a = act(0, 6, 1, "mine_sand", (0, 60, 0), (0, 60, 0), failed=True, desc="Mine sand from the water")
    assert codes(D.mining_in_water(TL(a), {})) == ["mining_in_water"]


def test_lost_drop():
    s = act(0, 3, 1, "mine_log", (0, 64, 0), (1, 64, 0))
    fs = D.lost_drop(TL(s), {})
    assert codes(fs) == ["lost_drop"] and fs[0].cost_s == 3.0
    got = act(0, 3, 1, "mine_log", (0, 64, 0), (1, 64, 0), inv1={"oak_planks": 4, "oak_log": 1})
    assert D.lost_drop(TL(got), {}) == []


def test_excess_food():
    s = act(0, 20, 1, "hunt_cow", (0, 64, 0), (30, 64, 0), inv1={"oak_planks": 4, "cooked_beef": 5})
    fs = D.excess_food(TL(s, meta={"difficulty": "peaceful"}), {})
    assert codes(fs) == ["excess_food"] and fs[0].cost_s == 20.0
    # easy, hungry (food 10) and later eaten: not excess
    s2 = act(0, 20, 1, "hunt_cow", (0, 64, 0), (30, 64, 0), inv1={"oak_planks": 4, "cooked_beef": 5})
    s2[0].food = 10.0
    s2 += [S(21, 3, pos=(30, 64, 0), inv={"oak_planks": 4, "cooked_beef": 4})]
    assert D.excess_food(TL(s2, meta={"difficulty": "easy"}), {}) == []
    # easy, full food bar, never eaten: excess
    assert codes(D.excess_food(TL(s, meta={"difficulty": "easy"}), {})) == ["excess_food"]


def test_excess_tools():
    s = (act(0, 2, 1, "craft_pickaxe", (0, 64, 0), (0, 64, 0), inv0={"oak_planks": 6},
             inv1={"oak_planks": 3, "wooden_pickaxe": 1})
         + act(3, 5, 3, "craft_pickaxe", (0, 64, 0), (0, 64, 0), inv0={"oak_planks": 3},
               inv1={"wooden_pickaxe": 2}))
    fs = D.excess_tools(TL(s), {})
    reasons = sorted(f.evidence["reason"] for f in fs)
    assert reasons == ["duplicate", "never_used"]
    used = (act(0, 2, 1, "craft_pickaxe", (0, 64, 0), (0, 64, 0), inv0={"oak_planks": 3},
                inv1={"wooden_pickaxe": 1})
            + act(3, 5, 3, "mine_stone", (0, 64, 0), (0, 64, 0), inv0={"wooden_pickaxe": 1},
                  inv1={"wooden_pickaxe": 1, "cobblestone": 3}))
    assert D.excess_tools(TL(used), {}) == []


def test_excess_materials():
    s = [S(0, 1, inv={}), S(10, 2, inv={"oak_log": 10}), S(20, 3, inv={"oak_log": 9, "oak_planks": 4})]
    fs = D.excess_materials(TL(s, source="human_poller"), {})
    assert codes(fs) == ["excess_materials"]
    f = fs[0]
    assert f.evidence["group"] == "wood" and f.evidence["leftover"] == 10.0 and f.evidence["excess"] == 6.0
    assert f.cost_s == 12.0  # 6 surplus logs x 2.0 s estimated per log
    lean = [S(0, 1, inv={}), S(10, 2, inv={"oak_log": 3})]
    assert D.excess_materials(TL(lean, source="human_poller"), {}) == []


def test_overshoot_waypoint_knowledge_and_return():
    k = {"entry_portal": {"x": 20.0, "y": 64.0, "z": 0.0, "dim": "overworld"}}
    xs = [0, 10, 19, 20, 30, 21]
    s = [S(i * 1.0, i + 1, pos=(x, 64.0, 0.0)) for i, x in enumerate(xs)]
    fs = D.overshoot_waypoint(TL(s, knowledge=k, source="human_poller"), {})
    assert codes(fs) == ["overshoot_waypoint"] and fs[0].evidence["target"] == "entry_portal"
    assert fs[0].cost_s == 2.0 and fs[0].lines == [4, 5, 6]
    # pass by and never come back (no action names it): silent
    s2 = [S(i * 1.0, i + 1, pos=(x, 64.0, 0.0)) for i, x in enumerate([0, 10, 20, 30, 40, 50])]
    assert D.overshoot_waypoint(TL(s2, knowledge=k, source="human_poller"), {}) == []


def test_damage_taken_classifies():
    lava = [S(0, 1, health=20.0), S(1, 2, health=16.0, in_lava=True), S(2, 3, health=12.0, in_lava=True)]
    f = D.damage_taken(TL(lava, source="human_poller"), {})[0]
    assert f.evidence["cause"] == "lava" and f.evidence["hp_lost"] == 8.0 and f.cost_s == 1.0
    fall = [S(0, 1, pos=(0, 80, 0), health=20.0), S(1, 2, pos=(0, 70, 0), health=20.0),
            S(2, 3, pos=(0, 64, 0), health=13.0)]
    f = D.damage_taken(TL(fall, source="human_poller"), {})[0]
    assert f.evidence["cause"] == "fall" and f.severity == "medium"


def test_death_with_return():
    s = [S(0, 1, pos=(100, 64, 0), health=20.0), S(5, 2, pos=(100, 64, 0), health=0.0),
         S(6, 3, pos=(0, 64, 0), health=20.0), S(40, 5, pos=(98, 64, 0), health=20.0)]
    ev = [{"t": 5.0, "line": 2, "type": "death_suspected", "pos": (100.0, 64.0, 0.0)}]
    fs = D.death(TL(s, events=ev, source="human_poller", meta={"duration_s": 50.0}), {})
    assert codes(fs) == ["death"] and fs[0].cost_s == 35.0 and fs[0].lines == [2, 5]


def test_registry_and_wasteful_fixture():
    for c in ("failed_action", "no_progress", "idle", "action_loop", "oscillation", "place_then_recover",
              "mining_in_water", "lost_drop", "excess_food", "excess_tools", "excess_materials",
              "overshoot_waypoint", "damage_taken", "death"):
        assert c in D.REGISTRY
    fs = D.run_all(load_timeline(FX / "wasteful_run.jsonl"), {},
                   codes={"failed_action", "action_loop", "place_then_recover", "excess_food",
                          "overshoot_waypoint", "death", "lost_drop"})
    got = {f.code: f for f in fs}
    assert set(got) == {"failed_action", "action_loop", "place_then_recover", "excess_food",
                        "overshoot_waypoint", "death", "lost_drop"}
    assert got["place_then_recover"].lines == [14, 18]
    assert [f.lines[0] for f in fs if f.code == "failed_action"] == [20, 24, 28]
    # deterministic
    again = D.run_all(load_timeline(FX / "wasteful_run.jsonl"), {})
    assert [(f.code, f.lines, f.cost_s) for f in again] == \
        [(f.code, f.lines, f.cost_s) for f in D.run_all(load_timeline(FX / "wasteful_run.jsonl"), {})]


def test_idle_excuses_portal_transfer_and_mining():
    still = [S(t, i + 1) for i, t in enumerate([0, 1, 2, 3, 4])]
    portal = TL(still + [S(4.5, 6, pos=(0, 64, 0), dim="the_nether")], source="human_poller")
    assert D.idle(portal, {}) == []
    mining = TL(still + [S(4.5, 6, inv={"oak_planks": 4, "obsidian": 1})], source="human_poller")
    assert D.idle(mining, {}) == []
    end = TL([S(t, i + 1, dim="the_end") for i, t in enumerate([0, 5, 10])], source="human_poller")
    assert D.idle(end, {}) == []
