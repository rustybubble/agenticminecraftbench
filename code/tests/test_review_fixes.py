"""Regression tests for the reviewer findings fixed in the fixer pass."""
import json
import shutil
from pathlib import Path

import pytest

from splitcheck import answers as A
from splitcheck import check, logeval
from splitcheck import rules_1165 as R
from splitcheck.sim import DEFAULT_COSTS, simulate

HERE = Path(__file__).parent
FIXTURES = HERE / "fixtures"
REPO = HERE.parent.parent


def mk(inv=None, dim="overworld", pos=(0, 64, 0), locs=None, world=None, version="1.16.5", split=None):
    t = {"id": "t", "version": version, "difficulty": "peaceful",
         "state": {"dimension": dim, "position": {"x": pos[0], "y": pos[1], "z": pos[2]},
                   "inventory": dict(inv or {}), "known_locations": locs or {}, "world": world or {},
                   "elapsed_s": 0}}
    if split:
        t["split"] = split
    return t


def run(task, *actions):
    return simulate(task, {"actions": list(actions)}, DEFAULT_COSTS)


def act(a, **kw):
    return {"action": a, **kw}


def _load(root, sub, tid):
    return json.loads((root / sub / f"{tid}.json").read_text())


# ---- every real reference / alternate / broken case scores as declared
@pytest.mark.skipif(not (REPO / "reference").is_dir(), reason="repo reference/ not present")
def test_real_reference_self_test_all_pass():
    cases = check.self_test(REPO)
    bad = [c for c in cases if not c["pass"]]
    assert cases and not bad, bad


# ---- bucket_lava at a lava pool needs only the water bucket
def test_bucket_lava_at_lava_pool_needs_only_water_bucket():
    locs = {"pool": {"x": 0, "y": 64, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"pool": {"type": "lava_pool"}}}
    r = run(mk({"water_bucket": 1, "flint_and_steel": 1}, locs=locs, world=world),
            act("build_portal", method="bucket_lava"), act("light_portal", **{"with": "flint_and_steel"}),
            act("enter_portal"))
    assert r.legal, r.reason
    # away from a pool a bucket is still needed
    r = run(mk({"water_bucket": 1}), act("build_portal", method="bucket_lava"))
    assert not r.legal and "bucket" in r.reason


# ---- complete_ruined: block list parsed (T05 layout -> 7), unknown count is not free
T05_NOTES = ("The ruined portal frame stands in the vertical plane x = -285. Its remaining blocks (z, y) are: "
             "obsidian at (258,66), (259,66), (260,66), (261,68), (261,69), (259,70), (260,70), (261,70); "
             "crying obsidian at (261,66) and (261,67). Other positions in that plane near the frame are air.")


def test_ruined_block_list_gives_7():
    from splitcheck.sim import ruined_missing_from_blocks
    assert ruined_missing_from_blocks(T05_NOTES) == 7
    locs = {"rp": {"x": 0, "y": 64, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"rp": {"type": "ruined_portal", "notes": T05_NOTES}}}
    r = run(mk({"obsidian": 21}, locs=locs, world=world), act("build_portal", method="complete_ruined"))
    assert r.legal and r.final_state["inventory"]["obsidian"] == 14
    r = run(mk({"obsidian": 6}, locs=locs, world=world), act("build_portal", method="complete_ruined"))
    assert not r.legal and "needs 7 obsidian" in r.reason


def test_ruined_unknown_count_is_illegal_not_free():
    locs = {"rp": {"x": 0, "y": 64, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"rp": {"type": "ruined_portal", "notes": "a ruined portal"}}}
    r = run(mk({"obsidian": 21}, locs=locs, world=world), act("build_portal", method="complete_ruined"))
    assert not r.legal and "missing-obsidian count unknown" in r.reason


# ---- barter table by version
def test_barter_uses_version_table():
    inv = {"gold_ingot": 32, "golden_helmet": 1}
    r161 = run(mk(inv, dim="the_nether", version="1.16.1"), act("barter", gold_ingots=32))
    r165 = run(mk(inv, dim="the_nether", version="1.16.5"), act("barter", gold_ingots=32))
    assert r161.final_state["inventory"]["ender_pearl"] == 9  # floor(32 * 20/423 * 6) = 9
    assert r165.final_state["inventory"]["ender_pearl"] == 2
    assert R.barter_table_for("1.16.1") == "1.16.1" and R.barter_table_for("1.16.5") == "1.16.2+"


