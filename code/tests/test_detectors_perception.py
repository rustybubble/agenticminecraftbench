"""Perception-assisted detectors on a synthetic perception.json over an agent-01-like timeline."""
from types import SimpleNamespace

from splitcheck import detectors_perception as dp


def _obs(**kw):
    o = {"obsidian_frame": "none", "portal_lit": False, "chest_visible": False, "village_visible": False,
         "lava_visible": False, "water_visible": False, "player_visible": True, "player_in_water": False,
         "player_activity": "walking", "confidence": 0.9}
    o.update(kw)
    return o


def _perc(frames):
    return {"model": "fake", "frames": [{"video_t": t, "run_t": t, "frame_sha": f"sha{i}", "obs": o,
                                         "model": "fake", "prompt_sha": "p"} for i, (t, o) in enumerate(frames)]}


def _tl(ok=False, starts=(("build_portal", 44.101, 26),), events=()):
    res = [{"line": 27, "t": 48.045, "skill": "build_portal", "ok": ok, "placed": 0 if not ok else 14,
            "error": None if ok else "frame incomplete"}]
    live = {"skill_results": res, "skill_starts": [{"skill": s, "t": t, "line": ln} for s, t, ln in starts]}
    return SimpleNamespace(meta={"live_agent": live, "t0_epoch": 1000.0}, samples=[], events=list(events))


def _server(last_t):
    samples = [SimpleNamespace(t=float(t)) for t in range(4, int(last_t) + 1)]
    return SimpleNamespace(meta={"t0_epoch": 1000.0}, samples=samples)


def _good(*fields, n=20, acc=0.95):
    return {"per_field": {f: {"n": n, "correct": int(n * acc), "accuracy": acc, "sufficient": n >= 10}
                          for f in fields}}


GOOD = _good("obsidian_frame", "portal_lit", "player_in_water", "lava_visible")

FRAMES = [(46.0, _obs(obsidian_frame="partial")), (50.0, _obs(obsidian_frame="partial")),
          (54.0, _obs(obsidian_frame="partial")), (60.0, _obs())]


def _portal(fs):
    return [f for f in fs if f.code == "portal_outcome_check"]


def test_independent_confirmation_when_agent_fails_and_frames_show_no_complete_frame():
    fs = _portal(dp.detect(_perc(FRAMES), _tl(ok=False), server_tl=_server(44), validation=GOOD))
    assert len(fs) == 1
    f = fs[0]
    assert f.evidence["outcome"] == "independent_confirmation"
    assert f.category == "claim" and f.severity == "low" and f.cost_s == 0.0
    assert f.evidence["perception_assisted"] and f.message.startswith("[perception-assisted]")
    assert f.lines == [27]
    assert len(f.evidence["frames_in_server_gap"]) == 3  # frames in [48.045, 68.045], all after server t=44


def test_contradiction_when_agent_claims_success_but_frames_show_none():
    f = _portal(dp.detect(_perc(FRAMES), _tl(ok=True), validation=GOOD))[0]
    assert f.evidence["outcome"] == "contradiction" and f.severity == "high"
    assert f.cost_s == 0.0


def test_contradiction_when_agent_fails_but_footage_shows_lit_portal():
    fr = FRAMES + [(52.0, _obs(obsidian_frame="complete", portal_lit=True))]
    f = _portal(dp.detect(_perc(fr), _tl(ok=False), validation=GOOD))[0]
    assert f.evidence["outcome"] == "contradiction" and f.evidence["footage_success"]


def test_low_confidence_frames():
    fr = [(t, dict(o, confidence=0.3)) for t, o in FRAMES]
    f = _portal(dp.detect(_perc(fr), _tl(ok=True)))[0]
    assert f.evidence["outcome"] == "low_confidence" and f.severity == "low"
    assert "low-confidence observation" in f.message


def test_low_accuracy_field_downgrades_to_low_confidence():
    val = {"per_field": {"obsidian_frame": {"n": 10, "correct": 5, "accuracy": 0.5},
                         "portal_lit": GOOD["per_field"]["portal_lit"]}}
    f = _portal(dp.detect(_perc(FRAMES), _tl(ok=True), validation=val))[0]
    assert f.evidence["outcome"] == "low_confidence"
    assert "obsidian_frame=0.5" in f.evidence["reason"]
    good = {"per_field": {"obsidian_frame": {"n": 10, "correct": 9, "accuracy": 0.9},
                          "portal_lit": GOOD["per_field"]["portal_lit"]}}
    f = _portal(dp.detect(_perc(FRAMES), _tl(ok=True), validation=good))[0]
    assert f.evidence["outcome"] == "contradiction" and "accuracy 0.9" in f.message


def test_no_frames_in_window_is_low_confidence():
    f = _portal(dp.detect(_perc([(10.0, _obs())]), _tl(ok=False)))[0]
    assert f.evidence["outcome"] == "low_confidence"


