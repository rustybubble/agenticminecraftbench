"""One command for the v4 efficiency check: game log in, four judge-facing files out.

    python -m splitcheck.evaluate <log> [--baseline ../baseline/pro_2m49_segments.json]
        [--run-id NAME] [--outdir ../agent_runs/NAME] [--seed-dir DIR] [--rules PATH]
        [--server-log server_events.jsonl]

--perception perception.json (or --footage VIDEO [--backend codex|fake] to compute it first with
splitcheck.perception) adds a "Perception (AI-assisted, validated)" section to report.md and a
"perception" block to runeval.json: AI observations of footage frames, their validated accuracy
(splitcheck.perception_validate) and deterministic perception-assisted findings
(splitcheck.detectors_perception, cost 0). Without these flags nothing changes; with them the
headline verdicts, efficiency.json and timeline.json are unchanged.

--server-log adds a claims cross-check of the agent log against the server-side poller log
(agent_server_mismatch findings, +-1.5 s) and an "Evidence coverage" section. Verdicts are unchanged.

Writes into the output directory:

- timeline.json    SCHEMA section 8 agent_timeline (splitcheck.v4export)
- efficiency.json  SCHEMA section 8 segment verdicts (splitcheck.effcheck, rules from baseline/rules.json)
- runeval.json     the full RunEval report (splitcheck.runeval), the evidence behind the waste entries
- report.md        headline table, per-segment waste with RunEval evidence, fairness notes

No LLM, no network, no clock, no randomness: the same input gives byte-identical files.
effcheck and v4export are imported lazily so this module loads even while they are absent.
"""
from __future__ import annotations

import argparse
import importlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]  # repo root (code/splitcheck/evaluate.py -> repo)
DEFAULT_BASELINE = ROOT / "baseline" / "pro_2m49_segments.json"
OUTPUTS = ("timeline.json", "efficiency.json", "runeval.json", "report.md")


def _mod(name: str):
    """Lazy import of a sibling module, with a clear message if a builder has not landed it yet."""
    try:
        return importlib.import_module(f"{__package__ or 'splitcheck'}.{name}")
    except ModuleNotFoundError as ex:
        if ex.name and ex.name.endswith(name):
            raise RuntimeError(f"splitcheck.{name} is not available yet (code/splitcheck/{name}.py)") from ex
        raise


def default_run_id(log_path) -> str:
    p = Path(log_path)
    stem = p.stem
    if stem in ("events", "log", "run") and p.parent.name:
        return p.parent.name
    return stem


def _dump(obj, sort_keys=True) -> str:
    return json.dumps(obj, indent=2, sort_keys=sort_keys, ensure_ascii=False) + "\n"


def _write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


# ---------------------------------------------------------------- report.md
def _f(x, unit=""):
    if x is None:
        return "-"
    if isinstance(x, float):
        x = round(x, 3)
    return f"{x}{unit}"


def _pair(lo, hi, unit=""):
    if lo is None and hi is None:
        return "-"
    if lo == hi:
        return _f(lo, unit)
    return f"{_f(lo)}-{_f(hi)}{unit}"


def _ev(e) -> str:
    if e is None:
        return ""
    if isinstance(e, str):
        s = e
    else:
        s = json.dumps(e, sort_keys=True, ensure_ascii=False)
    s = " ".join(s.split())
    return s.replace("|", "\\|")


def _waste_sum(ws) -> float | None:
    vals = [w.get("seconds") for w in ws if isinstance(w.get("seconds"), (int, float))]
    return round(sum(vals), 3) if vals else None


def _waste_cell(seg) -> str:
    """Tagged waste for the headline table. Entries overlap (different tags, repeated RunEval hits
    over the same seconds), so the raw sum is an upper bound; the shown value is capped at the
    segment's excess over the pro (agent_s_low - pro_s), with the raw sum in brackets when capped."""
    raw = _waste_sum(seg.get("waste", []))
    lo, pro = seg.get("agent_s_low"), seg.get("pro_s")
    if raw is None or lo is None or pro is None:
        return _f(raw)
    cap = round(max(0.0, lo - pro), 3)
    return _f(raw) if raw <= cap else f"{_f(cap)} (raw {_f(raw)})"


