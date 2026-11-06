"""Seed features for Minecraft Java 1.16.5 seed 8398967436125155523.

Deterministic, stdlib-only loader over the survey JSONs copied from
rmalde/minecraft-agent (see data/seed_8398967436125155523/PROVENANCE.md).

load_seed_features(seed_dir=None) -> dict of named features. Every feature
(and every list item) carries a "source" string "file#key" (or a doc line)
so detectors can cite where a fact came from.

Dimensions use the game ids: "overworld", "the_nether", "the_end".
"""
from __future__ import annotations

import json
import os
from pathlib import Path

SEED = "8398967436125155523"
DEFAULT_SEED_DIR = Path(__file__).resolve().parents[2] / "data" / f"seed_{SEED}"
REF = "rmalde/minecraft-agent@78b40ed optimization/nether/REVIEW.md"

# agent knownSeed key -> feature name here
KNOWNSEED_ALIASES = {
    "village": "village",
    "chests": "supply_chests",
    "entryPortal": "entry_portal",
    "exitPortal": "exit_portal",
    "netherRoute": "nether_route",
    "endPortal": "end_portal",
    "activePortal": "end_portal",
    "preparationBeds": "beds",
}


def _load(d: Path, name: str):
    with open(d / name, encoding="utf-8") as f:
        return json.load(f)


def _item(name: str) -> str:
    return name.split(":", 1)[1] if name.startswith("minecraft:") else name


def _contents(items) -> dict:
    out: dict = {}
    for it in items:
        k = _item(it["name"])
        out[k] = out.get(k, 0) + int(it.get("count", 1))
    return dict(sorted(out.items()))


def _xyz(p) -> tuple:
    return (int(p["x"]), int(p["y"]), int(p["z"]))


def _pt(p, dim, source, **extra) -> dict:
    d = {"x": p["x"], "y": p["y"], "z": p["z"], "dim": dim, "source": source}
    d.update(extra)
    return d


def _center(blocks) -> dict:
    n = len(blocks)
    return {k: round(sum(b[k] for b in blocks) / n, 1) for k in ("x", "y", "z")}