def test_unlogged_water_only_outside_server_coverage():
    fr = [(30.0, _obs(player_in_water=True)), (60.0, _obs(player_in_water=True)),
          (62.0, _obs(player_in_water=True))]
    fs = [f for f in dp.detect(_perc(fr), _tl(), server_tl=_server(44), validation=GOOD)
          if f.code == "unlogged_water"]
    assert len(fs) == 1 and fs[0].t_start == 60.0 and fs[0].t_end == 62.0 and fs[0].cost_s == 0.0
    assert fs[0].severity == "medium"


def test_unvalidated_or_insufficient_field_never_above_low():
    # regression: unlogged_water on an unvalidated field used to be emitted at medium severity
    fr = [(60.0, _obs(player_in_water=True)), (62.0, _obs(player_in_water=True))]
    for val in (None, {"per_field": {}}, _good("player_in_water", n=2, acc=1.0)):
        fs = [f for f in dp.detect(_perc(fr), _tl(), server_tl=_server(44), validation=val)
              if f.code == "unlogged_water"]
        assert len(fs) == 1 and fs[0].severity == "low" and fs[0].evidence["low_confidence"]
    # regression: n=2 accuracy 1.0 must not back an "independent confirmation"
    f = _portal(dp.detect(_perc(FRAMES), _tl(ok=False), validation=_good("obsidian_frame", "portal_lit", n=2,
                                                                          acc=1.0)))[0]
    assert f.evidence["outcome"] == "low_confidence" and "insufficient" in f.evidence["reason"]


def test_frames_after_run_log_end_are_dropped():
    # regression: footage after the agent exited produced an "unlogged_water" finding
    perc = _perc([(60.0, _obs(player_in_water=True)), (90.0, _obs(player_in_water=True))])
    perc["frames"][1]["after_run_log_end"] = True
    assert [f["t"] for f in dp.frames_of(perc)] == [60.0]
    assert len(dp.frames_of(perc, include_after_end=True)) == 2
    tl = _tl()
    tl.meta["duration_s"] = 83.267
    perc2 = _perc([(90.0, _obs(player_in_water=True)), (95.0, _obs(player_in_water=True))])
    assert [f for f in dp.detect(perc2, tl, server_tl=_server(44), validation=GOOD)
            if f.code == "unlogged_water"] == []


def test_visible_feature_ignored_report_only():
    fr = [(20.0, _obs(lava_visible=True)), (22.0, _obs(lava_visible=True)), (40.0, _obs(obsidian_frame="partial"))]
    fs = [f for f in dp.detect(_perc(fr), _tl(starts=()), validation=GOOD) if f.code == "visible_feature_ignored"]
    assert {f.evidence["field"] for f in fs} == {"lava_visible", "obsidian_frame"}
    assert all(f.category == "decision" and f.cost_s == 0.0 and f.evidence["report_only"] for f in fs)
    # agent did start a portal skill -> ruined portal not "ignored"
    fs = [f for f in dp.detect(_perc(fr), _tl(), validation=GOOD) if f.code == "visible_feature_ignored"]
    assert {f.evidence["field"] for f in fs} == {"lava_visible"}


def test_deterministic_and_run_offset():
    p = _perc(FRAMES)
    a = [f.message for f in dp.detect(p, _tl())]
    assert a == [f.message for f in dp.detect(p, _tl())]
    p2 = {"run_offset_s": 40.0, "frames": [{"video_t": 6.0, "run_t": None, "obs": _obs()}]}
    assert dp.frames_of(p2)[0]["t"] == 46.0


def test_evaluate_perception_section_keeps_headline(tmp_path):
    import json
    from pathlib import Path

    import pytest

    from splitcheck import evaluate as ev
    run = Path(ev.ROOT) / "agent_runs" / "agent-01"
    if not (run / "events.jsonl").exists():
        pytest.skip("agent-01 logs not present")
    perc = _perc([(float(t), _obs(obsidian_frame="partial" if t >= 44 else "none")) for t in range(2, 84, 2)])
    p = tmp_path / "perception.json"
    p.write_text(json.dumps(perc))
    kw = dict(server_log=str(run / "server_events.jsonl"), write=False, outdir=str(tmp_path))
    base = ev.evaluate(str(run / "events.jsonl"), **kw)
    withp = ev.evaluate(str(run / "events.jsonl"), perception=str(p), **kw)
    for name in ("efficiency.json", "timeline.json"):
        assert base["texts"][name] == withp["texts"][name]
    assert "## Perception" not in base["texts"]["report.md"]
    md = withp["texts"]["report.md"]
    # portal_lit has no non-circular ground truth -> no "independent confirmation" is claimed
    assert "## Perception (AI-assisted, validated)" in md and "independent confirmation:" not in md
    assert "| portal_lit | 0 |" in md
    assert "With vs without perception" in md and "Cache hits" not in md
    assert "Consistent with the agent-log claim" in md
    pf = withp["runeval"]["perception"]["findings"]
    assert [f["evidence"]["outcome"] for f in pf if f["code"] == "portal_outcome_check"] == ["low_confidence"]
    assert "cache_hits" not in withp["runeval"]["perception"]