def _timer_lines(eff, baseline, rules) -> list:
    """fairness.timer: the agent clock is wall clock, pro segments are IGT. Report the total against
    pro RTA too, and say where the IGT/RTA gap (mostly portal loads) could decide a FLAG."""
    off = (baseline or {}).get("official") or {}
    rta = off.get("rta_s")
    ms = (baseline or {}).get("milestones_s") or {}
    segs = rules.get("segments") or []
    if not segs or rta is None:
        return []
    igt = None
    a, b = ms.get(segs[0]["from"]), ms.get(segs[-1]["to"])
    if a is not None and b is not None:
        igt = round(b - a, 3)
    t = eff.get("total") or {}
    lo, hi = t.get("agent_s_low"), t.get("agent_s_high")
    L = ["## Timer basis (fairness.timer)", "",
         f"The agent clock is wall clock (portal loading and model latency included). Pro segment times "
         f"are IGT (total {_f(igt)} s); the pro's RTA is {_f(rta)} s."]
    if lo is not None and rta:
        L.append(f"Agent total vs pro RTA: {_pair(lo, hi)} s / {_f(rta)} s = ratio "
                 f"{_pair(round(lo / rta, 3), round(hi / rta, 3))}.")
    else:
        L.append("Agent total vs pro RTA: not scored (run unfinished).")
    gap = round(rta - igt, 3) if igt is not None else None
    vmin = (rules.get("verdict") or {}).get("flag_min_excess_s")
    if gap and gap > 0 and vmin is not None:
        close = [s["segment"] for s in eff.get("segments", [])
                 if s.get("verdict") == "FLAG" and s.get("agent_s_low") is not None
                 and s["agent_s_low"] - s["pro_s"] - gap < vmin]
        L.append(f"The pro's RTA-IGT gap is {_f(gap)} s, mostly portal loads that the agent's segments include. "
                 + (f"FLAG on {', '.join(close)} would not clear the {vmin} s floor if that whole gap fell in "
                    f"the segment; read it with that in mind." if close else
                    "No FLAG verdict depends on it."))
    return L + [""]


def _rel(p) -> str:
    """Show repo files relative to the repo root so report.md does not depend on the checkout path."""
    try:
        return Path(p).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(p)


def to_markdown(run_id, log_path, baseline_path, timeline, eff, rep, rules, baseline=None,
                xcheck=None, server_log=None, perception=None) -> str:
    L = [f"# Efficiency check: `{run_id}`", "",
         f"Log: `{_rel(log_path)}`. Baseline: `{_rel(baseline_path)}`. Deterministic (no LLM): every number "
         "comes from timeline.json, efficiency.json and runeval.json in this folder.", ""]
    if "error" in eff:
        L += [f"**Efficiency check failed:** {eff['error']}", ""]
    else:
        for fl in eff.get("flags", []):
            L += [f"**WARNING: {fl}**", ""]
        L += [f"Run median ratio: **{_f(eff.get('run_median_ratio'))}**", "",
              "| Segment | Agent s | Pro s | Ratio (low-high) | Verdict | Waste s (tagged, capped at excess) |",
              "|---|---|---|---|---|---|"]
        for s in eff.get("segments", []):
            if "verdict" not in s:  # whole-run rows (model latency) carry no verdict
                continue
            L.append(f"| {s['segment']} | {_pair(s.get('agent_s_low'), s.get('agent_s_high'))} | "
                     f"{_f(s.get('pro_s'))} | {_pair(s.get('ratio_low'), s.get('ratio_high'))} | "
                     f"**{s['verdict']}** | {_waste_cell(s)} |")
        t = eff.get("total", {})
        L.append(f"| **total** | {_pair(t.get('agent_s_low'), t.get('agent_s_high'))} | {_f(t.get('pro_s'))} | "
                 f"{_pair(t.get('ratio_low'), t.get('ratio_high'))} | | |")
        notes = {k: v.get("note") for k, v in (timeline.get("milestones") or {}).items()
                 if isinstance(v, dict) and v.get("note")}
        if notes:
            L += ["", "Milestone notes: " + "; ".join(f"{k}: {v}" for k, v in sorted(notes.items()))]
        vr = rules.get("verdict", {})
        L += ["", f"Verdict rule (baseline/rules.json): {vr.get('rule', '')}",
              f"Thresholds: ok_max_ratio={vr.get('ok_max_ratio')}, flag_k_times_median="
              f"{vr.get('flag_k_times_median')}, flag_min_excess_s={vr.get('flag_min_excess_s')}.", ""]
        L += ["## Waste by segment", "",
              "Waste never changes a verdict. Seconds are upper-bound estimates; RunEval entries keep "
              "their detector code and log lines in the evidence. Entries can overlap: see "
              "runeval.json `score.attributed_waste_s` for the overlap-merged total.", ""]
        for s in eff.get("segments", []):
            ws = s.get("waste", [])
            head = f"### {s['segment']}" + (f" ({s['verdict']})" if "verdict" in s else "")
            L += [head, ""]
            if not ws:
                L += ["No waste found.", ""]
                continue
            L += ["| Tag | Seconds | Evidence |", "|---|---|---|"]
            for w in ws:
                L.append(f"| {w.get('tag')} | {_f(w.get('seconds'))} | {_ev(w.get('evidence'))} |")
            L.append("")
        L += _timer_lines(eff, baseline, rules)
    sc = (rep or {}).get("score", {})
    if sc:
        L += ["## RunEval summary", "",
              f"Total {_f(sc.get('total_time_s'), ' s')}, attributed waste (overlaps merged) "
              f"{_f(sc.get('attributed_waste_s'), ' s')}, efficiency {_f(sc.get('efficiency'))}, "
              f"milestones {sc.get('milestones_reached')}/{sc.get('milestones_total')}, "
              f"findings {len(rep.get('findings', []))}. Full detail in runeval.json.", ""]
    L += _claims_lines(rep, xcheck, server_log)
    if perception:
        L += _perception_lines(perception, xcheck)
    fair = rules.get("fairness") or {}
    if fair:
        L += ["## Fairness notes (from baseline/rules.json)", ""]
        for k, v in fair.items():
            L.append(f"- **{k}**: {v}")
        L.append("")
    return "\n".join(L).rstrip("\n") + "\n"


