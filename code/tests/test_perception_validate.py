import json
from pathlib import Path

import pytest

from splitcheck import perception_validate as pv
from splitcheck.timeline import Sample, Timeline

ROOT = Path(__file__).resolve().parents[2]
RUN = ROOT / "agent_runs" / "agent-01" / "events.jsonl"
SRV = ROOT / "agent_runs" / "agent-01" / "server_events.jsonl"

FEATS = {
    "supply_chests": [{"x": 0, "y": 64, "z": 0}],
    "village": {"x": 100, "y": 64, "z": 0},
    "entry_portal": {"x": 0, "y": 64, "z": 100, "existing_frame_obsidian": [(0, 63, 100)]},
}


def obs(**kw):
    base = {"obsidian_frame": "none", "portal_lit": False, "chest_visible": False, "village_visible": False,
            "lava_visible": False, "water_visible": False, "player_visible": True, "player_in_water": None,
            "player_activity": "walking", "confidence": 0.9}
    base.update(kw)
    return base


def tl(samples, results=(), t0=1000.0):
    return Timeline(source="live_agent", samples=samples, events=[],
                    meta={"t0_epoch": t0, "live_agent": {"skill_results": list(results)}})


def S(t, pos, line=1, **kw):
    return Sample(t=t, line=line, pos=pos, dim="overworld", **kw)


def test_labels_pure_near_far_bands():
    ps = {"built": False, "lit": False}
    near = pv.labels_for(0, (3, 64, 0), FEATS, ps, None)
    assert near["chest_visible"][0] == [True]
    assert near["obsidian_frame"][0] == ["none"]  # 100 blocks from portal
    assert near["portal_lit"][0] == [False]
    assert "village_visible" not in near  # far from center: no label (village extent unknown)
    mid = pv.labels_for(0, (12, 64, 0), FEATS, ps, None)
    assert "chest_visible" not in mid  # ambiguous band 8..16
    port = pv.labels_for(0, (0, 64, 95), FEATS, ps, None)
    assert port["obsidian_frame"][0] == ["partial"]
    unk = pv.labels_for(0, None, FEATS, ps, None)
    assert unk["obsidian_frame"][0] == ["none", "partial"]
    assert set(unk) == {"obsidian_frame", "portal_lit"}
    built = pv.labels_for(0, (0, 64, 95), FEATS, {"built": True, "lit": True}, None)
    assert built["obsidian_frame"][0] == ["partial", "complete"] and "portal_lit" not in built


def test_village_far_has_no_false_label():
    # regression: one center point cannot say "no village visible" (houses seen 60 blocks away)
    lab = pv.labels_for(0, (3, 64, 0), FEATS, {"built": False, "lit": False}, None)
    assert "village_visible" not in lab
    lab = pv.labels_for(0, (90, 64, 0), FEATS, {"built": False, "lit": False}, None)
    assert lab["village_visible"][0] == [True]


def test_validate_synthetic_scores_and_unvalidated():
    agent = tl([S(0, (0, 64, 0), 1), S(10, (0.5, 64, 0), 2), S(20, (0, 64, 96), 3), S(30, (0, 64, 97), 4)],
               results=[{"skill": "build_portal", "t": 25, "ok": False, "placed": 0, "line": 4}])
    perc = [
        {"video_t": 0, "run_t": 5, "obs": obs(chest_visible=True)},                     # stationary 0..10
        {"video_t": 1, "run_t": 15, "obs": obs(chest_visible=True)},                    # unknown pos
        {"video_t": 2, "run_t": 25, "obs": obs(obsidian_frame="complete", portal_lit=True)},  # wrong x2
        {"video_t": 3, "run_t": 30, "obs": obs(obsidian_frame="partial")},
        {"video_t": 4, "run_t": None, "obs": obs()},
    ]
    r = pv.validate(perc, agent, None, FEATS)
    pf = r["per_field"]
    assert {k: pf["chest_visible"][k] for k in ("n", "correct", "accuracy", "sufficient")} == \
        {"n": 3, "correct": 3, "accuracy": 1.0, "sufficient": False}
    assert pf["chest_visible"]["ci95"][1] == 1.0 and pf["chest_visible"]["ci95"][0] < 0.5
    # regression: log-derived labels (portal_lit, "never complete") are circular -> not ground truth
    assert pf["portal_lit"]["n"] == 0
    assert r["log_consistency"]["portal_lit"] == {"n": 4, "consistent": 3, "source": "agent log claim"}
    of = [c for c in r["cases"] if c["field"] == "obsidian_frame"]
    assert [c["correct"] for c in of] == [True, False, True]   # position-based only (t=5, 25, 30)
    assert pf["obsidian_frame"]["n"] == 3
    assert pf["player_in_water"]["n"] == 0 and pf["player_in_water"]["accuracy"] is None
    assert "player_in_water" in r["unvalidated_fields"] and "lava_visible" in r["unvalidated_fields"]
    assert r["validated_fields"] == [] and "chest_visible" in r["insufficient_fields"]
    assert any("skipped" in n for n in r["notes"])


