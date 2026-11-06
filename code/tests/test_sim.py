"""Tests for splitcheck.sim (state simulator) and splitcheck.rules_1165."""
from __future__ import annotations

import json

import pytest

from splitcheck import rules_1165 as R
from splitcheck import sim
from splitcheck.sim import DEFAULT_COSTS, load_costs, simulate


def mk(inv=None, dim="overworld", pos=(0, 64, 0), locs=None, world=None, difficulty="peaceful"):
    return {
        "id": "t",
        "difficulty": difficulty,
        "state": {
            "dimension": dim,
            "position": None if pos is None else {"x": pos[0], "y": pos[1], "z": pos[2]},
            "inventory": dict(inv or {}),
            "known_locations": locs or {},
            "world": world or {},
            "elapsed_s": 0,
        },
    }


def run(task, *actions):
    return simulate(task, {"actions": list(actions)}, DEFAULT_COSTS)


def A(action, **kw):
    return {"action": action, **kw}


# ------------------------------------------------------------------ costs

def test_defaults_are_estimates():
    for k, e in DEFAULT_COSTS.items():
        assert e["source"] == "estimate" and e["verified"] is False, k


def test_load_costs_merges_file(tmp_path):
    p = tmp_path / "time_costs.json"
    p.write_text(json.dumps({"actions": {"craft": {"seconds": 9.0, "per": "item", "source": "vod", "verified": True}}}))
    c = load_costs(p)
    assert c["craft"]["seconds"] == 9.0 and c["craft"]["verified"] is True
    assert c["loot_chest"]["seconds"] == 3.0  # default kept
    assert load_costs(tmp_path / "missing.json")["craft"]["seconds"] == 1.5


def test_travel_priced_by_distance():
    r = run(mk(), A("travel", to={"x": 712.7, "y": 64, "z": 0}))
    assert r.legal and r.time_s == pytest.approx(100.0, abs=0.1)


def test_action_prices():
    t = mk(inv={"obsidian": 10, "flint_and_steel": 1, "oak_log": 1, "gold_ingot": 10, "golden_boots": 1,
                "white_bed": 2, "diamond_pickaxe": 1})
    r = run(t, A("mine", block="obsidian", count=2), A("craft", item="oak_planks", count=4),
            A("build_portal", method="chest_obsidian"), A("light_portal", **{"with": "flint_and_steel"}),
            A("enter_portal"), A("barter", gold_ingots=10), A("bed_explode", count=2))
    assert r.legal, r.reason
    times = [s["time_s"] for s in r.steps]
    assert times == pytest.approx([18.8, 1.5, 12.0, 1.0, 4.0, 60.0, 12.0])
    assert r.time_s == pytest.approx(sum(times))


# ------------------------------------------------------------------ legal chains

def test_full_legal_chain_and_tags():
    locs = {"chest_1": {"x": 10, "y": 64, "z": 0, "dimension": "overworld"},
            "stronghold": {"x": 800, "y": 30, "z": 800, "dimension": "overworld"}}
    world = {"chests": {"chest_1": {"obsidian": 10, "flint_and_steel": 1}},
             "structures": {"stronghold": {"type": "end_portal", "notes": "2 frames already filled"}}}
    t = mk(inv={"ender_pearl": 12, "blaze_rod": 5, "white_bed": 3}, locs=locs, world=world)
    r = run(t,
            A("loot_chest", at="chest_1"),
            A("build_portal", method="chest_obsidian"),
            A("light_portal", **{"with": "flint_and_steel"}),
            A("enter_portal"),
            A("travel", to={"x": 100, "y": 64, "z": 100}),
            A("craft", item="blaze_powder", count=10),
            A("craft", item="ender_eye", count=10),
            )
    assert r.legal, r.reason
    fs = r.final_state
    assert fs["dimension"] == "the_nether"
    assert fs["position"]["x"] == pytest.approx(100)
    assert fs["inventory"]["ender_eye"] == 10 and "blaze_rod" not in fs["inventory"]
    assert "chest_obsidian_portal" in r.techniques_used and "nether_travel_8to1" in r.techniques_used
    # back to overworld via the linked portal at (1.25, 0)
    r2 = run(t, A("loot_chest", at="chest_1"), A("build_portal", method="chest_obsidian"),
             A("light_portal", **{"with": "flint_and_steel"}), A("enter_portal"), A("enter_portal"))
    assert r2.legal and r2.final_state["dimension"] == "overworld"


def test_enter_portal_maps_coords_div8():
    t = mk(inv={"obsidian": 10, "fire_charge": 1}, pos=(-1130, 34, 856))
    r = run(t, A("build_portal", method="chest_obsidian"), A("light_portal", **{"with": "fire_charge"}),
            A("enter_portal"))
    assert r.legal
    p = r.final_state["position"]
    assert (p["x"], p["z"]) == pytest.approx((-141.25, 107.0))
    assert "fire_charge" not in r.final_state["inventory"]