# ---------------------------------------------------------------- server cross-check
SERVER_WINDOW_S = 1.5
SERVER_POS_TOL = 3.0  # blocks (3D) between the agent's reported position and the server sample


def _abs_samples(tl):
    t0 = (tl.meta or {}).get("t0_epoch")
    if t0 is None:
        return []
    return [(t0 + s.t, s) for s in tl.samples]


def server_crosscheck(agent_tl, server_tl) -> dict:
    """Compare agent position/inventory snapshots with the nearest server sample within +-1.5 s.
    Returns {"findings": [...], "coverage": {...}}. Deterministic; no verdict changes."""
    import math
    ag = _abs_samples(agent_tl)
    sv = [(t, s) for t, s in _abs_samples(server_tl) if s.pos is not None or s.inv]
    a0 = agent_tl.meta.get("t0_epoch")
    live = (agent_tl.meta or {}).get("live_agent") or {}
    snap_lines = {x["line"] for x in live.get("inventory_snapshots") or []}
    findings, checked, uncovered = [], 0, []

    def nearest(t):
        best = None
        for ts, s in sv:
            d = abs(ts - t)
            if d <= SERVER_WINDOW_S and (best is None or d < best[0]):
                best = (d, ts, s)
        return best

    for t, s in ag:
        pos_snap = s.kind in ("skill_result", "spawn", "summary") and s.pos is not None
        inv_snap = s.line in snap_lines
        if not (pos_snap or inv_snap):
            continue
        nb = nearest(t)
        if nb is None:
            uncovered.append(s.line)
            continue
        checked += 1
        d, ts, ss = nb
        rel = round(ts - a0, 3)
        if pos_snap and ss.pos is not None:
            dist = math.dist([s.pos[0], s.pos[1] or 0, s.pos[2]], [ss.pos[0], ss.pos[1] or 0, ss.pos[2]])
            if dist > SERVER_POS_TOL or (ss.dim and s.dim and ss.dim != s.dim):
                findings.append({"code": "agent_server_mismatch", "category": "claim", "severity": "high",
                                 "t_start": s.t, "t_end": s.t, "cost_s": 0.0, "lines": [s.line],
                                 "server_lines": [ss.line],
                                 "message": f"agent line {s.line} reports pos {tuple(round(v, 1) for v in s.pos)} "
                                            f"({s.dim}); server line {ss.line} (t={rel}) has "
                                            f"{tuple(round(v, 1) for v in ss.pos)} ({ss.dim}), {round(dist, 2)} blocks apart",
                                 "evidence": {"field": "position", "dt_s": round(d, 3)}})
        if inv_snap and ss.inv:
            diff = {k: (s.inv.get(k, 0), ss.inv.get(k, 0)) for k in sorted(set(s.inv) | set(ss.inv))
                    if s.inv.get(k, 0) != ss.inv.get(k, 0)}
            if diff:
                findings.append({"code": "agent_server_mismatch", "category": "claim", "severity": "high",
                                 "t_start": s.t, "t_end": s.t, "cost_s": 0.0, "lines": [s.line],
                                 "server_lines": [ss.line],
                                 "message": f"agent inventory snapshot line {s.line} vs server line {ss.line} "
                                            f"(t={rel}): " + ", ".join(f"{k} agent {a} / server {b}"
                                                                       for k, (a, b) in diff.items()),
                                 "evidence": {"field": "inventory", "diff": diff, "dt_s": round(d, 3)}})
    a_span = (0.0, agent_tl.meta.get("duration_s") or 0.0)
    s_first = round(sv[0][0] - a0, 3) if sv and a0 is not None else None
    s_last = round(sv[-1][0] - a0, 3) if sv and a0 is not None else None
    notes = []
    if s_first is not None and s_first > a_span[0] + SERVER_WINDOW_S:
        notes.append(f"server log starts {s_first} s after the agent run start")
    if s_last is not None and s_last < a_span[1] - SERVER_WINDOW_S:
        notes.append(f"server log ends at t={s_last} s, {round(a_span[1] - s_last, 3)} s before the agent run "
                     f"ends (t={a_span[1]} s)")
        for r in live.get("skill_results") or []:
            if r["t"] > s_last + SERVER_WINDOW_S:
                st = [x for x in live.get("skill_starts") or [] if x["line"] < r["line"]]
                if st and st[-1]["t"] <= s_last:
                    notes.append(f"server log ends during the {r['skill']} attempt (started t={st[-1]['t']} s, "
                                 f"line {st[-1]['line']}; result t={r['t']} s, line {r['line']})")
                notes.append(f"no server evidence for {r['skill']} result at t={r['t']} s (line {r['line']}"
                             f"{', FAILED' if not r['ok'] else ''})")
        for x in live.get("inventory_snapshots") or []:
            if x["t"] > s_last + SERVER_WINDOW_S:
                notes.append(f"no server evidence for the inventory snapshot at t={x['t']} s (line {x['line']})")
    cov = {"agent_span_s": [a_span[0], a_span[1]], "server_first_t_s": s_first, "server_last_t_s": s_last,
           "server_samples": len(sv), "snapshots_checked": checked,
           "snapshots_without_server_sample": uncovered, "notes": notes}
    return {"findings": findings, "coverage": cov}