def test_server_alignment_and_water(tmp_path):
    p = tmp_path / "srv.jsonl"
    rows = [{"t": 0, "feet_block": "water", "eye_block": "other"}, {"t": 1, "feet_block": "other", "eye_block": "other"}]
    p.write_text("\n".join(json.dumps(x) for x in rows) + "\n")
    # server clock starts 2 s before the agent clock
    server = Timeline(source="poller", samples=[S(5.0, (0, 64, 0), 1), S(8.0, (0, 64, 0), 2)], events=[],
                      meta={"t0_epoch": 998.0, "path": str(p)})
    agent = tl([S(0, (50, 64, 50), 1)])
    perc = [{"run_t": 3.2, "obs": obs(player_in_water=True, chest_visible=True)},
            {"run_t": 6.0, "obs": obs(player_in_water=True)},
            {"run_t": 4.5, "obs": obs(player_in_water=None)}]
    r = pv.validate(perc, agent, server, FEATS)
    w = [c for c in r["cases"] if c["field"] == "player_in_water"]
    assert [(c["run_t"], c["expected"], c["correct"]) for c in w] == [(3.2, [True], True), (6.0, [False], False)]
    cv = [c for c in r["cases"] if c["field"] == "chest_visible"]
    assert cv[0]["expected"] == [True] and "server line 1" in cv[0]["position_basis"]


def test_accepts_dict_container_and_format():
    agent = tl([S(0, (0, 64, 0))])
    r = pv.validate({"model": "fake", "observations": [{"run_t": 0, "obs": obs(chest_visible=True)}]},
                    agent, None, FEATS)
    assert r["per_field"]["chest_visible"]["accuracy"] == 1.0
    txt = pv.format_table(r)
    assert "| chest_visible | 1 | 1 | 100% (insufficient, n<10) |" in txt and "Unvalidated" in txt


@pytest.mark.skipif(not (RUN.exists() and SRV.exists()), reason="agent-01 logs not present")
def test_agent01_real_logs(tmp_path, capsys):
    perc = [{"video_t": t, "run_t": t, "obs": obs(chest_visible=t in (16, 38), obsidian_frame="partial",
                                                   player_in_water=False)}
            for t in (5, 16, 38, 46, 60, 80)]
    pj = tmp_path / "perception.json"
    pj.write_text(json.dumps({"observations": perc}))
    from splitcheck.seedfeatures import load_seed_features
    feats = load_seed_features()
    r = pv.validate(str(pj), str(RUN), str(SRV), feats)
    pf = r["per_field"]
    assert pf["portal_lit"]["n"] == 0  # never lit, but that label is the agent's claim (circular)
    assert r["log_consistency"]["portal_lit"]["n"] == 6 and r["log_consistency"]["portal_lit"]["consistent"] == 6
    of = {c["run_t"]: c for c in r["cases"] + r["log_cases"] if c["field"] == "obsidian_frame"}
    assert of[46]["expected"] == ["partial"] and of[46]["correct"]   # at the ruined frame
    assert of[60]["correct"]                                         # lingering by the frame (agent stationary)
    assert pf["player_in_water"]["n"] >= 1                          # server covers t <= ~44 s
    assert all(c["expected"] == [False] for c in r["cases"] if c["field"] == "player_in_water")
    assert pv.main([str(pj), "--run-log", str(RUN), "--server-log", str(SRV)]) == 0
    assert "Consistent with agent-log claim (not ground truth): portal_lit 6/6" in capsys.readouterr().out
