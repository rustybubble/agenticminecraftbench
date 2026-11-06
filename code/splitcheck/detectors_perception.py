"""Perception-assisted detectors: deterministic rules over AI observations of footage frames.

The AI (splitcheck.perception) is used ONLY to say what is visible in a frame. Every rule here is a
pure function of perception.json + the agent timeline (+ optional server timeline and validation
report), so the same inputs give the same findings. Every finding is labelled "perception-assisted"
(message prefix and evidence["perception_assisted"]) and carries cost_s 0: footage observations
never change a verdict or the attributed waste.

Gating (all must hold, else the finding is emitted as a 'low-confidence observation', severity low):
  * frame confidence >= CONF_MIN, and
  * every field the rule reads has non-circular ground truth with n >= MIN_N (10) labels
    (perception_validate per_field; log-derived labels do not count), and
  * that validated accuracy is >= ACC_MIN.
  A field with no ground truth, or too few labels, makes the result an 'unvalidated' /
  'insufficient' low-confidence observation: it never reaches medium or high severity.

Frames after the agent run log ends (perception record after_run_log_end, or run_t > the run's
duration_s) are dropped: the agent had exited, so they say nothing about the run.

Detectors (code -> rule):
  portal_outcome_check   after each *portal* skill_result, look at frames in [t, t+PORTAL_WINDOW_S]:
                         footage success = any frame with obsidian_frame == "complete" or portal_lit.
                         agent ok & footage none   -> contradiction (high)
                         agent fail & footage none -> independent confirmation (low)
                         agent fail & footage success -> contradiction (high)
                         agent ok & footage success -> independent confirmation (low)
                         Frames after the server log's last sample are counted as covering the
                         server-log gap (evidence["frames_in_server_gap"]).
  unlogged_water         frames saying player_in_water with no server sample within WATER_MATCH_S.
  visible_feature_ignored lava visible but never used / ruined portal (partial frame) visible while
                         the agent never started a portal skill. Report-only (decision).

perception.json shape (from splitcheck.perception): either a list of frame records or a dict with
"frames": [...]; each record {video_t, run_t, frame_sha, obs: {...OBS_SCHEMA}, model, prompt_sha}.
Records with run_t None use video_t + perception["run_offset_s"] when that is given, else are skipped.
"""
from __future__ import annotations

import re

CONF_MIN = 0.6
ACC_MIN = 0.8
MIN_N = 10                 # ground-truth labels a field needs before its accuracy may gate a finding
PORTAL_WINDOW_S = 20.0
WATER_MATCH_S = 1.0
GROUP_GAP_S = 5.0          # frames closer than this belong to one sighting/interval
LABEL = "perception-assisted"
PORTAL_SKILL_RE = re.compile(r"portal", re.I)
LAVA_USE_RE = re.compile(r"lava|bucket", re.I)


def _finding(**kw):
    from .detectors_seed import _finding as f
    ev = kw.setdefault("evidence", {})
    ev["perception_assisted"] = True
    ev["label"] = LABEL
    kw["message"] = f"[{LABEL}] " + kw["message"]
    kw["cost_s"] = 0.0
    return f(**kw)


# ---------------------------------------------------------------- inputs
def run_duration(perception):
    if isinstance(perception, dict):
        d = (perception.get("run") or {}).get("run_duration_s")
        return float(d) if isinstance(d, (int, float)) else None
    return None


def frames_of(perception, include_after_end: bool = False) -> list:
    """Normalised frame records sorted by run time: [{t, video_t, frame_sha, obs, model}].
    Frames after the agent run log ended are dropped unless include_after_end."""
    if perception is None:
        return []
    recs = perception.get("frames", []) if isinstance(perception, dict) else list(perception)
    off = perception.get("run_offset_s") if isinstance(perception, dict) else None
    dur = run_duration(perception)
    out = []
    for r in recs:
        t = r.get("run_t")
        if t is None and off is not None and r.get("video_t") is not None:
            t = float(r["video_t"]) + float(off)
        if t is None or not isinstance(r.get("obs"), dict):
            continue
        after = bool(r.get("after_run_log_end")) or (dur is not None and float(t) > dur)
        if after and not include_after_end:
            continue
        out.append({"t": round(float(t), 3), "video_t": r.get("video_t"), "frame_sha": r.get("frame_sha"),
                    "obs": r["obs"], "model": r.get("model")})
    return sorted(out, key=lambda x: (x["t"], x["video_t"] or 0))


def _vrow(validation, field):
    v = ((validation or {}).get("per_field") or {}).get(field)
    if isinstance(v, dict) and isinstance(v.get("accuracy"), (int, float)) and v.get("n"):
        return v
    return None


def _accuracy(validation, field):
    v = _vrow(validation, field)
    return float(v["accuracy"]) if v else None


def _sufficient(v) -> bool:
    return bool(v.get("sufficient", v.get("n", 0) >= MIN_N))


