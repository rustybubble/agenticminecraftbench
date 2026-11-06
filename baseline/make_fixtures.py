"""Writes fixtures/*.json for Person A's checker, with expected outputs from baseline/reference_check.py.

Run:  python baseline/make_fixtures.py
"""
import copy
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from reference_check import check  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
B249 = "baseline/pro_2m49_segments.json"
base249 = json.load(open(os.path.join(ROOT, B249), encoding="utf-8"))
END_PORTAL = {"x": -1130, "y": 34, "z": 856}
AGENT_ARRIVAL = {"x": -1129.5, "y": 24, "z": 837.5}


def pro_timeline(base):
    return {k: {"low": v, "high": v} for k, v in base["milestones_s"].items()}


def shift(ms, after, dt):
    order = ["M_start", "M_portal_in", "M_portal_out", "M_end_in", "M_finish"]
    out = copy.deepcopy(ms)
    for k in order[order.index(after):]:
        out[k]["low"] = round(out[k]["low"] + dt, 3)
        out[k]["high"] = round(out[k]["high"] + dt, 3)
    return out


FIXTURES = {}
FIXTURES["pro_as_agent"] = {
    "description": "The 2:49.149 pro run fed in as if it were an agent. Every segment must be OK, no waste.",
    "baseline": B249, "milestones": pro_timeline(base249),
    "facts": {"overworld_arrival_xyz": END_PORTAL, "end_portal_xyz": END_PORTAL},
}
FIXTURES["inflated_exit"] = {
    "description": "Pro run with +50 s added to exit portal -> End portal, and the arrival moved to where the agent's exit landed. Only exit_to_end_portal may FLAG, tagged missed_shortcut.",
    "baseline": B249, "milestones": shift(pro_timeline(base249), "M_end_in", 50.0),
    "facts": {"overworld_arrival_xyz": AGENT_ARRIVAL, "end_portal_xyz": END_PORTAL},
}
same = pro_timeline(base249)
same = shift(same, "M_portal_out", 50.0)
same["M_finish"] = {"low": base249["milestones_s"]["M_finish"], "high": base249["milestones_s"]["M_finish"]}
FIXTURES["same_total_diff_split"] = {
    "description": "Same total as the pro (169.149 s) but 50 s moved from the End into the Nether. Only nether may FLAG; the total ratio is 1.0.",
    "baseline": B249, "milestones": same,
    "facts": {"overworld_arrival_xyz": END_PORTAL, "end_portal_xyz": END_PORTAL},
}
FIXTURES["extra_beds"] = {
    "description": "Pro run plus 2 extra beds collected before the Nether (+8 s at the 4 s/bed estimate). spawn_to_nether must carry an extra_items waste entry for 2 beds.",
    "baseline": B249, "milestones": shift(pro_timeline(base249), "M_portal_in", 8.0),
    "facts": {"beds_collected": 8, "beds_used": 6, "overworld_arrival_xyz": END_PORTAL, "end_portal_xyz": END_PORTAL},
}
mont = json.load(open(os.path.join(ROOT, "agent_runs", "published_montage", "timeline.json"), encoding="utf-8"))
mm = {m["id"]: m for m in mont["milestones"]}
def br(i):
    return {"low": mm[i]["after_s"], "high": mm[i]["by_s"]}
FIXTURES["published_montage"] = {
    "description": "The real agent run (montage brackets) against the 2:49 baseline. Expected output is the preliminary finding; re-run against the 1:48 baseline when baseline/pro_1m48_segments.json exists.",
    "baseline": B249,
    "milestones": {"M_start": {"low": 0.0, "high": 0.0}, "M_portal_in": br("M4_enter_nether"), "M_portal_out": br("M5_exit_nether"),
                   "M_end_in": br("M7_enter_end"), "M_finish": br("M9_complete_exit")},
    "facts": {"overworld_arrival_xyz": AGENT_ARRIVAL, "end_portal_xyz": END_PORTAL, "beds_collected": 8, "beds_used": 6},
    "facts_sources": {
        "milestones": "agent_runs/published_montage/timeline.json (banner reads)",
        "overworld_arrival_xyz": "rmalde/minecraft-agent:optimization/nether/exit-link.json (position; nether_portal blocks at x -1130..-1129, y 24-26, z 837); montage banner (-1129.5, 24, 837.5) at 05:02.800",
        "end_portal_xyz": "rmalde/minecraft-agent:optimization/nether/config.json:52-56",
        "beds_collected": "montage evidence 'collecting 4th of 8 beds' at 01:08.000; rmalde/minecraft-agent:optimization/nether/config.json:59 (kit beds 8)",
        "beds_used": "rmalde/minecraft-agent:README.md:9 (six bed explosions)",
    },
}


def main():
    os.makedirs(os.path.join(ROOT, "fixtures"), exist_ok=True)
    for name, fx in FIXTURES.items():
        base = json.load(open(os.path.join(ROOT, fx["baseline"]), encoding="utf-8"))
        fx = dict(fx, kind="agent_timeline", run_id=name)
        fx["expected"] = check(fx, base)
        with open(os.path.join(ROOT, "fixtures", name + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(fx, f, indent=2)
            f.write("\n")
        segs = [(r["segment"], r.get("verdict"), [w["tag"] for w in r["waste"]]) for r in fx["expected"]["segments"]]
        print(name, fx["expected"]["total"]["ratio_low"], segs)


if __name__ == "__main__":
    main()