def _claims_lines(rep, xcheck, server_log) -> list:
    claims = [f for f in (rep or {}).get("findings", []) if f.get("category") == "claim"]
    if xcheck:
        claims = claims + xcheck["findings"]
    L = []
    if claims:
        L += ["## Claims cross-check", "",
              "Deterministic checks of what the agent reported against its own log"
              + (" and the server log" if xcheck else "") + ". Claims never change a verdict.", "",
              "| Code | Severity | t s | Lines | Finding |", "|---|---|---|---|---|"]
        for f in claims:
            ln = ", ".join(map(str, f.get("lines", [])))
            if f.get("server_lines"):
                ln += " (server " + ", ".join(map(str, f["server_lines"])) + ")"
            L.append(f"| {f.get('code')} | {f.get('severity')} | {_f(f.get('t_start'))} | {ln} | "
                     f"{_ev(f.get('message'))} |")
        L.append("")
    if xcheck:
        c = xcheck["coverage"]
        L += ["## Evidence coverage", "",
              f"Server log: `{_rel(server_log)}`, {c['server_samples']} samples, t={_f(c['server_first_t_s'])}"
              f"-{_f(c['server_last_t_s'])} s (agent run t={_f(c['agent_span_s'][0])}-{_f(c['agent_span_s'][1])} s). "
              f"Agent snapshots checked against a server sample within +-{SERVER_WINDOW_S} s: "
              f"{c['snapshots_checked']}; without one: {len(c['snapshots_without_server_sample'])}"
              + (f" (lines {', '.join(map(str, c['snapshots_without_server_sample']))})"
                 if c["snapshots_without_server_sample"] else "") + "."]
        if not c.get("server_samples"):
            L += ["- **no usable server samples** (log empty, unparsed format, or the player was never seen online): "
                  "there is NO server-side evidence for this run; every finding rests on the agent's own log"]
        else:
            L += [f"- {n}" for n in c["notes"]] or ["- server log covers the whole agent run"]
        L.append("")
    return L


