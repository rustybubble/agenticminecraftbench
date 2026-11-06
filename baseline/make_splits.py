"""Turns the filled baseline/timing_sheet_1m48.md into baseline/pro_1m48_segments.json.

Run:  python baseline/make_splits.py
Uses the on-screen IGT column when every core milestone has it, otherwise the video-timestamp column
(times relative to M_start). Refuses to write if a core milestone is missing. No guessing.
"""
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
CORE = ["M_start", "M_portal_in", "M_portal_out", "M_end_in", "M_finish"]
SEGMENTS = [("spawn_to_nether", "M_start", "M_portal_in"), ("nether", "M_portal_in", "M_portal_out"),
            ("exit_to_end_portal", "M_portal_out", "M_end_in"), ("end", "M_end_in", "M_finish")]


def parse_time(s):
    s = s.strip()
    if not s:
        return None
    parts = s.split(":")
    try:
        sec = 0.0
        for p in parts:
            sec = sec * 60 + float(p)
        return sec
    except ValueError:
        raise SystemExit("cannot parse time %r" % s)


def read_sheet(path):
    rows = {}
    for line in open(path, encoding="utf-8"):
        m = re.match(r"\|\s*(M_[a-z_]+)\s*\|([^|]*)\|([^|]*)\|([^|]*)\|([^|]*)\|", line)
        if m:
            rows[m.group(1)] = {"video": parse_time(m.group(3)), "igt": parse_time(m.group(4)), "notes": m.group(5).strip()}
    return rows


def main():
    rows = read_sheet(os.path.join(HERE, "timing_sheet_1m48.md"))
    missing = [k for k in CORE if k not in rows or (rows[k]["video"] is None and rows[k]["igt"] is None)]
    if missing:
        sys.exit("not filled yet: " + ", ".join(missing))
    use_igt = all(rows[k]["igt"] is not None for k in CORE[1:])
    if use_igt:
        t = {k: (rows[k]["igt"] if rows[k]["igt"] is not None else 0.0) for k in CORE}
        timer = "on-screen IGT read from the video"
    else:
        if any(rows[k]["video"] is None for k in CORE):
            sys.exit("need either IGT for all milestones or video timestamps for all milestones")
        t0 = rows["M_start"]["video"]
        t = {k: rows[k]["video"] - t0 for k in CORE}
        timer = "video timestamps relative to M_start (edited video: includes loading screens unless cut; NOT IGT)"
    out = {
        "run": "https://www.speedrun.com/mc/runs/zqe4g39z",
        "video": "https://www.youtube.com/watch?v=2NEvhsZG5iY",
        "runner": "Rayoh",
        "version": "1.16.5", "difficulty": "easy", "category": "Any% Glitchless, Set Seed",
        "official": {"igt_s": 108.421, "rta_s": 119.331},
        "timer": timer,
        "milestones_s": {k: round(t[k], 3) for k in CORE},
        "segments": [{"segment": n, "from": a, "to": b, "pro_s": round(t[b] - t[a], 3)} for n, a, b in SEGMENTS],
        "verified": True,
        "source": "baseline/timing_sheet_1m48.md, filled by a human from the video",
        "notes": {k: rows[k]["notes"] for k in rows if rows[k]["notes"]},
    }
    total = out["milestones_s"]["M_finish"] - out["milestones_s"]["M_start"]
    out["check"] = {"segment_sum_s": round(total, 3), "official_igt_s": 108.421,
                    "diff_vs_official_igt_s": round(total - 108.421, 3)}
    with open(os.path.join(HERE, "pro_1m48_segments.json"), "w", encoding="utf-8", newline="\n") as f:
        json.dump(out, f, indent=2)
        f.write("\n")
    print(json.dumps(out["segments"], indent=1), out["check"])


if __name__ == "__main__":
    main()
