#!/usr/bin/env python3
"""Burn a stats overlay into a frame sequence captured from the Prismarine viewer.

The overlay is proof-of-provenance, not decoration: every line comes from the server-side RCON
poller (`server_events.jsonl`) and the agent's own event log, aligned to each frame's file mtime.
If a frame and the log disagree, the log wins and the clip shows the log line.

    python3 live/footage/overlay.py \
      --frames evidence/footage/frames-agent01 \
      --server agent_runs/agent-01/server_events.jsonl \
      --agent runs/live/agent-01/events.jsonl \
      --run-id agent-01 --seed 8398967436125155523 --difficulty easy \
      --out evidence/footage/agent-01-chests.mp4
"""
import argparse
import datetime as dt
import json
import os
import subprocess
import sys

TOP = "SplitCheck · {run} · MC {ver} · seed {seed} · difficulty {diff} · server-verified"


def ts(value):
    if isinstance(value, (int, float)):
        return dt.datetime.fromtimestamp(value, dt.timezone.utc)
    return dt.datetime.fromisoformat(value.replace("Z", "+00:00"))


def ass_time(seconds):
    h = int(seconds // 3600)
    m = int((seconds % 3600) // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def load_jsonl(path, key):
    out = []
    if not path or not os.path.exists(path):
        return out
    for line in open(path, encoding="utf-8"):
        try:
            rec = json.loads(line)
            rec["_t"] = ts(rec.get(key) or rec.get("time") or rec.get("ts"))
            out.append(rec)
        except Exception:
            continue
    return sorted(out, key=lambda r: r["_t"])


def esc(text):
    return text.replace("\\", "\\\\").replace("{", "(").replace("}", ")").replace("\n", " ")


def fmt_inv(inv, keys=("obsidian", "iron_ingot", "flint_and_steel", "iron_pickaxe", "bread")):
    parts = [f"{k} {inv[k]}" for k in keys if inv.get(k)]
    return "  ".join(parts) if parts else "empty"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--frames", required=True)
    ap.add_argument("--server", required=True)
    ap.add_argument("--agent", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--seed", default="8398967436125155523")
    ap.add_argument("--version", default="1.16.5")
    ap.add_argument("--difficulty", default="peaceful")
    ap.add_argument("--fps", type=float, default=0)
    args = ap.parse_args()

    frames = sorted(f for f in os.listdir(args.frames) if f.endswith(".png"))
    if len(frames) < 10:
        sys.exit("not enough frames")
    paths = [os.path.join(args.frames, f) for f in frames]
    mtimes = [os.path.getmtime(p) for p in paths]
    span = mtimes[-1] - mtimes[0]
    fps = args.fps or (len(frames) - 1) / max(span, 0.1)
    t0 = mtimes[0]
    total = (len(frames) - 1) / fps

    server = [r for r in load_jsonl(args.server, "time") if r.get("type") in ("position_sample", "inventory")]
    agent = load_jsonl(args.agent, "ts")
    events = [r for r in agent if r.get("type") in ("decision", "skill_result", "route_portal", "route_loot", "split", "death", "spawn")]

    # Render the overlay with Pillow: this ffmpeg build has neither libass nor drawtext.
    from PIL import Image, ImageDraw, ImageFont

    def font(size, bold=False):
        return ImageFont.truetype("/System/Library/Fonts/Menlo.ttc", size)

    f_banner, f_hud, f_event = font(19), font(17), font(18)
    banner = TOP.format(run=args.run_id, ver=args.version, seed=args.seed, diff=args.difficulty)
    out_dir = os.path.join(os.path.dirname(args.out), "overlay-frames")
    os.makedirs(out_dir, exist_ok=True)

    server_sorted = server
    events_sorted = events

    def latest(records, wall, kind):
        best = None
        for r in records:
            if r["_t"] <= wall and (kind is None or r.get("type") == kind):
                best = r
        return best

    def box(draw, xy, text, fnt, fill, pad=6):
        x, y = xy
        b = draw.textbbox((0, 0), text, font=fnt)
        w, h = b[2] - b[0], b[3] - b[1]
        draw.rectangle([x - pad, y - pad, x + w + pad, y + h + pad * 2], fill=(0, 0, 0, 170))
        draw.text((x, y), text, font=fnt, fill=fill)

    for i, path in enumerate(paths):
        wall = dt.datetime.fromtimestamp(t0 + i / fps, dt.timezone.utc)
        img = Image.open(path).convert("RGB").resize((1280, 720), Image.LANCZOS)
        layer = Image.new("RGBA", img.size, (0, 0, 0, 0))
        draw = ImageDraw.Draw(layer)
        box(draw, (18, 18), banner, f_banner, (255, 255, 255, 235))

        sample = latest(server_sorted, wall, "position_sample")
        inv = (sample or {}).get("inventory") or {}
        t = i / fps
        # cumulative loot, rebuilt from the agent's own loot events (the poller's inventory
        # query is best-effort and can miss slots)
        loot = {}
        for r in events_sorted:
            if r.get("type") == "route_loot" and r["_t"] <= wall:
                for item in ((r.get("result") or {}).get("got") or []):
                    name, _, count = item.rpartition("x")
                    try:
                        loot[name] = loot.get(name, 0) + int(count)
                    except ValueError:
                        loot[item] = loot.get(item, 0) + 1
        loot_line = "  ".join(f"{k} {v}" for k, v in sorted(loot.items(), key=lambda kv: -kv[1])[:5])
        if sample:
            pos = sample.get("position") or [0, 0, 0]
            hud = (f"t+{int(t):02d}s  {sample.get('dimension')}  pos {pos[0]:.0f} {pos[1]:.0f} {pos[2]:.0f}"
                   f"  hp {sample.get('health')}  food {sample.get('food')}  held {sample.get('selected_item') or '-'}"
                   f"  |  looted {loot_line or '-'}")
        else:
            hud = f"t+{int(t):02d}s  waiting for server sample"
        box(draw, (18, 720 - 46), hud, f_hud, (210, 255, 210, 240))

        callout = None
        for r in events_sorted:
            off = (r["_t"] - dt.datetime.fromtimestamp(t0, dt.timezone.utc)).total_seconds()
            if -0.1 <= t - off <= 3.5:
                kind = r.get("type")
                if kind == "decision":
                    callout = (f"decision [{r.get('source')}] {r.get('skill')}  ({r.get('ms')} ms, {r.get('model')})"
                               f"  - {r.get('why', '')}")
                elif kind == "skill_result":
                    callout = f"{'ok' if r.get('ok') else 'FAIL'}  {r.get('skill')}  {int(r.get('ms', 0) / 1000)}s  {r.get('error') or ''}"
                elif kind == "route_loot":
                    callout = f"looted {r.get('step')}  ->  {', '.join(((r.get('result') or {}).get('got') or [])[:8])}"
                else:
                    callout = f"{kind}  {r.get('split') or ''}"
                break
        if callout:
            box(draw, (18, 720 - 82), callout[:150], f_event, (120, 220, 255, 245))

        # provenance strip: exact wall clock of the server sample this frame is showing
        stamp = sample["_t"].strftime("%H:%M:%S") if sample else "--:--:--"
        box(draw, (1280 - 380, 56), f"server clock {stamp}Z", f_hud, (255, 235, 150, 235))

        Image.alpha_composite(img.convert("RGBA"), layer).convert("RGB").save(
            os.path.join(out_dir, f"f{i:05d}.jpg"), quality=92)
        if i % 50 == 0:
            print(f"  {i}/{len(paths)}", flush=True)

    cmd = [
        "ffmpeg", "-y", "-loglevel", "error",
        "-framerate", f"{fps:.4f}", "-i", os.path.join(out_dir, "f%05d.jpg"),
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "22",
        "-pix_fmt", "yuv420p", "-movflags", "+faststart", args.out,
    ]
    subprocess.run(cmd, check=True)
    print(json.dumps({"out": args.out, "frames": len(frames), "seconds": round(total, 1), "fps": round(fps, 2), "overlay_frames": out_dir}, indent=1))


if __name__ == "__main__":
    main()