# ---------------------------------------------------------------- perception (AI-assisted)
def _load_json(p):
    with open(p, encoding="utf-8") as fh:
        return json.load(fh)


def compute_perception(footage, log_path, backend="codex", every=2.0, votes=1, out=None) -> str:
    """Run the splitcheck.perception CLI contract on footage; returns the perception.json path.
    Observations are cached on disk by that module, so reruns replay identically."""
    perc = _mod("perception")
    out = Path(out) if out else ROOT / "code" / ".perception_cache" / f"{Path(footage).stem}.perception.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    rc = perc.main([str(footage), "--run-log", str(log_path), "--out", str(out), "--every", str(every),
                    "--votes", str(votes), "--backend", backend])
    if rc not in (None, 0) or not out.exists():
        raise RuntimeError(f"splitcheck.perception failed on {footage} (exit {rc})")
    return str(out)


def perception_block(perception_path, log_path, server_log=None, seed_dir=None) -> dict:
    """Validate perception against ground truth and run the perception-assisted detectors."""
    import dataclasses
    tlmod = _mod("timeline")
    dpm = _mod("detectors_perception")
    data = _load_json(perception_path)
    atl = tlmod.load_timeline(log_path)
    stl = tlmod.load_timeline(server_log) if server_log else None
    validation, verr = None, None
    try:
        pv = _mod("perception_validate")
        from .seedfeatures import load_seed_features
        validation = pv.validate(data, atl, stl, load_seed_features(seed_dir))
    except Exception as ex:  # validation is optional; findings then say "unvalidated"
        verr = f"{type(ex).__name__}: {ex}"
    findings = [dataclasses.asdict(f) for f in dpm.detect(data, atl, stl, validation)]
    frames = dpm.frames_of(data, include_after_end=True)
    in_run = dpm.frames_of(data)
    dur = (atl.meta or {}).get("duration_s")
    if isinstance(dur, (int, float)):
        in_run = [f for f in in_run if f["t"] <= dur]
    recs = data.get("frames", []) if isinstance(data, dict) else data
    models = sorted({str(r.get("model")) for r in recs if r.get("model")})
    meta = data if isinstance(data, dict) else {}
    s_last = None
    if stl is not None and stl.samples:
        a0, s0 = (atl.meta or {}).get("t0_epoch"), (stl.meta or {}).get("t0_epoch")
        s_last = round(stl.samples[-1].t + ((s0 - a0) if a0 is not None and s0 is not None else 0.0), 3)
    per_field = {}
    if validation:
        per_field = {k: {"n": v.get("n"), "correct": v.get("correct"), "accuracy": v.get("accuracy"),
                         "ci95": v.get("ci95"), "sufficient": v.get("sufficient")}
                     for k, v in (validation.get("per_field") or {}).items()}
    return {"perception": _rel(perception_path), "label": "perception-assisted",
            "model": meta.get("model") or (models[0] if len(models) == 1 else models),
            "backend": meta.get("backend"), "backend_params": meta.get("backend_params"),
            "prompt_sha": meta.get("prompt_sha"), "frames": len(recs), "frames_aligned": len(frames),
            "frames_in_run": len(in_run), "frames_after_run_log_end": len(frames) - len(in_run),
            "run_duration_s": dur,
            "distinct_frames": len({r.get("frame_sha") for r in recs if r.get("frame_sha")}),
            # backend calls / cache hits are per-run provenance: they live in perception.json "stats"
            # and are kept out of report.md / runeval.json so reruns are byte-identical.
            "validation": {"per_field": per_field,
                           "validated_fields": (validation or {}).get("validated_fields"),
                           "insufficient_fields": (validation or {}).get("insufficient_fields"),
                           "min_n": (validation or {}).get("min_n"),
                           "log_consistency": (validation or {}).get("log_consistency"),
                           "unvalidated_fields": (validation or {}).get("unvalidated_fields"),
                           "notes": (validation or {}).get("notes", []), "error": verr},
            "findings": findings, "server_last_t_s": s_last,
            "frames_after_server_log": (sum(1 for f in in_run if f["t"] > s_last) if s_last is not None else None),
            "frame_span_s": [frames[0]["t"], frames[-1]["t"]] if frames else None}


