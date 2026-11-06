import json
from pathlib import Path

from splitcheck.timeline import Sample, Timeline, load_timeline

FIX = Path(__file__).parent / "fixtures" / "events"


def _write(tmp_path, rows, name="events.jsonl"):
    p = tmp_path / name
    lines = [r if isinstance(r, str) else json.dumps(r) for r in rows]
    p.write_text("\n".join(lines) + "\n")
    return p


def _ts(s):
    return f"2026-11-06T12:00:{s:06.3f}Z"


KNOWN = {"village": {"x": -225, "y": 71, "z": 255},
         "chests": [{"x": -228, "y": 71, "z": 240}, {"x": -290, "y": 68, "z": 253}],
         "entryPortal": {"x": -285, "y": 67, "z": 259, "axis": "x"},
         "exitPortal": {"x": -141, "y": 40, "z": 104},
         "remainingChests": [{"x": -228, "y": 71, "z": 240}], "seed": "839"}


def _state(**kw):
    st = {"stage": "prepare", "position": {"x": 0.5, "y": 64, "z": 0.5}, "dimension": "overworld",
          "health": 20, "food": 18, "inventory": {"bread": 2}, "knownSeed": KNOWN}
    st.update(kw)
    return st


def agent_rows():
    return [
        {"time": _ts(0), "type": "start", "seed": "8398967436125155523", "state": _state()},
        {"time": _ts(1), "type": "decision", "step": 0, "selected": "chest_-228,71,240",
         "request": {"state": json.dumps(_state())}, "response": {}, "latencyMs": 900},
        {"time": _ts(4), "type": "result", "step": 1, "action": "Loot surveyed supply chest",
         "result": "Looted chest", "position": {"x": -228, "y": 71, "z": 241},
         "inventory": {"bread": 3, "obsidian": 10}},
        "{not json",
        {"time": _ts(5), "type": "decision", "step": 1, "selected": "bed_x",
         "request": {"state": json.dumps(_state(stage="entry"))}},
        {"time": _ts(7), "type": "result", "step": 2, "action": "Collect bed",
         "result": "FAILED Path stopped before target", "position": {"x": -230, "y": 71, "z": 241},
         "inventory": {"bread": 3, "obsidian": 10}},
        {"time": _ts(8), "type": "position_sample", "position": {"x": -139, "y": 41, "z": 98},
         "dimension": "the_nether"},
        {"time": _ts(8.1), "type": "nether_entered", "position": {"x": -139, "y": 41, "z": 98}},
        {"time": _ts(20), "type": "position_sample", "position": {"x": 0, "y": 60, "z": 0},
         "dimension": "minecraft:the_end"},
        {"time": _ts(30), "type": "dragon_killed", "source": "x"},
        {"time": _ts(31), "type": "game_won", "dragonKilled": True},
    ]


def test_agent_timeline(tmp_path):
    tl = load_timeline(_write(tmp_path, agent_rows()))
    assert isinstance(tl, Timeline) and tl.source == "agent"
    assert tl.meta["malformed_lines"] == 1 and tl.meta["malformed_line_numbers"] == [4]
    res = [s for s in tl.samples if s.kind == "result"]
    assert [s.action for s in res] == ["chest_-228,71,240", "bed_x"]
    assert [s.action_failed for s in res] == [False, True]
    assert res[0].action_desc == "Loot surveyed supply chest"
    assert res[1].stage == "entry" and res[0].inv == {"bread": 3, "obsidian": 10}
    assert res[0].t == 4.0 and res[0].line == 3 and res[0].pos == (-228.0, 71.0, 241.0)
    dec = [s for s in tl.samples if s.kind == "decision"][0]
    assert dec.food == 18 and dec.health == 20 and dec.stage == "prepare" and dec.in_water is None
    types = [e["type"] for e in tl.events]
    assert types == ["start", "nether_entered", "end_entered", "dragon_killed", "game_won"]
    end = [e for e in tl.events if e["type"] == "end_entered"][0]
    assert end["derived"] == "dimension_change" and end["line"] == 9 and end["t"] == 20.0
    # knowledge from knownSeed, normalized; remainingChests and non-points dropped
    k = tl.knowledge
    assert k["village"] == {"x": -225.0, "y": 71.0, "z": 255.0, "dim": "overworld"}
    assert k["chests_1"]["z"] == 253.0 and k["exitPortal"]["dim"] == "the_nether"
    assert k["entryPortal"]["axis"] == "x"
    assert "seed" not in k and not any(n.startswith("remaining") for n in k)


