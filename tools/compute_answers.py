"""Reproducible math behind the numeric and coordinate reference answers.

Run:  python tools/compute_answers.py
Prints every computed value used in reference/*.json. No game files or network needed.

Conventions (sources in SOURCES.md):
- Minecraft yaw: 0 = south (+Z), -90 = east (+X), 90 = west (-X), +-180 = north (-Z).
  Unit direction for yaw y is (dx, dz) = (-sin y, cos y).            [minecraft.wiki/w/Rotation]
- Nether <-> overworld: X and Z scale 1:8, Y is not scaled.          [minecraft.wiki/w/Nether_Portal]
- First stronghold ring (Java): 1,280-2,816 blocks from (0, 0).      [minecraft.wiki/w/Stronghold]
- Eye of ender: 20% break, 80% survive, per throw.                   [minecraft.wiki/w/Eye_of_Ender]
- Blaze rod -> 2 blaze powder; eye = 1 powder + 1 pearl.             [minecraft.wiki/w/Blaze_Powder, Eye_of_Ender]
- Piglin barter, ender pearl entry (from the game's loot table gameplay/piglin_bartering.json):
    1.16.1: weight 20 of 423, count uniform 4-8
    1.16.5: weight 10 of 459, count uniform 2-4
  [github.com/InventivetalentDev/minecraft-assets, branches 1.16.1 and 1.16.5]
"""
import json
import math

# ---------- geometry ----------

def yaw_to_dir(yaw_deg):
    r = math.radians(yaw_deg)
    return (-math.sin(r), math.cos(r))


def dir_to_yaw(dx, dz):
    return math.degrees(math.atan2(-dx, dz))


def intersect(p1, yaw1, p2, yaw2):
    """Intersect two rays p + t*d (2D, x/z). Returns (x, z, t1, t2)."""
    d1, d2 = yaw_to_dir(yaw1), yaw_to_dir(yaw2)
    det = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
    if abs(det) < 1e-12:
        raise ValueError("parallel throws")
    bx, bz = p2[0] - p1[0], p2[1] - p1[1]
    t1 = (bx * (-d2[1]) - bz * (-d2[0])) / det
    t2 = (d1[0] * bz - d1[1] * bx) / det
    return (p1[0] + t1 * d1[0], p1[1] + t1 * d1[1], t1, t2)


def to_nether(x, z):
    return (x / 8.0, z / 8.0)


