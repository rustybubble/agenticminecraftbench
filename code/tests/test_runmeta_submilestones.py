"""runmeta (RUN_NOTES facts, fairness applicability) and submilestones (progress before failure)."""
import json
from pathlib import Path

import pytest

from splitcheck import evaluate, runmeta, submilestones, timeline

ROOT = Path(__file__).resolve().parents[2]
A01 = ROOT / "agent_runs" / "agent-01"
RULES = json.loads((ROOT / "baseline" / "rules.json").read_text())

NOTES = """# RUN demo-02 — live agent, seed 1

- **RUN_ID:** demo-02
- **Planner model:** `some-model` (effort low)
- **Server:** Minecraft 1.16.5, **difficulty peaceful**
- **First attempt?** Yes.
- **Interventions during the run:** one restart at t=30 s.
- **Outcome:** reached the Nether.
  Then died.
"""


def test_parse_synthetic_notes(tmp_path):
    p = tmp_path / "RUN_NOTES.md"
    p.write_text(NOTES)
    f = runmeta.parse_run_notes(p)
    assert f["run_id"] == "demo-02" and f["agent"] == "live agent" and f["live"]
    assert f["planner_model"] == "some-model"
    assert f["difficulty"] == "peaceful"
    assert f["first_attempt"] == "Yes." and f["first_attempt_world"]
    assert not f["interventions_none"]
    assert f["outcome"] == "reached the Nether. Then died."
    na = runmeta.fairness_applicability(RULES["fairness"], f, reached={"start", "nether_entered"})
    assert "difficulty" not in na  # Peaceful matches the rules
    assert "never reached the End" in na["rng"]
    na_end = runmeta.fairness_applicability(RULES["fairness"], f, reached={"end_entered"})
    assert "never reached the End" not in na_end.get("rng", "")
    assert "brackets" in na  # live run, not the montage


def test_missing_notes_is_empty():
    assert runmeta.parse_run_notes(None) == {}
    assert runmeta.parse_run_notes("/nonexistent/RUN_NOTES.md") == {}
    assert runmeta.fairness_applicability(RULES["fairness"], {}) == {}
    assert runmeta.this_run_lines({}) == []


@pytest.mark.skipif(not (A01 / "RUN_NOTES.md").exists(), reason="agent-01 not present")
def test_agent01_facts_and_contradictions():
    f = runmeta.parse_run_notes(A01 / "RUN_NOTES.md")
    assert f["run_id"] == "agent-01" and f["difficulty"] == "easy" and f["interventions_none"]
    assert f["planner_model"] == "deepseek-flash"
    assert "placed 0 verified blocks" in f["outcome"]
    na = runmeta.fairness_applicability(RULES["fairness"], f, reached={"start"})
    assert "Easy" in na["difficulty"]
    assert {"practice", "brackets", "rng"} <= set(na)
    assert "timer" not in na  # still wall clock vs IGT


def test_pro_steps_from_playbook():
    pro = submilestones.load_pro_steps()
    assert pro["nether_entered"]["lo"] == pytest.approx(66.7)  # runner's comment says 66.683
    assert pro["chest:village"] == {**pro["chest:village"], "lo": 29.0, "hi": 33.0}
    assert pro["flint_and_steel"]["lo"] == 60.0
    assert submilestones.load_pro_steps("/nonexistent.md") == {}


def test_missing_pro_time_wording():
    rows = submilestones.compare_to_pro({"chest_1": {"t": 5.0, "line": 3, "reached": True,
                                                     "identity": "village", "note": ""}}, pro={})
    md = "\n".join(submilestones.progress_lines(rows, None))
    assert "no pro time for this step" in md


@pytest.mark.skipif(not (A01 / "events.jsonl").exists(), reason="agent-01 not present")
def test_agent01_progress():
    tl = timeline.load_timeline(A01 / "events.jsonl")
    steps = submilestones.derive_steps(tl)
    assert [steps[f"chest_{i}"]["identity"] for i in (1, 2, 3)] == ["village", "obsidian", "flint"]
    assert [steps[f"chest_{i}"]["line"] for i in (1, 2, 3)] == [8, 14, 20]
    assert steps["flint_and_steel"]["line"] == 30 and steps["flint_and_steel"]["t_lo"] < steps["flint_and_steel"]["t"]
    assert steps["portal_build_attempted"]["line"] == 26
    assert steps["portal_built"]["reached"] is False and steps["portal_built"]["line"] == 27
    fail = submilestones.failure_point(steps)
    assert fail["step"] == "portal_built" and fail["line"] == 27
    lines, data = submilestones.progress_section(tl)
    md = "\n".join(lines)
    assert "## Progress before failure" in md and "run failed at: portal_built (line 27)" in md
    row = {r["step"]: r for r in data["steps"]}
    assert row["nether_entered"]["agent_t"] is None and row["nether_entered"]["pro_lo"] == pytest.approx(66.7)
    assert row["chest_1"]["delta_lo"] == pytest.approx(row["chest_1"]["agent_t"] - 33.0)


@pytest.mark.skipif(not (A01 / "events.jsonl").exists(), reason="agent-01 not present")
def test_evaluate_report_sections(tmp_path):
    res = evaluate.evaluate(A01 / "events.jsonl", outdir=tmp_path, write=False)
    md = res["texts"]["report.md"]
    assert md.index("## This run") < md.index("## Fairness notes")
    assert "does not apply to this run: the rules say the agent played on Peaceful" in md
    assert "## Progress before failure" in md and "run failed at: portal_built (line 27)" in md
    # headline verdicts unchanged with and without run notes
    res2 = evaluate.evaluate(A01 / "events.jsonl", outdir=tmp_path, write=False, run_notes=False)
    assert res2["texts"]["efficiency.json"] == res["texts"]["efficiency.json"]
    assert "## This run" not in res2["texts"]["report.md"]
    # deterministic
    res3 = evaluate.evaluate(A01 / "events.jsonl", outdir=tmp_path, write=False)
    assert res3["texts"] == res["texts"]