def test_end_portal_triangulation_and_entry():
    locs = {"sh": {"x": 1600, "y": 30, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"sh": {"type": "end_portal", "frames_filled": 2}}}
    t = mk(inv={"ender_eye": 12}, locs=locs, world=world)
    r = run(t, A("throw_eye", at={"x": 0, "y": 64, "z": 0}), A("throw_eye", at={"x": 300, "y": 64, "z": 300}),
            A("travel", to="sh"), A("place_eyes", count=10), A("enter_portal"))
    assert r.legal, r.reason
    assert r.final_state["dimension"] == "the_end"
    # 2 throws at the expected 20% break rate -> floor(0.4) = 0 broken; 12 - 10 placed = 2 left
    assert r.final_state["inventory"] == {"ender_eye": 2}
    assert "triangulation" in r.techniques_used


def test_already_active_end_portal_from_facts():
    locs = {"sh": {"x": 0, "y": 30, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"sh": {"type": "end_portal", "notes": ""}},
             "facts": ["the End portal is already active"]}
    r = run(mk(locs=locs, world=world), A("enter_portal"))
    assert r.legal, r.reason


def test_ruined_portal_completion():
    locs = {"rp": {"x": 0, "y": 64, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"rp": {"type": "ruined_portal", "missing_obsidian": 3}}}
    r = run(mk(inv={"obsidian": 3, "flint_and_steel": 1}, locs=locs, world=world),
            A("build_portal", method="complete_ruined"), A("light_portal", **{"with": "flint_and_steel"}),
            A("enter_portal"))
    assert r.legal and "ruined_portal_completion" in r.techniques_used
    r = run(mk(inv={"obsidian": 2}, locs=locs, world=world), A("build_portal", method="complete_ruined"))
    assert not r.legal and "needs 3 obsidian" in r.reason


def test_lava_and_mine_portal_tags():
    r = run(mk(inv={"water_bucket": 1, "bucket": 1}), A("build_portal", method="bucket_lava"))
    assert r.legal and r.techniques_used == ["lava_pool_portal"] and r.time_s == 30.0
    r = run(mk(inv={"diamond_pickaxe": 1}), A("mine", block="obsidian", count=10),
            A("build_portal", method="mine_obsidian"))
    assert r.legal and "mine_obsidian_portal" in r.techniques_used
    assert r.time_s == pytest.approx(94.0)


def test_crafting_chain_from_logs():
    r = run(mk(inv={"birch_log": 3, "cobblestone": 3}),
            A("craft", item="birch_planks", count=12), A("craft", item="crafting_table", count=1),
            A("craft", item="stick", count=4), A("craft", item="wooden_pickaxe", count=1),
            A("craft", item="stone_pickaxe", count=1))
    assert r.legal, r.reason
    inv = r.final_state["inventory"]
    assert inv == {"birch_planks": 3, "crafting_table": 1, "wooden_pickaxe": 1, "stone_pickaxe": 1}


def test_gravel_flint_expected_value():
    r = run(mk(inv={"iron_ingot": 1}), A("mine", block="gravel", count=10), A("craft", item="flint_and_steel", count=1))
    assert r.legal, r.reason
    assert sim.STOCHASTIC_NOTE in r.steps[0]["note"]
    r = run(mk(), A("mine", block="gravel", count=9))
    assert "flint" not in r.final_state["inventory"]  # floor(0.9) = 0


def test_barter_expected_value_and_tag():
    r = run(mk(dim="the_nether", inv={"gold_ingot": 100, "golden_helmet": 1}), A("barter", gold_ingots=100))
    assert r.legal and "piglin_barter" in r.techniques_used
    assert r.final_state["inventory"]["ender_pearl"] == 6  # floor(100 * 10/459 * 3)
    assert sim.STOCHASTIC_NOTE in r.steps[0]["note"]
    assert R.BARTER_TOTAL_WEIGHT == 459
    assert all(e["verified"] is False for e in R.BARTER_TABLE.values())


def test_blaze_kill_on_easy():
    r = run(mk(dim="the_nether", difficulty="easy"), A("kill", mob="blaze", count=7))
    assert r.legal and r.final_state["inventory"]["blaze_rod"] == 3
    assert r.time_s == 35.0


def test_piglin_kill_on_peaceful_ok():
    assert run(mk(dim="the_nether"), A("kill", mob="piglin", count=1)).legal


def test_reset_ends_plan():
    r = run(mk(), A("reset"), A("light_portal", **{"with": "flint_and_steel"}))
    assert r.legal and r.final_state["reset"] and r.steps[1]["note"].startswith("ignored")


def test_deterministic():
    t = mk(dim="the_nether", inv={"gold_ingot": 30, "golden_boots": 1})
    a = run(t, A("barter", gold_ingots=30))
    b = run(t, A("barter", gold_ingots=30))
    assert a == b


# ------------------------------------------------------------------ must be ILLEGAL

def illegal(task, *actions, step=None, contains=None):
    r = run(task, *actions)
    assert r.legal is False, r
    assert r.reason
    if step is not None:
        assert r.failed_step == step, r.reason
    if contains:
        assert contains in r.reason, r.reason
    return r


