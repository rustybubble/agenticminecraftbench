from splitcheck.seedfeatures import load_seed_features, feature_points, DEFAULT_SEED_DIR


def F():
    return load_seed_features()


def test_data_dir_and_provenance():
    assert (DEFAULT_SEED_DIR / "PROVENANCE.md").exists()


def test_supply_obsidian_total_21_and_key_items():
    f = F()
    assert len(f["supply_chests"]) == 3
    t = f["supply_totals"]
    assert t["obsidian"] == 21
    assert t["iron_pickaxe"] == 1
    assert t["flint"] == 1
    assert t["iron_ingot"] == 6
    by = {(c["x"], c["y"], c["z"]): c for c in f["supply_chests"]}
    assert by[(-228, 71, 240)]["contents"]["iron_pickaxe"] == 1
    assert by[(-284, 66, 262)]["contents"]["flint"] == 1
    assert sum(c["contents"].get("obsidian", 0) for c in by.values()) == 21


def test_end_portal():
    e = F()["end_portal"]
    assert (e["x"], e["y"], e["z"], e["dim"]) == (-1130, 34, 856, "overworld")
    assert e["frame_count"] == 12 and e["eyes_filled"] == 12
    assert len(e["portal_blocks"]) == 9


def test_portals_route_beds_village():
    f = F()
    assert (f["village"]["x"], f["village"]["z"]) == (-225, 255)
    ep = f["entry_portal"]
    assert (ep["x"], ep["y"], ep["z"]) == (-285, 67, 259)
    assert ep["obsidian_to_place"] == 7 and ep["essential_existing"] == 3
    assert len(ep["existing_frame_obsidian"]) >= 3
    assert (f["exit_portal"]["x"], f["exit_portal"]["dim"]) == (-141, "the_nether")
    assert len(f["nether_route"]) >= 8 and all(p["dim"] == "the_nether" for p in f["nether_route"])
    assert len(f["beds"]) == 8
    assert f["entry_portal_nether_side"]["dim"] == "the_nether"


def test_every_feature_has_source_and_deterministic():
    f = F()
    for k, v in f.items():
        if k == "supply_totals":
            assert "supply_totals_source" in f
        elif isinstance(v, dict):
            assert "source" in v, k
        elif isinstance(v, list):
            assert all("source" in x for x in v), k
    assert F() == f
    pts = feature_points(f)
    assert pts["end_portal"]["x"] == -1130 and all("dim" in p for p in pts.values())
