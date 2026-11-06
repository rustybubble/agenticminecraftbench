"""B's consistency check on reference files (not the checker; A owns code/).

For number / coordinates / choice tasks: the reference answer and every alternate must be inside tolerance,
and every broken answer must be outside it. Also checks schema basics for every task.
Run:  python tools/validate_refs.py
"""
import glob
import json
import math
import os
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TAGS = {"no_reset_judgment", "brute_force_over_trick", "no_nether_shortcut", "ignores_information",
        "resource_miscount", "mob_rule_unaware", "detour_overprep", "unnecessary_risk"}
SPLITS = {"reset", "nether_entry", "bastion", "fortress", "blind_travel", "triangulation", "portal_room", "dragon", "full_route"}


def ok(task, ref, ans):
    t, tol = task["answer_type"], ref["tolerance"]
    gold = ref["answer"]
    if t == "choice":
        return ans.get("choice") in tol.get("choices", [gold["choice"]])
    if t == "number":
        for k, v in gold.items():
            if k not in ans:
                return False
            lim = tol.get("fields", {}).get(k, {}).get("abs", tol.get("abs", 0))
            if abs(ans[k] - v) > lim + 1e-9:
                return False
        return True
    if t == "coordinates":
        if ans.get("dimension") != gold["dimension"]:
            return False
        d = math.hypot(ans["x"] - gold["x"], ans["z"] - gold["z"])
        if d > tol["blocks"]:
            return False
        if "y_blocks" in tol and abs(ans.get("y", 1e9) - gold["y"]) > tol["y_blocks"]:
            return False
        return True
    return None


def main():
    bad = 0
    for f in sorted(glob.glob(os.path.join(ROOT, "tasks", "*.json"))):
        task = json.load(open(f, encoding="utf-8"))
        ref = json.load(open(f.replace("tasks", "reference"), encoding="utf-8"))
        tid = task["id"]
        errs = []
        if task["split"] not in SPLITS:
            errs.append("bad split")
        if ref["miss_category"] not in TAGS:
            errs.append("bad miss_category")
        if not ref["alternates"] or not ref["broken"]:
            errs.append("needs alternates and broken")
        if "options" in task and task["answer_type"] == "choice":
            for a in [ref["answer"]] + [x["answer"] for x in ref["alternates"] + ref["broken"]]:
                if a["choice"] not in task["options"]:
                    errs.append("choice not in options: " + a["choice"])
        for word in ("trap", "alternate", "broken", "expected_verdict"):
            if word in task["prompt"].lower():
                errs.append("prompt contains '%s'" % word)
        if task["answer_type"] != "plan":
            if not ok(task, ref, ref["answer"]):
                errs.append("reference answer outside its own tolerance")
            for a in ref["alternates"]:
                if not ok(task, ref, a["answer"]):
                    errs.append("alternate rejected: %s" % json.dumps(a["answer"]))
            for b in ref["broken"]:
                if ok(task, ref, b["answer"]):
                    errs.append("broken accepted: %s" % json.dumps(b["answer"]))
                if b["expected_verdict"] != "WRONG":
                    errs.append("non-plan broken must be WRONG")
        else:
            for b in ref["broken"]:
                if b["expected_verdict"] not in ("ILLEGAL", "SLOW"):
                    errs.append("plan broken must be ILLEGAL or SLOW")
        print(("OK   " if not errs else "FAIL ") + tid + ("" if not errs else "  " + "; ".join(errs)))
        bad += bool(errs)
    sys.exit(1 if bad else 0)


if __name__ == "__main__":
    main()
