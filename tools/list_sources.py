"""Prints the source -> tasks table used in SOURCES.md, from reference/*.json (sources + technique sources).

Run:  python tools/list_sources.py
"""
import glob
import json
import os
import re
from collections import defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def base(src):
    s = src.strip()
    s = re.split(r" \(|;|, (?=rmalde|https)", s)[0].strip()
    s = re.sub(r":\d[\d,\-]*$", "", s)          # drop line numbers
    s = s.split(" says ")[0]
    return s


def main():
    uses = defaultdict(set)
    for f in sorted(glob.glob(os.path.join(ROOT, "reference", "*.json")) + glob.glob(os.path.join(ROOT, "extras", "generic_tasks", "reference", "*.json"))):
        r = json.load(open(f, encoding="utf-8"))
        tid = r["id"].split("_")[0]
        srcs = list(r.get("sources", []))
        srcs += [t["source"] for t in r.get("techniques", [])]
        for s in srcs:
            for part in re.split(r"; ", s):
                b = base(part)
                if b and b.startswith(("http", "rmalde/", "tools/")):
                    uses[b].add(tid)
    for b in sorted(uses):
        print("| {} | {} |".format(b, ", ".join(sorted(uses[b]))))


if __name__ == "__main__":
    main()