def dist(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


# ---------- task data ----------

# T13 / T14: generic triangulation. The stronghold eye target is a chunk's NW corner (chunk 94, -132).
TRI_TARGET = (94 * 16, -132 * 16)          # (1504, -2112)
TRI_P1 = (1180.7, -1650.3)                  # throw 1 (x, z)
TRI_P2 = (1262.4, -1609.8)                  # throw 2, ~91 blocks to the side


def triangulation():
    yaw1_true = dir_to_yaw(TRI_TARGET[0] - TRI_P1[0], TRI_TARGET[1] - TRI_P1[1])
    yaw2_true = dir_to_yaw(TRI_TARGET[0] - TRI_P2[0], TRI_TARGET[1] - TRI_P2[1])
    yaw1, yaw2 = round(yaw1_true, 1), round(yaw2_true, 1)   # F3 shows one decimal
    x, z, t1, t2 = intersect(TRI_P1, yaw1, TRI_P2, yaw2)
    # Sensitivity: worst case over +-0.05 deg reading error on both throws.
    worst = 0.0
    for e1 in (-0.05, 0.05):
        for e2 in (-0.05, 0.05):
            xx, zz, _, _ = intersect(TRI_P1, yaw1 + e1, TRI_P2, yaw2 + e2)
            worst = max(worst, dist((xx, zz), (x, z)))
    # Trap: treating yaw as a math angle measured from +X counter-clockwise.
    def naive_dir(a):
        r = math.radians(a)
        return (math.cos(r), math.sin(r))
    d1, d2 = naive_dir(yaw1), naive_dir(yaw2)
    det = d1[0] * (-d2[1]) - d1[1] * (-d2[0])
    bx, bz = TRI_P2[0] - TRI_P1[0], TRI_P2[1] - TRI_P1[1]
    tt = (bx * (-d2[1]) - bz * (-d2[0])) / det
    naive = (TRI_P1[0] + tt * d1[0], TRI_P1[1] + tt * d1[1])
    return {
        "throw1": {"x": TRI_P1[0], "z": TRI_P1[1], "yaw": yaw1},
        "throw2": {"x": TRI_P2[0], "z": TRI_P2[1], "yaw": yaw2},
        "intersection_overworld": {"x": round(x, 1), "z": round(z, 1)},
        "distance_from_throw1": round(t1, 1),
        "distance_from_origin": round(math.hypot(x, z), 1),
        "in_first_ring": 1280 <= math.hypot(x, z) <= 2816,
        "worst_case_error_blocks_for_0.05deg": round(worst, 1),
        "true_target": {"x": TRI_TARGET[0], "z": TRI_TARGET[1]},
        "staircase_center_4_4": {"x": TRI_TARGET[0] + 4, "z": TRI_TARGET[1] + 4},
        "intersection_nether": {"x": round(x / 8, 1), "z": round(z / 8, 1)},
        "trap_math_angle_convention": {"x": round(naive[0], 1), "z": round(naive[1], 1)},
        "trap_throw1_distance_to_true": round(dist(TRI_P1, TRI_TARGET), 1),
    }


def seed_nether_exit():
    end_portal = (-1130, 856)                 # rmalde/minecraft-agent optimization/nether/config.json:52-56
    real_exit = (-141, 104)                   # config.json:34-39 (Nether side)
    n = to_nether(*end_portal)
    return {
        "end_portal_overworld": end_portal,
        "ideal_nether_xz": n,
        "real_exit_nether_xz": real_exit,
        "real_exit_error_nether_blocks": round(dist(n, real_exit), 2),
        "real_exit_maps_to_overworld": (real_exit[0] * 8, real_exit[1] * 8),
        "real_exit_overworld_walk_to_portal": round(dist((real_exit[0] * 8, real_exit[1] * 8), end_portal), 1),
        "trap_no_scaling": end_portal,
        "trap_multiply_by_8": (end_portal[0] * 8, end_portal[1] * 8),
    }


def blind_generic():
    # T12: stronghold estimate (1800, -900) overworld, player at overworld (40, -60).
    sh, me = (1800, -900), (40, -60)
    return {
        "overworld_distance": round(dist(sh, me), 1),
        "nether_distance": round(dist(to_nether(*sh), to_nether(*me)), 1),
        "nether_target": to_nether(*sh),
    }


def barter(ingots):
    def ev(w, tot, lo, hi):
        return w / tot * (lo + hi) / 2.0
    e1161, e1165 = ev(20, 423, 4, 8), ev(10, 459, 2, 4)
    return {
        "pearls_per_ingot_1.16.1": round(e1161, 5),
        "pearls_per_ingot_1.16.5": round(e1165, 5),
        "expected_pearls_1.16.1": round(ingots * e1161, 2),
        "expected_pearls_1.16.5": round(ingots * e1165, 2),
        "ingots_for_12_expected_1.16.1": round(12 / e1161, 1),
        "ingots_for_12_expected_1.16.5": round(12 / e1165, 1),
        "ratio_1161_over_1165": round(e1161 / e1165, 2),
    }


def rods_needed(pearls, rods, powder):
    need_powder = max(0, pearls - powder - 2 * rods)
    return {"additional_blaze_rods": math.ceil(need_powder / 2),
            "trap_rods_one_per_eye": max(0, pearls - rods),
            "trap_ignore_loose_powder": math.ceil(max(0, pearls - 2 * rods) / 2)}


def eye_breaks(throws, p_break=0.2):
    return {"expected_eyes_lost": round(throws * p_break, 3),
            "p_no_eye_lost": round((1 - p_break) ** throws, 4),
            "p_at_least_one_lost": round(1 - (1 - p_break) ** throws, 4)}


def ruined_portal_seed():
    """Ruined portal on seed 8398967436125155523, plane x = -285, coords (z, y).
    From rmalde/minecraft-agent optimization/nether/portal-survey.json (groups.obsidian / crying_obsidian)."""
    obsidian = {(258, 66), (259, 66), (260, 66), (261, 68), (261, 69), (259, 70), (260, 70), (261, 70)}
    crying = {(261, 66), (261, 67)}
    best = None
    rows = []
    for a in range(255, 262):          # interior starts at z = a, width 2
        for b in (67,):                 # interior starts at y = b, height 3 (bottom row y=66 exists)
            frame = [(a, b - 1), (a + 1, b - 1), (a, b + 3), (a + 1, b + 3)]
            frame += [(a - 1, b + i) for i in range(3)] + [(a + 2, b + i) for i in range(3)]
            blocked = [p for p in frame if p in crying]
            have = [p for p in frame if p in obsidian]
            place = 10 - len(have)
            rows.append({"interior_z": [a, a + 1], "existing_usable": len(have), "place": place,
                         "needs_crying_removed": len(blocked) > 0})
            if not blocked and (best is None or place < best["place"]):
                best = rows[-1]
    return {"options": rows, "best_without_diamond_pickaxe": best}


def main():
    out = {
        "T11_seed_nether_exit": seed_nether_exit(),
        "T12_blind_generic": blind_generic(),
        "T13_T14_triangulation": triangulation(),
        "T06_T07_barter_32_ingots": barter(32),
        "T10_rods": rods_needed(pearls=11, rods=2, powder=1),
        "T16_eye_breaks_3_throws": eye_breaks(3),
        "T05_ruined_portal": ruined_portal_seed(),
    }
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