def _perception_lines(pb, xcheck=None) -> list:
    v = pb.get("validation") or {}
    validated = bool(v.get("validated_fields")) if "validated_fields" in v else bool(v.get("per_field"))
    head = ("## Perception (AI-assisted, validated)" if validated else
            "## Perception (AI-assisted, validation insufficient)")
    L = [head, "",
         "A vision model was used ONLY to say what is visible in footage frames (overlay text cropped "
         "out); every finding below is a deterministic rule over those observations, labelled "
         "perception-assisted, cost 0 s. Headline verdicts above do not use perception.", "",
         f"Perception file: `{pb['perception']}`. Model: `{_ev(pb.get('model'))}`. Frames: {pb['frames']} "
         f"({pb['frames_aligned']} aligned to run time"
         + (f", t={pb['frame_span_s'][0]}-{pb['frame_span_s'][1]} s" if pb.get("frame_span_s") else "")
         + f"; {_f(pb.get('distinct_frames'))} distinct frame images)."
         + (f" {pb['frames_after_run_log_end']} of these frames fall after the agent run log ends "
            f"(t={pb['run_duration_s']} s) and are not used by any perception finding."
            if pb.get("frames_after_run_log_end") else ""), ""]
    if not validated:
        L += [f"No field has at least {_f(v.get('min_n'))} non-circular ground-truth labels, so every "
              "perception result below is a low-confidence observation, not evidence.", ""]
    pf = v.get("per_field") or {}
    if pf:
        L += ["### Validation against ground truth", "",
              "| Field | n | Correct | Accuracy | 95% CI | Status |", "|---|---|---|---|---|---|"]
        for k, r in pf.items():
            ci = r.get("ci95")
            st = ("no labels" if not r.get("n") else "validated" if r.get("sufficient")
                  else f"insufficient (n < {_f(v.get('min_n'))})")
            L.append(f"| {k} | {_f(r.get('n'))} | {_f(r.get('correct'))} | {_f(r.get('accuracy'))} | "
                     f"{'' if not ci else f'{ci[0]}-{ci[1]}'} | {st} |")
        L.append("")
    for k, r in (v.get("log_consistency") or {}).items():
        L.append(f"Consistent with the agent-log claim (circular, not ground truth, not used for gating): "
                 f"{k} {r.get('consistent')}/{r.get('n')}.")
    if v.get("unvalidated_fields"):
        L.append("Unvalidated (no ground truth, findings using them say so): "
                 + ", ".join(v["unvalidated_fields"]) + ".")
    for n in v.get("notes") or []:
        L.append(f"Note: {n}")
    if v.get("error"):
        L.append(f"Validation unavailable ({v['error']}); every field is treated as unvalidated.")
    L.append("")
    fs = pb.get("findings") or []
    L += ["### Perception-assisted findings", ""]
    if fs:
        L += ["| Code | Category | Severity | t s | Lines | Finding |", "|---|---|---|---|---|---|"]
        for f in fs:
            L.append(f"| {f['code']} | {f['category']} | {f['severity']} | {_pair(f['t_start'], f['t_end'])} | "
                     f"{', '.join(map(str, f.get('lines', [])))} | {_ev(f['message'])} |")
    else:
        L.append("None.")
    L.append("")
    strong = [f for f in fs if not (f.get("evidence") or {}).get("low_confidence")]
    low = len(fs) - len(strong)
    L += ["### With vs without perception", "",
          "- Without: verdicts, waste and claims come from the agent log"
          + (" and the server log" if xcheck else "") + " only.",
          f"- With: {len(strong)} perception-assisted finding(s) added"
          + (f" ({', '.join(sorted({f['code'] for f in strong}))})" if strong else "")
          + (f", plus {low} low-confidence observation(s) not used as evidence" if low else "") + "."]
    if pb.get("server_last_t_s") is not None:
        gap = [f for f in strong if (f.get("evidence") or {}).get("frames_in_server_gap")]
        L.append(f"- Coverage: {_f(pb.get('frames_after_server_log'))} frame(s) fall after the server log's last "
                 f"sample (t={pb['server_last_t_s']} s)"
                 + (f"; {len(gap)} finding(s) rest on footage inside that server-log gap" if gap else "")
                 + ".")
    L += ["- Headline verdicts and segment ratios: unchanged.", ""]
    return L