def _gate(frames, fields, validation, conf_min, acc_min):
    """-> (confident_frames, reason or None). reason set means the result is low-confidence."""
    rows = {f: _vrow(validation, f) for f in fields}
    unval = [f for f, v in rows.items() if v is None]
    insuf = {f: v["n"] for f, v in rows.items() if v is not None and not _sufficient(v)}
    bad = {f: float(v["accuracy"]) for f, v in rows.items()
           if v is not None and _sufficient(v) and v["accuracy"] < acc_min}
    conf = [f for f in frames if isinstance(f["obs"].get("confidence"), (int, float))
            and f["obs"]["confidence"] >= conf_min]
    if unval:
        return conf, "unvalidated: no ground truth for " + ", ".join(unval)
    if insuf:
        return conf, (f"insufficient ground truth (n < {MIN_N}) for " + ", ".join(
            f"{k} n={v}" for k, v in sorted(insuf.items())))
    if bad:
        return conf, ("validated accuracy below %s for %s" % (acc_min, ", ".join(
            f"{k}={round(v, 3)}" for k, v in sorted(bad.items()))))
    if not conf:
        return conf, f"no frame with confidence >= {conf_min}"
    return conf, None


def _acc_note(validation, fields):
    parts = []
    for f in fields:
        v = _vrow(validation, f)
        parts.append(f"{f} unvalidated" if v is None else f"{f} accuracy {round(float(v['accuracy']), 3)} "
                                                          f"(n={v['n']})")
    return "; ".join(parts)


def _server_rel_times(agent_tl, server_tl):
    if server_tl is None:
        return None
    a0 = (agent_tl.meta or {}).get("t0_epoch") if agent_tl is not None else None
    s0 = (server_tl.meta or {}).get("t0_epoch")
    shift = (s0 - a0) if (a0 is not None and s0 is not None) else 0.0
    return sorted(round(s.t + shift, 3) for s in server_tl.samples)


def _groups(frames):
    out = []
    for f in frames:
        if out and f["t"] - out[-1][-1]["t"] <= GROUP_GAP_S:
            out[-1].append(f)
        else:
            out.append([f])
    return out


def _ids(frames):
    return [{"run_t": f["t"], "video_t": f["video_t"], "frame_sha": f["frame_sha"]} for f in frames]


def _low(code, t0, t1, lines, what, reason, frames, extra=None, category="claim"):
    ev = {"detector": code, "low_confidence": True, "reason": reason, "frames": _ids(frames)}
    ev.update(extra or {})
    return _finding(code=code, category=category, severity="low", t_start=t0, t_end=t1, lines=lines,
                    message=f"low-confidence observation: {what} ({reason}); not used as evidence",
                    evidence=ev)


# ---------------------------------------------------------------- detectors
def portal_outcome_check(frames, tl, server_tl=None, validation=None, conf_min=CONF_MIN, acc_min=ACC_MIN):
    live = ((tl.meta or {}).get("live_agent") or {}) if tl is not None else {}
    stimes = _server_rel_times(tl, server_tl)
    s_last = stimes[-1] if stimes else None
    fields = ("obsidian_frame", "portal_lit")
    out = []
    for r in live.get("skill_results") or []:
        if not PORTAL_SKILL_RE.search(str(r.get("skill", ""))):
            continue
        t0, t1 = float(r["t"]), float(r["t"]) + PORTAL_WINDOW_S
        win = [f for f in frames if t0 <= f["t"] <= t1]
        claim_ok = bool(r.get("ok"))
        claim = (f"agent log line {r['line']}: {r['skill']} {'succeeded' if claim_ok else 'FAILED'}"
                 + (f" (placed {r['placed']})" if r.get("placed") is not None else "")
                 + (f", error '{r['error']}'" if r.get("error") else ""))
        if not win:
            out.append(_low("portal_outcome_check", t0, t1, [r["line"]], claim,
                            f"no footage frame in t={round(t0, 3)}-{round(t1, 3)} s", [],
                            {"agent_ok": claim_ok, "outcome": "low_confidence"}))
            continue
        conf, reason = _gate(win, fields, validation, conf_min, acc_min)
        if reason:
            out.append(_low("portal_outcome_check", t0, t1, [r["line"]], claim, reason, win,
                            {"agent_ok": claim_ok, "outcome": "low_confidence"}))
            continue
        hits = [f for f in conf if f["obs"].get("obsidian_frame") == "complete" or f["obs"].get("portal_lit") is True]
        seen_ok = bool(hits)
        gap = [f for f in conf if s_last is not None and f["t"] > s_last]
        gap_note = (f"; {len(gap)} of these frames fall after the server log's last sample (t={s_last} s), "
                    f"so footage is the only outside evidence there" if gap else "")
        if server_tl is None:
            gap_note = "; no server log given, footage is the only outside evidence"
        frame_desc = (f"{len(conf)} confident frame(s) in t={round(t0, 3)}-{round(t1, 3)} s "
                      + ("show a complete frame or lit portal" if seen_ok else
                         "show no complete obsidian frame and no lit portal"))
        contradiction = claim_ok != seen_ok
        outcome = "contradiction" if contradiction else "independent_confirmation"
        msg = (f"{'contradiction' if contradiction else 'independent confirmation'}: {claim}; footage: "
               f"{frame_desc} ({_acc_note(validation, fields)}){gap_note}")
        out.append(_finding(code="portal_outcome_check", category="claim",
                            severity="high" if contradiction else "low", t_start=t0, t_end=t1,
                            lines=[r["line"]], message=msg,
                            evidence={"detector": "portal_outcome_check", "outcome": outcome,
                                      "agent_ok": claim_ok, "footage_success": seen_ok,
                                      "frames": _ids(hits or conf), "frames_in_server_gap": _ids(gap),
                                      "server_last_t_s": s_last}))
    return out