def test_light_without_fire():
    illegal(mk(inv={"obsidian": 10}), A("build_portal", method="chest_obsidian"),
            A("light_portal", **{"with": "flint_and_steel"}), step=1, contains="flint_and_steel")


def test_ender_eye_without_powder():
    illegal(mk(inv={"ender_pearl": 5, "blaze_rod": 2}), A("craft", item="ender_eye", count=1), step=0,
            contains="blaze_powder")


def test_mine_obsidian_without_diamond_pick():
    illegal(mk(inv={"iron_pickaxe": 1}), A("mine", block="obsidian", count=10), step=0, contains="diamond_pickaxe")
    illegal(mk(), A("build_portal", method="mine_obsidian"), contains="diamond_pickaxe")


def test_enter_portal_without_lit_portal():
    illegal(mk(), A("enter_portal"), step=0)
    illegal(mk(inv={"obsidian": 10}), A("build_portal", method="chest_obsidian"), A("enter_portal"),
            step=1, contains="not lit")
    # portal built elsewhere does not count
    illegal(mk(inv={"obsidian": 10, "flint_and_steel": 1}), A("build_portal", method="chest_obsidian"),
            A("light_portal", **{"with": "flint_and_steel"}), A("travel", to={"x": 100, "y": 64, "z": 0}),
            A("enter_portal"), step=3)


def test_travel_to_other_dimension():
    locs = {"fort": {"x": 50, "y": 70, "z": 50, "dimension": "the_nether"}}
    illegal(mk(locs=locs), A("travel", to="fort"), step=0, contains="enter_portal")
    illegal(mk(), A("travel", to={"x": 5, "y": 64, "z": 5}, dimension="the_nether"), step=0)


def test_loot_chest_twice_or_unknown():
    locs = {"c": {"x": 0, "y": 64, "z": 0, "dimension": "overworld"}}
    world = {"chests": {"c": {"obsidian": 4}}}
    illegal(mk(locs=locs, world=world), A("loot_chest", at="c"), A("loot_chest", at="c"), step=1,
            contains="already looted")
    illegal(mk(locs=locs, world=world), A("loot_chest", at="nope"), step=0, contains="state.world.chests")


def test_barter_without_gold_armor():
    illegal(mk(dim="the_nether", inv={"gold_ingot": 10}), A("barter", gold_ingots=10), step=0, contains="gold armor")


def test_bed_explode_in_overworld():
    illegal(mk(inv={"red_bed": 4}), A("bed_explode", count=1), step=0,
            contains="beds only explode in the_nether/the_end")
    assert run(mk(dim="the_end", inv={"red_bed": 4}), A("bed_explode", count=4)).techniques_used == ["bed_explosion"]


def test_place_eyes_limits():
    locs = {"sh": {"x": 0, "y": 30, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"sh": {"type": "end_portal", "frames_filled": 3}}}
    illegal(mk(inv={"ender_eye": 12}, locs=locs, world=world), A("place_eyes", count=10), contains="9 empty frames")
    illegal(mk(inv={"ender_eye": 5}, locs=locs, world=world), A("place_eyes", count=9), contains="5 ender_eye")
    r = run(mk(inv={"ender_eye": 9}, locs=locs, world=world), A("place_eyes", count=9), A("enter_portal"))
    assert r.legal, r.reason


def test_kill_hostile_on_peaceful():
    for mob in ("blaze", "enderman", "piglin_brute"):
        illegal(mk(dim="the_nether"), A("kill", mob=mob, count=1), step=0, contains="Peaceful")


def test_throw_eye_consumes_and_needs_eye():
    illegal(mk(), A("throw_eye", at={"x": 0, "y": 64, "z": 0}), contains="ender_eye")
    r = run(mk(inv={"ender_eye": 2}), A("throw_eye", at={"x": 0, "y": 64, "z": 0}))
    assert r.final_state["inventory"]["ender_eye"] == 2  # 80% drop back: floor(0.2 * 1) = 0 broken
    # one throw position only -> no triangulation tag
    locs = {"sh": {"x": 0, "y": 30, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"sh": {"type": "end_portal", "frames_filled": 0}}}
    r = run(mk(inv={"ender_eye": 3}, locs=locs, world=world), A("throw_eye", at={"x": 0, "y": 64, "z": 0}),
            A("throw_eye", at={"x": 0, "y": 64, "z": 0}), A("place_eyes", count=1))
    assert r.legal and "triangulation" not in r.techniques_used


def test_craft_needs_table():
    illegal(mk(inv={"iron_ingot": 3}), A("craft", item="bucket", count=1), contains="crafting_table")
    assert run(mk(inv={"iron_ingot": 3, "crafting_table": 1}), A("craft", item="bucket", count=1)).legal


def test_failed_plan_stops_and_reports_time_so_far():
    r = illegal(mk(), A("travel", to={"x": 71.27, "y": 64, "z": 0}), A("enter_portal"), step=1)
    assert r.time_s == pytest.approx(10.0, abs=0.01)
    assert r.steps[-1]["ok"] is False and len(r.steps) == 2