# ---------------------------------------------------------------- run facts + progress (runmeta, submilestones)
def default_run_notes(log_path):
    """RUN_NOTES.md next to the log, if present."""
    p = Path(log_path).parent / "RUN_NOTES.md"
    return p if p.exists() else None


def _insert_before(md: str, headings, lines) -> str:
    """Insert markdown lines before the first heading in `headings` found in md (else append)."""
    if not lines:
        return md
    chunk = "\n".join(lines).rstrip("\n") + "\n\n"
    for h in headings:
        i = md.find("\n" + h)
        if i >= 0:
            return md[:i + 1] + chunk + md[i + 1:]
    return md.rstrip("\n") + "\n\n" + chunk.rstrip("\n") + "\n"


def run_context(log_path, run_notes=None, rules=None, ok=True) -> dict:
    """Run facts (RUN_NOTES.md), fairness notes that do not apply, and sub-milestone progress
    (the progress table is rendered only for partial runs: ok=False)."""
    runmeta = _mod("runmeta")
    sub = _mod("submilestones")
    tl = _mod("timeline").load_timeline(log_path)
    facts = runmeta.parse_run_notes(run_notes) if run_notes else {}
    if facts.get("source"):
        facts["source"] = _rel(facts["source"])
    reached = {ev["type"] for ev in tl.events}
    na = runmeta.fairness_applicability((rules or {}).get("fairness") or {}, facts, reached=reached)
    prog_lines, prog = sub.progress_section(tl)
    return {"facts": facts, "fairness_not_applicable": na, "progress": prog,
            "progress_lines": prog_lines if not ok else [], "this_run_lines": runmeta.this_run_lines(facts)}


def apply_run_context(md: str, ctx: dict) -> str:
    """Add '## This run' above the fairness notes, mark contradicted notes, add the progress table."""
    na = ctx.get("fairness_not_applicable") or {}
    if na:
        out = []
        for ln in md.split("\n"):
            for k, why in na.items():
                if ln.startswith(f"- **{k}**: "):
                    ln += f" **does not apply to this run: {why.rstrip('.')}.**"
            out.append(ln)
        md = "\n".join(out)
    md = _insert_before(md, ["## Fairness notes"], ctx.get("this_run_lines") or [])
    md = _insert_before(md, ["## Waste by segment", "## RunEval summary", "## Claims cross-check",
                             "## Perception", "## This run", "## Fairness notes"],
                        ctx.get("progress_lines") or [])
    return md