def unlogged_water(frames, tl, server_tl=None, validation=None, conf_min=CONF_MIN, acc_min=ACC_MIN):
    stimes = _server_rel_times(tl, server_tl) or []
    wet = [f for f in frames if f["obs"].get("player_in_water") is True]
    unc = [f for f in wet if not any(abs(f["t"] - s) <= WATER_MATCH_S for s in stimes)]
    out = []
    for g in _groups(unc):
        t0, t1 = g[0]["t"], g[-1]["t"]
        what = f"player in water at t={t0}-{t1} s with no server sample within {WATER_MATCH_S} s"
        conf, reason = _gate(g, ("player_in_water",), validation, conf_min, acc_min)
        if reason:
            out.append(_low("unlogged_water", t0, t1, [], what, reason, g))
            continue
        out.append(_finding(code="unlogged_water", category="claim", severity="medium", t_start=t0, t_end=t1,
                            lines=[], message=f"{what}: {len(conf)} confident frame(s) "
                                              f"({_acc_note(validation, ('player_in_water',))}); the logs "
                                              f"cannot confirm or price this, report only",
                            evidence={"detector": "unlogged_water", "frames": _ids(conf), "report_only": True}))
    return out


def visible_feature_ignored(frames, tl, server_tl=None, validation=None, conf_min=CONF_MIN, acc_min=ACC_MIN):
    live = ((tl.meta or {}).get("live_agent") or {}) if tl is not None else {}
    portal_started = [s for s in live.get("skill_starts") or [] if PORTAL_SKILL_RE.search(str(s.get("skill", "")))]
    texts = []
    for s in (tl.samples if tl is not None else []):
        texts.append(" ".join(str(x) for x in (s.action, s.action_desc, s.result) if x))
    for e in (tl.events if tl is not None else []):
        texts.append(str(e))
    lava_used = any(LAVA_USE_RE.search(t) for t in texts)
    checks = []
    if not lava_used:
        checks.append(("lava_visible", lambda o: o.get("lava_visible") is True,
                       "lava visible, but the agent log never mentions lava or a bucket"))
    if not portal_started:
        checks.append(("obsidian_frame", lambda o: o.get("obsidian_frame") in ("partial", "complete"),
                       "obsidian frame (ruined portal) visible, but the agent never started a portal skill"))
    out = []
    for field, pred, what in checks:
        seen = [f for f in frames if pred(f["obs"])]
        if not seen:
            continue
        g = _groups(seen)[0]  # first sighting only
        t0, t1 = g[0]["t"], g[-1]["t"]
        conf, reason = _gate(g, (field,), validation, conf_min, acc_min)
        if reason:
            out.append(_low("visible_feature_ignored", t0, t1, [], f"{what} (t={t0}-{t1} s)", reason, g,
                            {"field": field, "report_only": True}, category="decision"))
            continue
        out.append(_finding(code="visible_feature_ignored", category="decision", severity="low",
                            t_start=t0, t_end=t1, lines=[],
                            message=f"{what}: first seen t={t0}-{t1} s in {len(conf)} confident frame(s) "
                                    f"({_acc_note(validation, (field,))}); report only, seeing a feature on "
                                    f"camera does not mean the agent perceived it",
                            evidence={"detector": "visible_feature_ignored", "field": field,
                                      "frames": _ids(conf), "report_only": True}))
    return out


REGISTRY = {
    "portal_outcome_check": portal_outcome_check,
    "unlogged_water": unlogged_water,
    "visible_feature_ignored": visible_feature_ignored,
}


def detect(perception, tl, server_tl=None, validation=None, conf_min=CONF_MIN, acc_min=ACC_MIN) -> list:
    """Run every perception detector; deterministic order (registry order, then t_start)."""
    frames = frames_of(perception)
    dur = ((tl.meta or {}).get("duration_s") if tl is not None else None)
    if isinstance(dur, (int, float)):
        frames = [f for f in frames if f["t"] <= dur]   # agent had exited: not evidence about the run
    out = []
    for fn in REGISTRY.values():
        out += sorted(fn(frames, tl, server_tl, validation, conf_min, acc_min),
                      key=lambda f: (f.t_start, f.t_end, f.message))
    return out
