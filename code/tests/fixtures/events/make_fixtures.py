"""Regenerates the synthetic rmalde-format fixture logs. Run: python make_fixtures.py"""
import json, datetime, sys
import os
OUT = os.path.dirname(os.path.abspath(__file__)) + "/"
T0 = datetime.datetime(2026, 11, 6, 12, 0, 0, tzinfo=datetime.timezone.utc)


class Log:
    def __init__(s, difficulty="peaceful"):
        s.lines, s.t, s.step, s.pos, s.dim, s.inv = [], 0.0, 0, {"x": 0.5, "y": 64.0, "z": 0.5}, "overworld", {}
        s.stage = "prepare"
        s.add("start", seed="8398967436125155523", version="1.16.5", difficulty=difficulty,
              state=s.state())

    def state(s):
        return {"stage": s.stage, "position": dict(s.pos), "dimension": s.dim, "inventory": dict(s.inv),
                "health": 20, "steps": s.step}

    def add(s, type, dt=0.0, **data):
        s.t += dt
        tm = (T0 + datetime.timedelta(seconds=s.t)).isoformat().replace("+00:00", "Z")
        s.lines.append(json.dumps({"time": tm, "type": type, **data}))
        return len(s.lines)

    def act(s, key, desc, dt, result="done", move=None, gain=None, lose=None, dim=None, dec_dt=0.5):
        st = s.state(); st["active"] = desc
        s.add("decision", dec_dt, step=s.step, request={"model": "typesafe/jev-1.13", "state": json.dumps(st)},
              response={"answers": {"action": {"choice": "a0"}}}, latencyMs=400, selected=key)
        if move:
            s.pos = {"x": move[0], "y": move[1], "z": move[2]}
        for k, v in (gain or {}).items():
            s.inv[k] = s.inv.get(k, 0) + v
        for k, v in (lose or {}).items():
            s.inv[k] -= v
            if s.inv[k] == 0:
                del s.inv[k]
        if dim:
            s.dim = dim
        s.step += 1
        return s.add("result", dt, step=s.step, action=desc, result=result, position=dict(s.pos),
                     inventory=dict(s.inv))

    def sample(s, x, y, z, dt=0.1):
        s.pos = {"x": x, "y": y, "z": z}
        return s.add("position_sample", dt, position=dict(s.pos), dimension=s.dim)

    def plan(s, objective, dt=0.2):
        return s.add("plan", dt, result={"objective": objective, "steps": []}, latencyMs=2000, model="sol")

    def write(s, name):
        open(OUT + name, "w").write("\n".join(s.lines) + "\n")


marks = {}

# ---------------- clean run
c = Log()
c.plan("Loot the surveyed chests; need 12 eyes total before the stronghold.")
c.act("chest_loot_1", "Loot chest at (10, 64, 12)", 6, move=(10.5, 64, 12.5),
      gain={"obsidian": 10, "flint_and_steel": 1, "oak_log": 3, "gold_ingot": 6})
c.act("craft_planks", "Craft oak planks", 1, gain={"oak_planks": 12}, lose={"oak_log": 3})
c.act("craft_table", "Craft crafting table", 1, gain={"crafting_table": 1}, lose={"oak_planks": 4})
c.act("place_crafting_table", "Place crafting table", 1, lose={"crafting_table": 1})
c.act("craft_pickaxe", "Craft wooden pickaxe", 1, gain={"wooden_pickaxe": 1}, lose={"oak_planks": 3})
c.act("build_portal", "Build Nether portal at (20, 64, 20)", 15, move=(20.5, 64, 20.5), lose={"obsidian": 10})
c.act("light_portal", "Light the portal", 2)
c.add("nether_entered", 4, position={"x": 2.5, "y": 70, "z": 2.5})
c.dim = "the_nether"; c.stage = "nether"; c.pos = {"x": 2.5, "y": 70, "z": 2.5}
c.act("barter_gold", "Barter gold with piglins", 30, gain={"ender_pearl": 12}, lose={"gold_ingot": 6})
c.act("kill_blaze", "Kill blazes at fortress (40, 70, 40)", 40, move=(40.5, 70, 40.5), gain={"blaze_rod": 6})
c.act("craft_powder", "Craft blaze powder", 1, gain={"blaze_powder": 12}, lose={"blaze_rod": 6})
c.act("craft_eyes", "Craft eyes of ender", 1, gain={"ender_eye": 12}, lose={"blaze_powder": 12, "ender_pearl": 12})
c.act("return_portal", "Walk back to portal at (2, 70, 2)", 20, move=(2.5, 70, 2.5))
c.add("nether_exited", 4, position={"x": 20.5, "y": 64, "z": 20.5})
c.dim = "overworld"; c.stage = "stronghold"; c.pos = {"x": 20.5, "y": 64, "z": 20.5}
c.act("go_stronghold", "Travel to stronghold portal room at (100, 30, 200)", 60, move=(100.5, 30, 199.5))
c.act("fill_portal", "Fill the End portal frames", 3, lose={"ender_eye": 12})
c.act("enter_end_careful", "Step into the End portal", 2, move=(100, 49, 0), dim="the_end")
c.stage = "combat"
c.sample(100, 49, 0, dt=0.5)
c.act("attack_dragon", "Attack the dragon", 90, move=(0.5, 64, 0.5))
c.add("dragon_killed", 1, source="server entity health zero and dying phase")
c.add("game_won", 5, packet={"reason": 4}, dragonKilled=True)
c.write("clean_run.jsonl")