# ---- throw_eye: expected breakage, overworld only
def test_throw_eye_expected_breakage():
    locs = {"sh": {"x": 0, "y": 30, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"sh": {"type": "end_portal", "frames_filled": 1}}}
    r = run(mk({"ender_eye": 11}, locs=locs, world=world), act("throw_eye", at={"x": 0, "y": 64, "z": 0}),
            act("place_eyes", count=11))
    assert r.legal, r.reason
    r = run(mk({"ender_eye": 10}), *[act("throw_eye", at={"x": i, "y": 64, "z": 0}) for i in range(5)])
    assert r.final_state["inventory"]["ender_eye"] == 9  # floor(0.2 * 5) = 1 broken


def test_throw_eye_not_in_nether():
    r = run(mk({"ender_eye": 2}, dim="the_nether"), act("throw_eye", at={"x": 0, "y": 64, "z": 0}))
    assert not r.legal and "the_nether" in r.reason


# ---- triangulate ignores intersections behind a thrower
def test_triangulate_behind_is_none():
    assert A.triangulate(0, 0, 0, 100, -100, 135) is None
    assert A.triangulate(0, 0, -45, 100, 0, 45) is not None


# ---- leaves / unknown blocks / items cannot be mined into existence
def test_leaves_do_not_drop_leaves():
    rule = R.mining_rule("oak_leaves")
    assert "oak_leaves" not in rule["drops"] and rule["verified"] is False


def test_mining_items_is_illegal():
    r = run(mk(), act("mine", block="flint_and_steel", count=1))
    assert not r.legal and "no 1.16.5 mining rule" in r.reason


# ---- crafting: bed colour and plank wood must match
def test_bed_colour_and_plank_wood():
    inv = {"white_wool": 1, "red_wool": 1, "blue_wool": 1, "oak_planks": 3, "crafting_table": 1}
    assert not run(mk(inv), act("craft", item="red_bed", count=1)).legal
    inv = {"red_wool": 3, "oak_planks": 3, "crafting_table": 1}
    assert run(mk(inv), act("craft", item="red_bed", count=1)).legal
    assert not run(mk({"crimson_stem": 1}), act("craft", item="oak_planks", count=4)).legal
    assert run(mk({"crimson_stem": 1}), act("craft", item="crimson_planks", count=4)).legal


# ---- goal check
@pytest.fixture
def fx3():
    return _load(FIXTURES, "tasks", "FX3_nether_entry_plan"), _load(FIXTURES, "reference", "FX3_nether_entry_plan")


def test_plan_must_reach_goal(fx3):
    task, ref = fx3
    for raw in ('{"actions": []}', '{"actions": [{"action": "reset"}]}',
                '{"actions": [{"action": "loot_chest", "at": "portal_chest_1"}]}'):
        r = check.check_task(task, ref, raw)
        assert r["verdict"] == "WRONG" and "goal" in r["reason"], (raw, r["reason"])
    assert check.check_task(task, ref, json.dumps(ref["answer"]))["verdict"] == "OK"


def test_cheat_plan_mining_flint_and_steel(fx3):
    task, ref = fx3
    raw = json.dumps({"actions": [act("mine", block="flint_and_steel", count=1), act("travel", to="portal_site"),
                                  act("build_portal", method="complete_ruined"),
                                  act("light_portal", **{"with": "flint_and_steel"}), act("enter_portal")]})
    assert check.check_task(task, ref, raw)["verdict"] == "ILLEGAL"


# ---- malformed plans never crash
@pytest.mark.parametrize("bad", [
    {"action": ["mine"]}, {"action": "craft", "item": ["x"]}, {"action": "mine", "block": {"a": 1}},
    {"action": "kill", "mob": ["blaze"]}, {"action": "mine", "block": "dirt", "count": 1e400},
    {"action": "travel", "to": "village", "dimension": ["x"]},
])
def test_malformed_params_are_illegal(fx3, bad):
    task, ref = fx3
    r = check.check_task(task, ref, json.dumps({"actions": [bad]}).replace("Infinity", "1e400"))
    assert r["verdict"] == "ILLEGAL" and r["reason"].startswith("step 0")


