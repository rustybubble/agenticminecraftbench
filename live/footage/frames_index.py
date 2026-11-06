#!/usr/bin/env python3
"""Map raw captured frames to run time: [{"file": "f0001.png", "run_t": 0.0}, ...].

`run_t` is seconds since the agent's `spawn` event (from events.jsonl), so the perception layer
can align any frame with the event log without trusting frame numbering.

    python3 live/footage/frames_index.py --frames agent_runs/agent-02/frames \
        --events agent_runs/agent-02/events.jsonl --out agent_runs/agent-02/frames_index.json
"""
import argparse, datetime as dt, json, os

ap = argparse.ArgumentParser()
ap.add_argument("--frames", required=True)
ap.add_argument("--events", required=True)
ap.add_argument("--out", required=True)
a = ap.parse_args()

spawn = None
for line in open(a.events, encoding="utf-8"):
    try:
        rec = json.loads(line)
    except Exception:
        continue
    if rec.get("type") == "spawn":
        spawn = dt.datetime.fromisoformat(rec["ts"].replace("Z", "+00:00")).timestamp()
        break
if spawn is None:
    raise SystemExit("no spawn event in events log")

files = sorted(f for f in os.listdir(a.frames) if f.endswith((".png", ".jpg")))
index = [{"file": f, "run_t": round(os.path.getmtime(os.path.join(a.frames, f)) - spawn, 3)} for f in files]
json.dump({"spawn_epoch": spawn, "frames": index}, open(a.out, "w"), indent=1)
print(json.dumps({"frames": len(index), "first": index[0], "last": index[-1]}, indent=1))