# ---------------------------------------------------------------- pipeline
def evaluate(log_path, baseline_path=None, run_id=None, outdir=None, seed_dir=None, rules_path=None,
             write=True, server_log=None, perception=None, footage=None, backend="codex",
             run_notes=None) -> dict:
    """Run RunEval -> v4export -> effcheck on one log. Returns {filename: text} plus parsed parts."""
    runeval = _mod("runeval")
    v4export = _mod("v4export")
    effcheck = _mod("effcheck")
    baseline_path = Path(baseline_path) if baseline_path else DEFAULT_BASELINE
    run_id = run_id or default_run_id(log_path)
    outdir = Path(outdir) if outdir else ROOT / "agent_runs" / run_id

    rep = runeval.evaluate_run(log_path, seed_dir=seed_dir)
    # same file however the path was typed (relative vs absolute)
    if isinstance(rep.get("summary"), dict) and "log" in rep["summary"]:
        rep["summary"]["log"] = _rel(log_path)
    meta = (rep.get("coverage") or {}).get("meta")
    if isinstance(meta, dict) and "path" in meta:
        meta["path"] = _rel(log_path)
    timeline = v4export.to_timeline(log_path, seed_dir=seed_dir, baseline_path=str(baseline_path),
                                    findings=rep.get("findings", []), rules_path=rules_path)
    timeline["run_id"] = run_id
    rules = effcheck.load_rules(rules_path) if rules_path else effcheck.load_rules()
    baseline = effcheck.load_baseline(str(baseline_path))
    try:
        eff = effcheck.check(timeline, baseline, rules)
        ok = True
    except Exception as ex:  # e.g. a milestone never reached; report it instead of writing nothing
        eff = {"error": f"{type(ex).__name__}: {ex}"}
        ok = False

    xcheck = None
    if server_log:
        tlmod = _mod("timeline")
        xcheck = server_crosscheck(tlmod.load_timeline(log_path), tlmod.load_timeline(server_log))
        rep["server_crosscheck"] = {"server_log": _rel(server_log), **xcheck}
    pblock = None
    if footage and not perception:
        perception = compute_perception(footage, log_path, backend=backend)
    if perception:
        pblock = perception_block(perception, log_path, server_log=server_log, seed_dir=seed_dir)
        rep["perception"] = pblock
    if run_notes is None:
        run_notes = default_run_notes(log_path)
    partial = not ok or any(sg.get("verdict") == "NOT_REACHED" for sg in eff.get("segments", []))
    ctx = run_context(log_path, run_notes or None, rules, ok=not partial)
    if ctx["facts"]:
        rep["run_facts"] = {"facts": ctx["facts"], "fairness_not_applicable": ctx["fairness_not_applicable"]}
    if partial:
        rep["progress"] = ctx["progress"]
    texts = {
        "timeline.json": _dump(timeline),
        "efficiency.json": _dump(eff, sort_keys=False),  # keep SCHEMA section 8 key order
        "runeval.json": _dump(rep),
        "report.md": to_markdown(run_id, log_path, baseline_path, timeline, eff, rep, rules, baseline,
                                 xcheck=xcheck, server_log=server_log, perception=pblock),
    }
    texts["report.md"] = apply_run_context(texts["report.md"], ctx)
    if write:
        for name in OUTPUTS:
            _write(outdir / name, texts[name])
    return {"ok": ok, "outdir": str(outdir), "run_id": run_id, "texts": texts,
            "timeline": timeline, "efficiency": eff, "runeval": rep}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m splitcheck.evaluate")
    ap.add_argument("log")
    ap.add_argument("--baseline", default=None, help="pro segments (default ../baseline/pro_2m49_segments.json)")
    ap.add_argument("--run-id", default=None, help="name of the run (default: log file stem)")
    ap.add_argument("--outdir", default=None, help="output folder (default ../agent_runs/<run-id>)")
    ap.add_argument("--seed-dir", default=None, help="seed feature dir (default: data/seed_<seed>)")
    ap.add_argument("--rules", default=None, help="rules file (default ../baseline/rules.json)")
    ap.add_argument("--server-log", default=None,
                    help="server-side poller log of the same run: cross-check claims, report coverage")
    ap.add_argument("--perception", default=None,
                    help="perception.json (splitcheck.perception): add the AI-assisted, validated section")
    ap.add_argument("--footage", default=None,
                    help="footage video: compute perception.json first (cached) with --backend")
    ap.add_argument("--backend", default="codex", choices=("codex", "fake"),
                    help="vision backend for --footage (default codex)")
    ap.add_argument("--run-notes", default=None,
                    help="RUN_NOTES.md with run facts (default: RUN_NOTES.md next to the log, if present)")
    a = ap.parse_args(argv)
    for flag, p in (("perception", a.perception), ("footage", a.footage)):
        if p and not Path(p).exists():
            print(f"{flag} not found: {p}", file=sys.stderr)
            return 2
    if a.run_notes and not Path(a.run_notes).exists():
        print(f"run notes not found: {a.run_notes}", file=sys.stderr)
        return 2
    if a.server_log and not Path(a.server_log).exists():
        print(f"server log not found: {a.server_log}", file=sys.stderr)
        return 2
    if not Path(a.log).exists():
        print(f"log not found: {a.log}", file=sys.stderr)
        return 2
    res = evaluate(a.log, baseline_path=a.baseline, run_id=a.run_id, outdir=a.outdir,
                   seed_dir=a.seed_dir, rules_path=a.rules, server_log=a.server_log,
                   perception=a.perception, footage=a.footage, backend=a.backend,
                   run_notes=a.run_notes)
    eff = res["efficiency"]
    if not res["ok"]:
        print(f"efficiency check failed: {eff['error']}", file=sys.stderr)
    else:
        verdicts = ", ".join(f"{s['segment']}={s['verdict']}({s.get('ratio_low')})"
                             for s in eff.get("segments", []) if "verdict" in s)
        print(f"{res['run_id']}: median ratio {eff.get('run_median_ratio')}; {verdicts}")
    print(f"wrote {', '.join(OUTPUTS)} to {res['outdir']}")
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