def load_seed_features(seed_dir=None) -> dict:
    d = Path(seed_dir) if seed_dir else Path(os.environ.get("SPLITCHECK_SEED_DIR", DEFAULT_SEED_DIR))
    cfg = _load(d, "config.json")
    loot = {_xyz(c["position"]): (c, "portal-loot.json") for c in _load(d, "portal-loot.json")}
    for c in _load(d, "chest-survey.json"):
        loot.setdefault(_xyz(c["position"]), (c, "chest-survey.json"))
    portal_sv = _load(d, "portal-survey.json")
    spawn_sv = _load(d, "spawn-survey.json")
    sh_sv = _load(d, "stronghold-survey.json")
    entry_link = _load(d, "entry-link.json")
    exit_link = _load(d, "exit-link.json")

    f: dict = {"seed": cfg["seed"], "version": cfg["version"], "difficulty": cfg["difficulty"]}

    f["village"] = _pt(cfg["village"], "overworld", "config.json#village")

    # Supply chests = the ones the route uses (config.chests), with surveyed contents.
    supply_keys = {_xyz(c) for c in cfg["chests"]}
    chests = []
    for key in sorted(loot):
        c, fname = loot[key]
        chests.append(_pt(c["position"], "overworld", f"{fname}#position={list(key)}",
                          contents=_contents(c["items"]), supply=key in supply_keys))
    f["chests"] = chests
    f["supply_chests"] = [c for c in chests if c["supply"]]
    missing = supply_keys - {_xyz(c) for c in f["supply_chests"]}
    for key in sorted(missing):  # config chest without surveyed contents
        f["supply_chests"].append(_pt(dict(zip("xyz", key)), "overworld", "config.json#chests",
                                      contents={}, supply=True))
    tot: dict = {}
    for c in f["supply_chests"]:
        for k, v in c["contents"].items():
            tot[k] = tot.get(k, 0) + v
    f["supply_totals"] = dict(sorted(tot.items()))
    f["supply_totals_source"] = "sum of supply_chests contents (portal-loot.json + chest-survey.json)"

    # Entry portal (overworld). Existing frame blocks from portal-survey near the frame.
    ep = cfg["entryPortal"]
    frame = [o for o in portal_sv["groups"]["obsidian"]
             if abs(o["x"] - ep["x"]) <= 1 and abs(o["z"] - ep["z"]) <= 3 and ep["y"] - 2 <= o["y"] <= ep["y"] + 4]
    crying = [o for o in portal_sv["groups"].get("crying_obsidian", [])
              if abs(o["x"] - ep["x"]) <= 1 and abs(o["z"] - ep["z"]) <= 3]
    f["entry_portal"] = _pt(ep, "overworld", "config.json#entryPortal", axis=ep.get("axis"),
                            existing_frame_obsidian=[_xyz(o) for o in frame],
                            existing_frame_source="portal-survey.json#groups.obsidian (within frame box)",
                            crying_obsidian=[_xyz(o) for o in crying],
                            essential_existing=3, obsidian_to_place=7,
                            obsidian_source=f"{REF}:9 (3 essential exist, 7 placed; avoids crying obsidian)",
                            config_note=cfg.get("entryNote"))
    nb = entry_link["groups"]["nether_portal"]
    f["entry_portal_nether_side"] = _pt(_center(nb), "the_nether", "entry-link.json#groups.nether_portal",
                                        blocks=[_xyz(b) for b in nb])

    xp = cfg["exitPortal"]
    f["exit_portal"] = _pt(xp, "the_nether", "config.json#exitPortal", axis=xp.get("axis"),
                           obsidian_to_place=10, obsidian_source=f"{REF}:9 (ten obsidian, four ordinary corners)")
    ob = exit_link["groups"]["nether_portal"]
    f["exit_portal_overworld_side"] = _pt(_center(ob), "overworld", "exit-link.json#groups.nether_portal",
                                          blocks=[_xyz(b) for b in ob])

    ap = cfg["activePortal"]
    frames = sh_sv["groups"]["end_portal_frame"]
    f["end_portal"] = _pt(ap, "overworld", "config.json#activePortal", active=True,
                          frame_count=len(frames), eyes_filled=sum(1 for b in frames if b["properties"].get("eye")),
                          portal_blocks=[_xyz(b) for b in sh_sv["groups"]["end_portal"]],
                          frame_source="stronghold-survey.json#groups.end_portal_frame")

    route = [_pt(p, "the_nether", f"config.json#netherTravel[{i}]") for i, p in enumerate(cfg.get("netherTravel", []))]
    for i, p in enumerate(cfg.get("netherRoute", [])):
        if _xyz(p) not in {_xyz(r) for r in route}:
            route.append(_pt(p, "the_nether", f"config.json#netherRoute[{i}]"))
    f["nether_route"] = route

    f["beds"] = [_pt(p, "overworld", f"config.json#preparationBeds[{i}]")
                 for i, p in enumerate(cfg.get("preparationBeds", []))]

    sp = spawn_sv["position"]
    f["spawn"] = _pt({"x": int(sp["x"] // 1), "y": int(sp["y"]), "z": int(sp["z"] // 1)}, "overworld",
                     "spawn-survey.json#position", approximate=True,
                     note="bot position when the spawn survey ran (fresh join), not read from level.dat")

    f["stronghold_chests"] = [_pt(c, "overworld", "stronghold-survey.json#groups.chest", contents=None)
                              for c in sh_sv["groups"]["chest"]]

    f["kit"] = dict(cfg.get("kit", {}), source="config.json#kit")
    f["route_source"] = dict(url=cfg.get("source"), source="config.json#source")

    # Not surveyed in the reference repo; empty lists so detectors can rely on the key.
    f["lava_pools"] = []
    f["water"] = []
    f["hazards_source"] = "none: rmalde surveys scan chests/beds/obsidian/portals/gravel only (survey.mjs:4)"
    return f


def feature_points(feats: dict) -> dict:
    """Flat name -> {x,y,z,dim,source}, same shape as Timeline.knowledge."""
    out = {}
    for name in ("village", "entry_portal", "entry_portal_nether_side", "exit_portal",
                 "exit_portal_overworld_side", "end_portal", "spawn"):
        if name in feats:
            v = feats[name]
            out[name] = {k: v[k] for k in ("x", "y", "z", "dim", "source")}
    for c in feats.get("supply_chests", []):
        out[f"chest@{c['x']},{c['y']},{c['z']}"] = {k: c[k] for k in ("x", "y", "z", "dim", "source")}
    for i, p in enumerate(feats.get("nether_route", [])):
        out[f"nether_route[{i}]"] = {k: p[k] for k in ("x", "y", "z", "dim", "source")}
    for i, p in enumerate(feats.get("beds", [])):
        out[f"bed[{i}]"] = {k: p[k] for k in ("x", "y", "z", "dim", "source")}
    return out


if __name__ == "__main__":
    import sys
    print(json.dumps(load_seed_features(sys.argv[1] if len(sys.argv) > 1 else None), indent=1))
