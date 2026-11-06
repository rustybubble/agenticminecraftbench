// Deterministic Minecraft 1.16 arithmetic. The point of this module is that an LLM should
// never do coordinate math in its head: every number the planner needs is computed here and
// shown to it. These are also the checks behind the SplitCheck decision tasks.
//
// Sources: Minecraft Wiki (Nether portal, Eye of Ender, Stronghold, Bartering, End portal frame).
// Numbers flagged [verify] in docs/ground-truth.md.

const clamp = (v, lo, hi) => Math.max(lo, Math.min(hi, v))
const HALF_PI = Math.PI / 2

// --- Portal linking -------------------------------------------------------
// Overworld -> Nether: x/8, z/8 (floored). Nether -> Overworld: x*8, z*8.
// Y is not scaled; the game searches for a safe spot near the target Y.
function overworldToNether ({ x, z }) {
  return { x: Math.floor(x / 8), z: Math.floor(z / 8) }
}
function netherToOverworld ({ x, z }) {
  return { x: Math.floor(x * 8), z: Math.floor(z * 8) }
}
// Where a new nether-side portal should be built so that it links back to an overworld portal.
// Portals link to the closest portal within 128 blocks on the destination side.
function portalTarget (overworldPos, netherY = 40) {
  const n = overworldToNether(overworldPos)
  return { x: n.x + 0.5, y: netherY, z: n.z + 0.5, tolerance: 8 }
}

// --- Eye of Ender triangulation ------------------------------------------
// Eyes travel toward the stronghold and break 20% of the time. Two throws from different
// positions give two rays; their intersection is the stronghold estimate.
// yaw in Minecraft degrees: 0 = +Z (south), 90 = -X (west), 180 = -Z, 270 = +X.
function yawToVector (yawDeg) {
  const r = yawDeg * Math.PI / 180
  return { x: -Math.sin(r), z: Math.cos(r) }
}
function rayIntersect (a, b) {
  const v1 = yawToVector(a.yaw), v2 = yawToVector(b.yaw)
  const den = v1.x * v2.z - v1.z * v2.x
  if (Math.abs(den) < 1e-6) return null
  const dx = b.x - a.x, dz = b.z - a.z
  const t = (dx * v2.z - dz * v2.x) / den
  const u = (dx * v1.z - dz * v1.x) / den
  if (t <= 0 || u <= 0) return null
  return { x: a.x + v1.x * t, z: a.z + v1.z * t, t, u }
}
function triangulate (throws) {
  if (throws.length < 2) return { ok: false, error: 'need >=2 throws' }
  let best = null
  for (let i = 0; i < throws.length; i++) {
    for (let j = i + 1; j < throws.length; j++) {
      const p = rayIntersect(throws[i], throws[j])
      if (!p) continue
      // agreement of the two rays: distance between the intersection and each ray's own
      // independent least-squares position is captured by t/u; keep the closest crossing.
      if (!best || Math.abs(p.t - p.u) < Math.abs(best.t - best.u)) best = p
    }
  }
  if (!best) return { ok: false, error: 'rays are parallel or point apart' }
  const dist = Math.hypot(best.x, best.z)
  return {
    ok: true,
    x: Math.round(best.x), z: Math.round(best.z),
    distanceFromOrigin: Math.round(dist),
    inFirstRing: dist >= 1280 && dist <= 2816,
    note: 'stronghold ring 1 is 1280-2816 blocks from origin'
  }
}

// --- Ender resources ------------------------------------------------------
// 12 frames per End portal; each generated frame has a 10% chance to already hold an eye.
// 1 blaze rod -> 2 blaze powder; 1 eye = 1 pearl + 1 powder.
// A thrown eye has a 20% chance to shatter, so expected throws = needed / 0.8.
function enderRequirement ({ filledFrames = 0, pearls = 0, rods = 0, spareEyes = 1 } = {}) {
  const empty = 12 - clamp(filledFrames, 0, 12)
  const eyesNeeded = empty
  const pearlsShort = Math.max(0, eyesNeeded - pearls)
  const powderHave = rods * 2
  const powderShort = Math.max(0, eyesNeeded - powderHave)
  const rodsNeeded = Math.ceil(powderShort / 2)
  const expectedThrows = Math.ceil(eyesNeeded / 0.8)
  const eyesWithSpare = eyesNeeded + spareEyes
  return {
    emptyFrames: empty,
    eyesNeeded,
    pearlsShort, powderShort, rodsNeeded,
    expectedThrowsToLocate: expectedThrows,
    eyesWithSpare, rodsWithSpare: Math.ceil(Math.max(0, eyesWithSpare - powderHave) / 2),
    note: 'eyes break 20% per throw; 12 frames, 10% pre-filled each'
  }
}

// --- Bartering ------------------------------------------------------------
// 1.16.1 piglin bartering loot (Minecraft Wiki, Bartering table). Weights out of 459.
// End result is pearls per gold ingot, used to decide "barter or loot a bastion".
const BARTER_1_16_1 = {
  totalWeight: 459,
  drops: {
    ender_pearl: 8,
    obsidian: 40,
    string: 40,
    fire_charge: 40,
    gravel: 40,
    leather: 40,
    iron_nugget: 40,
    quartz: 40,
    glowstone_dust: 40,
    nether_brick: 40,
    crying_obsidian: 40,
    soul_sand: 40,
    leather_boots: 8,
    potion_fire_resistance: 8,
    splash_potion_fire_resistance: 8,
    water_bottle: 8,
    iron_boots: 8
  }
}
function barterMath (goldIngots) {
  const pPearl = (BARTER_1_16_1.drops.ender_pearl || 0) / BARTER_1_16_1.totalWeight
  const pObsidian = (BARTER_1_16_1.drops.obsidian || 0) / BARTER_1_16_1.totalWeight
  const expectedPearls = goldIngots * pPearl
  return {
    pPearl: +(pPearl * 100).toFixed(2),
    expectedPearls: +expectedPearls.toFixed(2),
    bartersFor12Pearls: Math.ceil(12 / pPearl),
    expectedObsidian: +(goldIngots * pObsidian).toFixed(1),
    note: '1.16.1 weights, [verify] against wiki before citing'
  }
}

// --- Route timing ---------------------------------------------------------
// Pro RSG 1.16.1 split targets in seconds. Source: WR/top-runner VODs, [verify].
// These are targets, not claims: used to tell the planner how far off pace it is.
const SPLIT_TARGETS = {
  spawn_reset: 5,
  wood: 25,
  stone_tools: 60,
  iron_and_food: 120,
  nether_entry: 150,
  bastion_pearls: 210,
  fortress_rods: 300,
  blind_travel: 330,
  stronghold: 380,
  end_entry: 400,
  dragon: 400
}

module.exports = {
  overworldToNether, netherToOverworld, portalTarget,
  yawToVector, rayIntersect, triangulate,
  enderRequirement, barterMath, BARTER_1_16_1, SPLIT_TARGETS
}