def test_batch_survives_crashing_reply(tmp_path, monkeypatch):
    root = tmp_path / "repo"
    shutil.copytree(FIXTURES, root)
    (root / "attempts" / "zz_bad.json").write_text(json.dumps(
        {"task_id": "FX3_nether_entry_plan", "model": "m", "raw_response": '{"actions": []}'}))
    real = check.check_task

    def boom(task, ref, raw, costs=None):
        if raw == '{"actions": []}':
            raise RuntimeError("boom")
        return real(task, ref, raw, costs)
    monkeypatch.setattr(check, "check_task", boom)
    results, _ = check.run_attempts(root)
    assert (root / "runs" / "results.csv").is_file()
    assert any(r["verdict"] == "WRONG" and "boom" in r["reason"] for r in results)


# ---- end portal activity is not inferred from unrelated facts
def test_end_portal_not_active_from_unrelated_facts():
    locs = {"sh": {"x": 0, "y": 30, "z": 0, "dimension": "overworld"}}
    world = {"structures": {"sh": {"type": "end_portal", "notes": "2 eyes already placed"}},
             "facts": ["the ruined portal near spawn can be made active with 2 obsidian",
                       "the end portal room is under the village"]}
    r = run(mk(locs=locs, world=world), act("enter_portal"))
    assert not r.legal
    world["facts"] = ["The End portal is already active."]
    assert run(mk(locs=locs, world=world), act("enter_portal")).legal


# ---- answer selection: last matching object, schema echo skipped
def test_answer_selection_skips_schema_echo():
    task = {"answer_type": "coordinates", "answer_schema": '{"x": 0, "z": 0, "dimension": "overworld"}'}
    ref = {"answer": {"x": -141, "z": 107, "dimension": "the_nether"}, "tolerance": {"blocks": 16}}
    raw = ('Format: {"x": 0, "z": 0, "dimension": "overworld"}. '
           'My answer: {"x": -141, "y": 40, "z": 107, "dimension": "the_nether"}')
    r = check.check_task(task, ref, raw)
    assert r["verdict"] == "OK" and r["details"]["answer_selection"]["span"]
    raw2 = 'Example:\n```json\n{"x": 1, "z": 1}\n```\nFinal:\n```json\n{"x": -140, "z": 100, "dimension": "the_nether"}\n```'
    assert check.check_task(task, ref, raw2)["verdict"] == "OK"


# ---- logeval: claims checked against the pre-action state; negations skipped
def _rewrite(tmp_path, src, fn):
    lines = (FIXTURES / "events" / src).read_text().splitlines()
    out = [json.dumps(fn(i + 1, json.loads(l))) for i, l in enumerate(lines)]
    p = tmp_path / src
    p.write_text("\n".join(out) + "\n")
    return p


def test_true_claim_before_consuming_action_is_not_flagged(tmp_path):
    def fn(n, e):
        if e.get("type") == "decision" and "Fill the End portal" in json.dumps(e):
            e["response"] = {"note": "I have 12 eyes so I place them all now; I don't have 3 rods left either"}
        return e
    rep = logeval.evaluate(_rewrite(tmp_path, "clean_run.jsonl", fn))
    assert rep["claims"] == [], rep["claims"]


def test_light_portal_keeping_flint_is_not_no_progress(tmp_path):
    rep = logeval.evaluate(FIXTURES / "events" / "clean_run.jsonl")
    assert rep["waste"]["no_progress"] == []
    ev = (FIXTURES / "events" / "clean_run.jsonl").read_text()
    assert '"action": "Light the portal", "result": "done", "position": {"x": 20.5, "y": 64, "z": 20.5}, ' \
           '"inventory": {"flint_and_steel": 1' in ev


def test_string_inventory_counts_do_not_crash(tmp_path):
    def fn(n, e):
        if n == 4 and isinstance(e.get("inventory"), dict):
            e["inventory"] = {k: str(v) for k, v in e["inventory"].items()}
        return e
    logeval.evaluate(_rewrite(tmp_path, "clean_run.jsonl", fn))