# ---------------- wasteful run
w = Log()
w.plan("Loot chests then build the portal.")
w.act("chest_loot_1", "Loot chest at (10, 64, 12)", 6, move=(10.5, 64, 12.5),
      gain={"obsidian": 10, "flint_and_steel": 1, "oak_log": 3, "gold_ingot": 6})
marks["w_detour"] = w.act("detour_food", "Kill cows for food", 25, move=(30.5, 64, -10.5),
                          gain={"cooked_beef": 5, "leather": 3})
marks["w_detour_armor"] = w.act("craft_armor", "Craft iron chestplate", 3, gain={"iron_chestplate": 1})
w.act("craft_planks", "Craft oak planks", 1, gain={"oak_planks": 12}, lose={"oak_log": 3})
w.act("craft_table", "Craft crafting table", 1, gain={"crafting_table": 1}, lose={"oak_planks": 4})
marks["w_place"] = w.act("place_crafting_table", "Place crafting table", 1, lose={"crafting_table": 1})
w.act("craft_pickaxe", "Craft wooden pickaxe", 1, gain={"wooden_pickaxe": 1}, lose={"oak_planks": 3})
marks["w_recover"] = w.act("mine_crafting_table", "Mine the crafting table back", 4, gain={"crafting_table": 1})
marks["w_fail"] = w.act("build_portal", "Build Nether portal at (20, 64, 20)", 25,
                        result="FAILED Timed out after 25000ms")
marks["w_wait"] = w.act("wait_for_planner", "Wait for planner", 5)
# loop: 3 identical unproductive actions
marks["w_loop_start_res"] = w.act("collect_drop", "Collect dropped item", 3, result="FAILED No path")
w.act("collect_drop", "Collect dropped item", 3)
marks["w_loop_end"] = w.act("collect_drop", "Collect dropped item", 3, result="FAILED No path")
# overshoot toward (20, 64, 20)
marks["w_go1"] = w.act("go_portal_site", "Walk to portal site at (20, 64, 20)", 4, move=(18.5, 64, 18.5))
marks["w_reach"] = w.sample(19.5, 64, 19.8)
marks["w_over"] = w.sample(27.5, 64, 26.5)
w.act("go_portal_site", "Walk to portal site at (20, 64, 20)", 4, move=(21.0, 64, 20.5))
w.act("build_portal", "Build Nether portal at (20, 64, 20)", 15, lose={"obsidian": 10})
w.act("light_portal", "Light the portal", 2, lose={"flint_and_steel": 1})
w.add("nether_entered", 4, position={"x": 2.5, "y": 70, "z": 2.5})
w.dim = "the_nether"; w.stage = "nether"; w.pos = {"x": 2.5, "y": 70, "z": 2.5}
w.act("barter_gold", "Barter gold with piglins", 30, gain={"ender_pearl": 8}, lose={"gold_ingot": 6})
marks["w_death"] = w.add("death", 10, state={**w.state(), "position": {"x": 41.2, "y": 70, "z": 39.9},
                                             "active": "Kill blazes at fortress", "health": 0})
w.write("wasteful_run.jsonl")

# ---------------- false claim run
f = Log()
f.plan("Loot chests and barter.")
f.act("chest_loot_1", "Loot chest at (10, 64, 12)", 6, move=(10.5, 64, 12.5),
      gain={"obsidian": 10, "flint_and_steel": 1, "gold_ingot": 6, "ender_eye": 9})
marks["f_claim"] = f.plan("We have 12 eyes of ender and entered the nether; go fill the portal.")
marks["f_evidence"] = f.act("go_stronghold", "Travel to stronghold portal room at (100, 30, 200)", 60,
                            move=(100.5, 30, 199.5))
f.act("fill_portal", "Fill the End portal frames", 3, lose={"ender_eye": 9})
f.write("false_claim_run.jsonl")

print(marks)  # line numbers asserted in tests/test_logeval.py
