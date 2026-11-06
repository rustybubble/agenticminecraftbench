"""End-to-end tests for splitcheck.evaluate: log -> timeline/efficiency/runeval/report, deterministic."""
import json
from pathlib import Path

import pytest

from splitcheck import evaluate as ev

EVENTS = Path(__file__).parent / "fixtures" / "events"
LOGS = [EVENTS / "clean_run.jsonl", EVENTS / "wasteful_run.jsonl"]
SEGMENTS = ["spawn_to_nether", "nether", "exit_to_end_portal", "end"]
TAGS = {"extra_items", "longer_path", "failed_or_retried_action", "idle_wait",
        "unnecessary_risk", "wrong_order", "missed_shortcut"}


def _read_all(d: Path) -> dict:
    return {n: (d / n).read_bytes() for n in ev.OUTPUTS}


@pytest.mark.parametrize("log", LOGS, ids=lambda p: p.stem)
def test_end_to_end_outputs_and_determinism(log, tmp_path):
    a, b = tmp_path / "a", tmp_path / "b"
    assert ev.main([str(log), "--run-id", log.stem, "--outdir", str(a)]) == 0
    for n in ev.OUTPUTS:
        assert (a / n).is_file() and (a / n).stat().st_size > 0, n
    first = _read_all(a)
    # rerun into the same folder and into a fresh one: byte-identical
    assert ev.main([str(log), "--run-id", log.stem, "--outdir", str(a)]) == 0
    assert ev.main([str(log), "--run-id", log.stem, "--outdir", str(b)]) == 0
    assert _read_all(a) == first
    assert _read_all(b) == first

    tl = json.loads(first["timeline.json"])
    assert tl["kind"] == "agent_timeline" and tl["run_id"] == log.stem
    for m in ("M_start", "M_portal_in", "M_portal_out", "M_end_in", "M_finish"):
        assert m in tl["milestones"]

    eff = json.loads(first["efficiency.json"])
    assert list(eff)[:3] == ["run_median_ratio", "total", "segments"]
    assert set(eff) <= {"run_median_ratio", "total", "segments", "flags"}  # flags only when unfinished
    rows = [s for s in eff["segments"] if "verdict" in s]
    assert [s["segment"] for s in rows] == SEGMENTS
    for s in rows:
        assert s["verdict"] in ("OK", "SLOW", "FLAG", "NOT_REACHED")
        for w in s["waste"]:
            assert w["tag"] in TAGS
    for s in eff["segments"]:
        for w in s["waste"]:
            assert w["tag"] in TAGS

    rep = json.loads(first["runeval.json"])
    assert "findings" in rep and "score" in rep

    md = first["report.md"].decode("utf-8")
    assert "| Segment |" in md and "## Fairness notes" in md
    for seg in SEGMENTS:
        assert seg in md


def test_wasteful_run_waste_carries_runeval_codes(tmp_path):
    res = ev.evaluate(LOGS[1], run_id="wasteful", outdir=tmp_path)
    codes = {f["code"] for f in res["runeval"]["findings"]}
    assert codes, "fixture should produce RunEval findings"
    evid = " ".join(str(w.get("evidence")) for s in res["efficiency"]["segments"] for w in s["waste"])
    assert any(c in evid for c in codes), "RunEval codes should appear in waste evidence"
    md = res["texts"]["report.md"]
    assert any(c in md for c in codes)


def test_verdicts_unchanged_by_waste_extra(tmp_path):
    res = ev.evaluate(LOGS[1], run_id="wasteful", outdir=tmp_path, write=False)
    from splitcheck import effcheck
    tl = dict(res["timeline"])
    tl.pop("waste_extra", None)
    bare = effcheck.check(tl, effcheck.load_baseline(str(ev.DEFAULT_BASELINE)), effcheck.load_rules())
    v = lambda e: [(s["segment"], s.get("verdict")) for s in e["segments"] if "verdict" in s]
    assert v(bare) == v(res["efficiency"])


def test_default_run_id():
    assert ev.default_run_id("x/agent_runs/run7/events.jsonl") == "run7"
    assert ev.default_run_id("x/wasteful_run.jsonl") == "wasteful_run"