def test_deterministic(tmp_path):
    p = _write(tmp_path, agent_rows())
    a, b = load_timeline(p), load_timeline(p)
    assert a == b


def poller_rows():
    def ps(t, pos, dim="overworld", feet="air", head="air", **kw):
        r = {"time": _ts(t), "type": "position_sample", "player": "anshul", "position": pos,
             "dimension": dim, "inventory": {"oak_log": 3}, "health": 20.0,
             "feet_block": feet, "head_block": head}
        r.update(kw)
        return r
    return [
        {"time": _ts(0), "type": "start", "player": "anshul", "seed": "s", "source": "rcon_poller", "hz": 2},
        ps(0.5, [1.0, 64.0, 2.0]),
        ps(1.0, [1.0, 62.0, 2.0], feet="water", head="minecraft:water"),
        ps(1.5, [1.0, 11.0, 2.0], feet="lava", head="air"),
        "",
        "garbage",
        ps(2.0, [5.0, 70.0, 5.0], dim="the_nether"),
        {"time": _ts(2.0), "type": "nether_entered", "position": [5.0, 70.0, 5.0]},
        {"time": _ts(3.0), "type": "position_sample", "player": "anshul", "position": [0, 60, 0],
         "dimension": "the_end", "inventory": {}, "health": 20.0},
        {"time": _ts(3.0), "type": "end_entered", "position": [0, 60, 0]},
        {"time": _ts(4.0), "type": "death_suspected", "note": "x"},
        {"time": _ts(5.0), "type": "stop"},
    ]


def test_poller_timeline(tmp_path):
    tl = load_timeline(_write(tmp_path, poller_rows()))
    assert tl.source == "human_poller"
    assert tl.meta["malformed_lines"] == 1
    s = tl.samples
    assert [x.in_water for x in s[:4]] == [False, True, False, False]
    assert [x.in_lava for x in s[:4]] == [False, False, True, False]
    assert s[4].in_water is None and s[4].in_lava is None   # no block fields
    assert s[0].pos == (1.0, 64.0, 2.0) and s[0].inv == {"oak_log": 3} and s[0].t == 0.5
    assert s[0].action is None and s[0].food is None
    types = [e["type"] for e in tl.events]
    assert types == ["start", "nether_entered", "end_entered", "death_suspected", "stop"]
    assert all("derived" not in e for e in tl.events)       # explicit events not duplicated
    assert tl.knowledge == {}


def test_poller_route_sheet(tmp_path):
    sheet = tmp_path / "sheet.json"
    sheet.write_text(json.dumps({"entry_portal": {"x": 1, "y": 2, "z": 3},
                                 "bastion": {"x": 9, "y": 40, "z": 9, "dim": "nether"}}))
    tl = load_timeline(_write(tmp_path, poller_rows()), route_sheet=sheet)
    assert tl.knowledge["entry_portal"]["dim"] == "overworld"
    assert tl.knowledge["bastion"]["dim"] == "the_nether"
    assert tl.meta["knowledge_source"] == "route_sheet"


def test_existing_fixtures_load():
    for p in sorted(FIX.glob("*.jsonl")):
        tl = load_timeline(p)
        assert tl.source == "agent" and tl.samples and tl.events[0]["type"] == "start"
        assert all(isinstance(s, Sample) for s in tl.samples)
        assert [s.t for s in tl.samples] == sorted(s.t for s in tl.samples)
