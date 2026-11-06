"""B's reference implementation of baseline/rules.json, used only to write the expected outputs into fixtures/.
Person A's checker in code/ is the real one; the fixtures let A test it against these expectations.

Run:  python baseline/reference_check.py fixtures/<file>.json [baseline/pro_2m49_segments.json]
"""
import json
import math
import os
import statistics
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
RULES = json.load(open(os.path.join(ROOT, "baseline", "rules.json"), encoding="utf-8"))


def bracket(m):
    if isinstance(m, (int, float)):
        return float(m), float(m)
    return float(m["low"]), float(m["high"])


def check(timeline, baseline):
    v = RULES["verdict"]
    pro_m = baseline["milestones_s"]
    rows = []
    for seg in RULES["segments"]:
        fl, fh = bracket(timeline["milestones"][seg["from"]])
        tl, th = bracket(timeline["milestones"][seg["to"]])
        lo, hi = max(0.0, tl - fh), max(0.0, th - fl)
        pro = pro_m[seg["to"]] - pro_m[seg["from"]]
        rows.append({"segment": seg["segment"], "agent_s_low": round(lo, 3), "agent_s_high": round(hi, 3), "pro_s": round(pro, 3),
                     "ratio_low": round(lo / pro, 3), "ratio_high": round(hi / pro, 3), "waste": []})
    med = statistics.median([(r["ratio_low"] + r["ratio_high"]) / 2 for r in rows])
    for r in rows:
        if r["ratio_low"] > v["flag_k_times_median"] * max(med, 1.0) and r["agent_s_low"] - r["pro_s"] >= v["flag_min_excess_s"]:
            r["verdict"] = "FLAG"
        elif r["ratio_low"] > v["ok_max_ratio"]:
            r["verdict"] = "SLOW"
        else:
            r["verdict"] = "OK"
    facts = timeline.get("facts", {})
    by = {r["segment"]: r for r in rows}
    a, e = facts.get("overworld_arrival_xyz"), facts.get("end_portal_xyz")
    if a and e:
        d = math.dist([a["x"], a["y"], a["z"]], [e["x"], e["y"], e["z"]])
        if d > 8:
            r = by["exit_to_end_portal"]
            r["waste"].append({"tag": "missed_shortcut", "seconds": round(max(0.0, r["agent_s_low"] - r["pro_s"]), 3),
                               "evidence": "overworld arrival {:.1f} blocks from the End portal".format(d)})
    if "beds_collected" in facts and "beds_used" in facts:
        pro_left = baseline.get("items", {}).get("beds_leftover", 0)
        extra = (facts["beds_collected"] - facts["beds_used"]) - pro_left
        if extra > 0:
            per = [w for w in RULES["waste_rules"] if w["tag"] == "extra_items"][0]["seconds_per_extra_bed"]
            by["spawn_to_nether"]["waste"].append({"tag": "extra_items", "seconds": extra * per,
                                                   "evidence": "{} beds collected, {} used".format(facts["beds_collected"], facts["beds_used"])})
    if "model_latency_s" in facts:
        rows.append({"segment": "whole_run", "waste": [{"tag": "idle_wait", "seconds": facts["model_latency_s"], "evidence": "model latency total"}]})
    tl, th = bracket(timeline["milestones"]["M_finish"])
    total = pro_m["M_finish"] - pro_m["M_start"]
    return {"run_median_ratio": round(med, 3), "total": {"agent_s_low": tl, "agent_s_high": th, "pro_s": total,
                                                          "ratio_low": round(tl / total, 3), "ratio_high": round(th / total, 3)},
            "segments": rows}


def main():
    tl = json.load(open(sys.argv[1], encoding="utf-8"))
    bpath = sys.argv[2] if len(sys.argv) > 2 else os.path.join(ROOT, tl.get("baseline", "baseline/pro_2m49_segments.json"))
    print(json.dumps(check(tl, json.load(open(bpath, encoding="utf-8"))), indent=1))


if __name__ == "__main__":
    main()
