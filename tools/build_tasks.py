"""Builds tasks/<id>.json and reference/<id>.json from one place so prompts, states and answers stay consistent.

Run:  python tools/build_tasks.py
Numbers come from tools/compute_answers.py. Sources and verification status are in each reference file,
SOURCES.md and UNVERIFIED.md. Owner: B. Never send these files to an AI model.
"""
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import compute_answers as ca  # noqa: E402
from taskdefs_common import *  # noqa: E402,F401,F403
import taskdefs_a  # noqa: E402
import taskdefs_b  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def make_prompt(t):
    seed = t["seed"] if t["seed"] else "random (unknown to you)"
    head = PREAMBLE + "Version: Java {}. Difficulty: {}. Seed: {}.\n\n".format(t["version"], t["difficulty"].capitalize(), seed)
    body = t["situation"].strip() + "\n\nCurrent state (JSON):\n" + json.dumps(t["state"], indent=1) + "\n\n" + t["question"].strip()
    if t["answer_type"] == "plan":
        body += "\n\n" + ACTIONS_DOC
    return head + body + REPLY.format(schema=t["answer_schema"])


def build():
    tasks = taskdefs_a.TASKS + taskdefs_b.TASKS
    ids = set()
    for t in tasks:
        assert t["id"] not in ids, t["id"]
        ids.add(t["id"])
        ref = t.pop("reference")
        assert ref["alternates"] and ref["broken"], t["id"] + " needs alternates and broken answers"
        task = {
            "id": t["id"],
            "split": t["split"],
            "version": t["version"],
            "seed": t["seed"],
            "difficulty": t["difficulty"],
            "prompt": make_prompt(t),
            "state": t["state"],
            "answer_type": t["answer_type"],
            "answer_schema": t["answer_schema"],
        }
        if "options" in t:
            task["options"] = t["options"]
        ref = {"id": t["id"], **ref}
        with open(os.path.join(ROOT, "tasks", t["id"] + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(task, f, indent=2, ensure_ascii=False)
            f.write("\n")
        with open(os.path.join(ROOT, "reference", t["id"] + ".json"), "w", encoding="utf-8", newline="\n") as f:
            json.dump(ref, f, indent=2, ensure_ascii=False)
            f.write("\n")
    print("wrote", len(tasks), "tasks")


if __name__ == "__main__":
    build()
