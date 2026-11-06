"""Build the offline judge demo page from evaluator outputs.

    python -m splitcheck.demo --root .. --out ../runs/demo

Reads (never writes) agent_runs/, evidence/, baseline/, runs/<run>-eval/ and runs/results_pack/.
Writes runs/demo/index.html (data embedded as a JSON <script> block) and runs/demo/media/.
Stdlib only; ffmpeg is used (if present) to extract the agent-01 still frame. No clock, no
randomness, no network: the same inputs give a byte-identical index.html.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
from pathlib import Path

CLIP_FPS = 20.7  # ffprobe r_frame_rate 207/10 of demo-01-nether-entry.mp4


def _jl(path: Path):
    out = []
    for i, line in enumerate(path.read_text().splitlines(), 1):
        line = line.strip()
        if line:
            out.append((i, line, json.loads(line)))
    return out


def _load(p: Path):
    return json.loads(p.read_text())


def _items(got):
    inv = {}
    for g in got:
        m = re.match(r"^(.*)x(\d+)$", g)
        name, n = (m.group(1), int(m.group(2))) if m else (g, 1)
        inv[name] = inv.get(name, 0) + n
    return inv


def _short(line: str, n: int = 900) -> str:
    return line if len(line) <= n else line[:n] + " …"


def replay_data(root: Path):
    run = root / "agent_runs" / "agent-06"
    ev_dir = root / "runs" / "agent-06-eval"
    events = _jl(run / "events.jsonl")
    epoch0 = events[0][2]["epoch"]
    t = lambda e: round((e["epoch"] - epoch0) / 1000.0, 3)

    # live-panel rows: every event, with derived inventory (from loot results)
    inv: dict = {}
    rows = []
    action = {"text": "spawn", "state": "idle"}
    for ln, raw, e in events:
        typ = e.get("type")
        if typ == "skill_start":
            a = e.get("args") or {}
            tgt = f" → ({a['x']}, {a['y']}, {a['z']})" if "x" in a else ""
            action = {"text": f"{e['skill']}{tgt}", "state": "running"}
        elif typ == "skill_result":
            ok = e.get("ok")
            err = e.get("error") or (e.get("result") or {}).get("error") or ""
            fr = (e.get("result") or {}).get("frame") or {}
            if fr.get("error"):
                err = f"{err}: {fr['error']}" if err else fr["error"]
            action = {"text": f"{e['skill']} {'OK' if ok else 'FAILED'} ({e['ms']/1000:.1f} s){' — ' + err if err else ''}",
                      "state": "ok" if ok else "fail"}
            res = e.get("result") or {}
            if e["skill"] == "loot_chest" and res.get("got"):
                for k, v in _items(res["got"]).items():
                    inv[k] = inv.get(k, 0) + v
            placed = fr.get("placed")
            if e["skill"] == "build_portal" and ok and placed:
                inv["obsidian"] = inv.get("obsidian", 0) - placed
        elif typ == "route_inventory":
            inv = _items(e["items"])
            inv["obsidian"] = inv.get("obsidian", 0)
        elif typ == "death":
            action = {"text": "DEATH in the Nether", "state": "fail"}
        elif typ == "linger":
            action = {"text": f"linger {e['seconds']} s (no route step left)", "state": "idle"}
        keep = {k: inv[k] for k in sorted(inv) if k in (
            "obsidian", "iron_pickaxe", "flint", "flint_and_steel", "iron_ingot", "bread", "netherrack")}
        rows.append({"line": ln, "t": t(e), "type": typ, "raw": _short(raw), "action": action,
                     "inv": keep, "inv_src": "logged (line %d)" % ln if typ == "route_inventory" else "derived from loot/build results"})

    by_type = {}
    for ln, raw, e in events:
        by_type.setdefault(e["type"], []).append((ln, t(e), e))
    portal_ln, portal_t, _ = by_type["route_portal"][0]
    death_ln, death_t, _ = by_type["death"][0]
    end_t = t(events[-1][2])
    starts = by_type["skill_start"]
    results = by_type["skill_result"]

    # server log (log tail lines + RCON samples)
    srv = _jl(run / "server_events.jsonl")
    srv_logs = [{"line": ln, "t": t(e), "kind": e.get("kind"), "text": e.get("line")}
                for ln, raw, e in srv if e.get("type") == "log"]
    samples = [e for _, _, e in srv if e.get("type") == "sample"]
    online = sum(1 for e in samples if e.get("online"))
    srv_span = [t(srv[0][2]), t(srv[-1][2])]

    # clip alignment
    ci_path = root / "runs" / "live" / "demo-01" / "clip_index.json"
    ci = _load(ci_path)
    frames = [round(f["run_t"], 3) for f in ci["frames"]]

    eff = _load(ev_dir / "efficiency.json")
    reval = _load(ev_dir / "runeval.json")
    pro = _load(root / "baseline" / "pro_2m49_segments.json")
    pro_in = pro["milestones_s"]["M_portal_in"]
    seg0 = eff["segments"][0]

    def finding(code, pred=lambda f: True):
        return [f for f in reval["findings"] if f["code"] == code and pred(f)]

    goto_fail = finding("failed_action", lambda f: 31 in f["lines"])[0]
    exit_fail = finding("failed_action", lambda f: 34 in f["lines"])[0]
    idle = finding("idle")[0]
    death = finding("death")[0]
    contra = finding("self_report_contradiction")
    raw_by_line = {ln: _short(raw, 600) for ln, raw, _ in events}

    def ev(lines):
        return [{"line": l, "raw": raw_by_line[l]} for l in lines if l in raw_by_line]

    build_res = results[[r[0] for r in results].index(27)][2]
    frm = build_res["result"]["frame"]
    adv = [s for s in srv_logs if "Go Deeper" in (s["text"] or "")]
    srv_death = [s for s in srv_logs if s["kind"] == "death"]

    loot = [(ln, tt, e) for ln, tt, e in by_type.get("route_loot", [])]
    segments = [
        {"id": "chests", "label": "Chests", "t0": 0.0, "t1": loot[-1][1], "kind": "good",
         "title": "3 supply chests looted",
         "finding": "Chests matched to the pro by contents: village (iron pickaxe), obsidian chest, flint chest. "
                    "Obsidian collected: 21. All three ahead of the pro's chest times (report.md, Progress by step).",
         "lines": [l for l, _, _ in loot]},
        {"id": "build", "label": "Build", "t0": starts[[s[0] for s in starts].index(26)][1], "t1": portal_t, "kind": "good",
         "title": f"Portal frame {frm['placed']}/{frm['targets']} placed and lit → Nether",
         "finding": f"build_portal ok in {build_res['ms']/1000:.1f} s; spawn_to_nether {seg0['agent_s_low']} s vs pro "
                    f"{seg0['pro_s']} s = {seg0['ratio_low']}x ({seg0['verdict']}). Server log corroborates: "
                    f"advancement \"We Need to Go Deeper\" at t={adv[0]['t'] if adv else '?'} s.",
         "lines": [26, 27, portal_ln]},
        {"id": "goto", "label": "Nether goto — 240 s TIMEOUT", "t0": goto_fail["t_start"], "t1": goto_fail["t_end"], "kind": "bad",
         "title": "Nether travel: goto timed out after 240 s",
         "finding": goto_fail["message"] + ". Netherrack/lava terrain; pathfinder never reached (-139, 41, 100).",
         "lines": goto_fail["lines"]},
        {"id": "exit", "label": "Exit portal abort", "t0": exit_fail["t_start"], "t1": exit_fail["t_end"], "kind": "bad",
         "title": "Exit portal aborted: \"no obsidian in inventory\"",
         "finding": exit_fail["message"] + ". The 7 spare obsidian (21 looted − 14 placed) were gone: "
                    "the logged inventory at line 37 has 0 obsidian.",
         "lines": [34, 37]},
        {"id": "idle", "label": "Idle", "t0": idle["t_start"], "t1": idle["t_end"], "kind": "warn",
         "title": "Idle: no route step left", "finding": idle["message"], "lines": idle["lines"]},
    ]
    markers = [
        {"id": "death", "t": death_t, "kind": "bad", "label": "Death",
         "title": f"Death at {death_t} s",
         "finding": death["message"] + (f". Server log line {srv_death[0]['line']}: \"{srv_death[0]['text']}\" at t={srv_death[0]['t']} s." if srv_death else ""),
         "lines": [death_ln]},
        {"id": "summary", "t": end_t, "kind": "bad", "label": "Summary",
         "title": "Self-report contradicted (4 findings)",
         "finding": " · ".join(f["message"] for f in contra), "lines": [events[-1][0]]},
    ]
    for s in segments + markers:
        s["evidence"] = ev(s["lines"])

    toasts = [
        {"t": portal_t - 0.005, "kind": "good", "title": segments[1]["title"], "body": f"line 27 · placed {frm['placed']}, failed {len(frm['failed'])}, lit"},
        {"t": portal_t, "kind": "good", "title": "Entered the Nether", "body": f"line {portal_ln} route_portal · dimension the_nether"},
    ]
    if adv:
        toasts.append({"t": adv[0]["t"], "kind": "good", "title": "Server confirms",
                       "body": f"server log line {adv[0]['line']}: \"{adv[0]['text']}\""})
    toasts.append({"t": pro_in, "kind": "info", "title": "Ghost pro enters the Nether", "body": f"pro M_portal_in {pro_in} s (2:49 run, IGT)"})
    toasts.append({"t": frames[-1] - 3.0, "kind": "bad", "title": "Next 240 s: goto timeout",
                   "body": "line 31 · nether goto fails after 239.995 s (outside this clip)"})

    seg_rows = [{"segment": s["segment"], "verdict": s["verdict"], "agent_s": s.get("agent_s_low"),
                 "pro_s": s["pro_s"], "ratio": s.get("ratio_low")} for s in eff["segments"]]
    return {
        "run_id": "agent-06", "epoch0": epoch0, "rows": rows,
        "portal_t": portal_t, "pro_portal_in": pro_in, "ahead_s": round(pro_in - portal_t, 3),
        "death_t": death_t, "end_t": end_t,
        "clip": {"src": "media/demo-01-nether-entry.mp4", "fps": CLIP_FPS, "frames": frames,
                 "t0": frames[0], "t1": frames[-1],
                 "method": f"Per-frame index: runs/live/demo-01/clip_index.json gives run_t for each of the {len(frames)} "
                           f"captured frames (spawn_epoch {ci['spawn_epoch']} = log line 1 epoch). Video time v maps to "
                           f"frame floor(v x {CLIP_FPS} fps) and its run_t, interpolated between frames."},
        "segments": segments, "markers": markers, "toasts": toasts,
        "server": {"span": srv_span, "logs": srv_logs, "samples": len(samples), "online": online},
        "seg_rows": seg_rows,
        "headline": [
            {"kind": "good", "text": f"spawn_to_nether {seg0['ratio_low']:.2f}x pro · {seg0['verdict']}"},
            {"kind": "bad", "text": f"nether: NOT COMPLETED · died at {death_t:.1f} s"},
        ],
    }


def caught_data(root: Path):
    rv = _load(root / "runs" / "agent-01-eval" / "runeval.json")
    ev = _jl(root / "agent_runs" / "agent-01" / "events.jsonl")
    summary = [e for _, _, e in ev if e["type"] == "summary"][-1]
    raw = {ln: _short(r, 500) for ln, r, _ in ev}
    f = {x["code"]: x for x in rv["findings"] if x["code"] != "self_report_contradiction"}
    contra = [x for x in rv["findings"] if x["code"] == "self_report_contradiction"]
    n_actions = sum(1 for _, _, e in ev if e["type"] == "skill_result")
    n_fail = sum(1 for _, _, e in ev if e["type"] == "skill_result" and not e["ok"])
    others = []
    for n in range(2, 7):
        p = root / "runs" / f"agent-0{n}-eval" / "runeval.json"
        if not p.exists():
            continue
        c = [x["message"] for x in _load(p)["findings"] if x["code"] == "self_report_contradiction"]
        if c:
            others.append({"run": f"agent-0{n}", "count": len(c), "messages": c})
    return {
        "claimed": {"actions": summary["actions"], "failures": summary["failures"], "line": [ln for ln, _, e in ev if e["type"] == "summary"][-1]},
        "actual": {"actions": n_actions, "failures": n_fail},
        "build": {"message": f["failed_action"]["message"], "raw": raw[27]},
        "obsidian": f["inventory_loss_without_effect"]["message"],
        "contra": [x["message"] for x in contra],
        "others": others,
        "still": "media/agent-01-portal-site.jpg",
    }


def published_data(root: Path):
    pm = _load(root / "runs" / "results_pack" / "efficiency" / "published_montage.json")
    fx = _load(root / "runs" / "results_pack" / "efficiency" / "fixtures.json")
    rules = _load(root / "baseline" / "rules.json")
    ms = [r for r in rules.get("waste_rules", []) if isinstance(r, dict) and r.get("tag") == "missed_shortcut"] \
        if isinstance(rules, dict) else []
    return {
        "segments": pm["segments"], "total": pm["total"], "median": pm["run_median_ratio"],
        "fixtures": [{"fixture": x["fixture"], "pass": bool(x.get("pass"))} for x in fx],
        "missed_shortcut_rule": ms[0]["when"] if ms else "overworld arrival more than 8 blocks (3D) from the End portal",
        "missed_shortcut": "Route's Nether exit (-141, 40, 104) puts the agent out at (-1129.5, 24, 837.5): 18.5 blocks "
                           "horizontally and 10 below the End portal, then ~52 s of digging and walking. The pro's exit "
                           "lands inside the End portal room: 2 blocks placed, drop in, 2.45 s. (WRITEUP.md, finding 1)",
    }


PITCH_RUNS = ["agent-01", "agent-02", "agent-03", "agent-04", "agent-05", "demo-01", "demo-02", "demo-03",
              "demo-04", "demo-05", "live-01", "live-02", "live-03"]  # 13 distinct runs (agent-06 == demo-01)


def pitch_data(root: Path):
    rows = []
    for run in PITCH_RUNS:
        d = root / "runs" / f"{run}-eval"
        rv, eff = _load(d / "runeval.json"), _load(d / "efficiency.json")
        s0 = eff["segments"][0]
        contra = sum(1 for f in rv["findings"] if f["code"] == "self_report_contradiction")
        w = sorted((f for f in rv["findings"] if f.get("attributed_s")), key=lambda f: -f["attributed_s"])
        big = (f"{w[0]['code']} {w[0]['attributed_s']:.1f} s (line {w[0]['lines'][0]})" if w and w[0].get("lines")
               else (f"{w[0]['code']} {w[0]['attributed_s']:.1f} s" if w else "-"))
        rows.append({"run": run, "nether": bool(rv["summary"]["milestones"].get("nether_entry")),
                     "ratio": s0.get("ratio_low"), "verdict": s0["verdict"], "contra": contra, "waste": big})
    det = _load(root / "runs" / "results_pack" / "determinism.json")
    txt = (root / "runs" / "results_pack" / "RESULTS.md").read_text()
    st = {m.group(1): (int(m.group(2)), int(m.group(3))) for m in re.finditer(r"- (seed|generic): (\d+)/(\d+) cases pass", txt)}
    dm = re.search(r"\| (\S+) \| (\d+) \| (\d+) \| (\d+) \| (\d+) \|\n\n\| task", txt)
    nt = re.search(r"across (\d+) tasks", txt)
    return {"runs": rows, "n_runs": len(rows), "n_contra": sum(1 for r in rows if r["contra"]),
            "det_files": det["files"], "det_identical": det["identical"],
            "selftest": {k: v[0] for k, v in st.items()}, "selftest_total": sum(v[1] for v in st.values()),
            "selftest_pass": sum(v[0] for v in st.values()),
            "decision": ({"model": dm.group(1), "illegal": int(dm.group(2)), "ok": int(dm.group(3)),
                          "wrong": int(dm.group(4)), "total": int(dm.group(5))} if dm else None),
            "n_tasks": int(nt.group(1)) if nt else None,
            "seed": "8398967436125155523", "version": "Java 1.16.5"}


def build(root: Path, out: Path) -> Path:
    root, out = root.resolve(), out.resolve()
    media = out / "media"
    media.mkdir(parents=True, exist_ok=True)
    clip_src = root / "evidence" / "footage" / "demo-01-nether-entry.mp4"
    dst = media / "demo-01-nether-entry.mp4"
    if not dst.exists() or dst.read_bytes() != clip_src.read_bytes():
        shutil.copyfile(clip_src, dst)
    still = media / "agent-01-portal-site.jpg"
    if not still.exists() and shutil.which("ffmpeg"):
        subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", str(root / "evidence" / "footage" / "agent-01-chests.mp4"),
                        "-frames:v", "1", "-vf", "scale=960:-2", "-q:v", "3", "-map_metadata", "-1", str(still)], check=True)
    stills = [  # (source, ffmpeg select / seek, output) -- overlay strips cropped off
        (root / "evidence" / "footage" / "demo-01-nether-entry.mp4", ["-vf", "select=eq(n\\,285),crop=960:430:0:40"], "s-portal.jpg"),
        (root / "evidence" / "footage" / "demo-04-nether-travel.mp4", ["-ss", "20", "-vf", "crop=960:430:0:40"], "s-nether.jpg"),
        (root / "agent_runs" / "agent-05" / "frames-clean" / "f00100.jpg", ["-vf", "scale=960:-2"], "s-chests.jpg"),
    ]
    for src, args, name in stills:
        dst_s = media / name
        if not dst_s.exists() and src.exists() and shutil.which("ffmpeg"):
            pre = args[:2] if args[0] == "-ss" else []
            rest = args[2:] if pre else args
            subprocess.run(["ffmpeg", "-loglevel", "error", "-y", *pre, "-i", str(src), *rest, "-frames:v", "1",
                            "-q:v", "4", "-map_metadata", "-1", str(dst_s)], check=True)
    data = {"replay": replay_data(root), "caught": caught_data(root), "published": published_data(root), "pitch": pitch_data(root),
            "reproduce": "cd code && python -m splitcheck.demo --root .. --out ../runs/demo"}
    blob = json.dumps(data, sort_keys=True, ensure_ascii=False, indent=None).replace("</", "<\\/")
    tpl = (Path(__file__).with_name("demo_template.html")).read_text()
    html = tpl.replace("/*__DATA__*/null", blob)
    page = out / "index.html"
    page.write_text(html)
    return page


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", default="..")
    ap.add_argument("--out", default="../runs/demo")
    a = ap.parse_args(argv)
    print(build(Path(a.root), Path(a.out)))


if __name__ == "__main__":
    main()
