// The route model. This is the domain knowledge the planner is given, written down as data:
// entry conditions, pro technique, the miss it prevents, and the target time.
// Times/sources live in docs/ground-truth.md; everything marked [verify] needs a VOD check.
const { SPLIT_TARGETS } = require('./math')

const SPLITS = [
  {
    id: 'spawn',
    title: 'Reset judgment',
    target: SPLIT_TARGETS.spawn_reset,
    enter: () => true,
    pro: 'Judge the seed in seconds: trees/ruins/village/lava pool within ~80 blocks, or reset.',
    miss: 'Plays every seed; sinks minutes into a hopeless spawn.',
    technique: 'reset_judgment',
    skills: ['goto', 'collect_wood']
  },
  {
    id: 'wood',
    title: 'Wood + basic tools',
    target: SPLIT_TARGETS.wood,
    enter: s => !s.inventory.items.some(i => /_pickaxe/.test(i.name)),
    pro: '4-8 logs, planks, sticks, wooden pickaxe and axe in under ~25s. No spare tools.',
    miss: 'Over-collects wood/food/tools ("extra everything" in the rmalde notes).',
    technique: 'minimal_toolkit',
    skills: ['collect_wood', 'craft', 'ensure_pickaxe', 'ensure_axe']
  },
  {
    id: 'stone',
    title: 'Stone tools',
    target: SPLIT_TARGETS.stone_tools,
    enter: s => !s.inventory.items.some(i => /stone_pickaxe/.test(i.name)),
    pro: '3 stone for a stone pickaxe (and sword if mobs). Dig exposed stone, not a staircase to y=11.',
    miss: 'Mines a full staircase and a stack of cobblestone the route never uses.',
    technique: 'exposed_stone',
    skills: ['dig_staircase', 'mine_blocks', 'craft', 'ensure_pickaxe', 'ensure_sword']
  },
  {
    id: 'iron',
    title: 'Iron + food + bucket',
    target: SPLIT_TARGETS.iron_and_food,
    enter: s => !s.inventory.items.some(i => /iron_pickaxe|bucket/.test(i.name)),
    pro: '3 iron for a bucket (and pickaxe if a lava pool is the plan). Kill 2-3 animals on the way. Never full armor.',
    miss: 'Farms food or builds armor; the "potato detour".',
    technique: 'iron_for_bucket',
    skills: ['mine_blocks', 'smelt', 'craft', 'attack', 'eat']
  },
  {
    id: 'portal',
    title: 'Nether entry',
    target: SPLIT_TARGETS.nether_entry,
    enter: s => s.dimension === 'overworld' && !s.blocks.netherPortal,
    pro: 'Bucket portal: water on a lava pool makes obsidian in place (needs a diamond pickaxe to mine it), or finish a ruined portal with chest obsidian. Never mine obsidian bare-handed and never detour for diamonds unless the pool route needs it.',
    miss: 'Mines obsidian with a diamond pickaxe (needs a diamond detour), or wanders looking for a village.',
    technique: 'lava_pool_portal|ruined_portal',
    skills: ['water_on_lava', 'light_portal', 'enter_portal', 'take_from_chest', 'goto']
  },
  {
    id: 'pearls',
    title: 'Bastion / pearls',
    target: SPLIT_TARGETS.bastion_pearls,
    enter: s => s.dimension === 'nether' && !s.inventory.items.some(i => i.name === 'ender_pearl'),
    pro: 'Bastion chests are the pearl source; barter is supplementary (pearl rate is low). Wear one gold piece before entering; never open chests or break gold blocks in front of piglins without it.',
    miss: 'Hunts endermen, or loots without gold armor and gets swarmed.',
    technique: 'bastion_loot|gold_armor_barter',
    skills: ['barter', 'take_from_chest', 'attack', 'flee']
  },
  {
    id: 'rods',
    title: 'Fortress / blaze rods',
    target: SPLIT_TARGETS.fortress_rods,
    enter: s => s.dimension === 'nether' && !s.inventory.items.some(i => i.name === 'blaze_rod'),
    pro: '6 rods = 12 powder = 12 eyes; take 7 as buffer. Eyes break 20% per throw. Do not over-farm.',
    miss: 'Under-farms (forgets eyes break) or farms a stack of rods.',
    technique: 'exact_rod_count',
    skills: ['attack', 'collect_wood', 'take_from_chest']
  },
  {
    id: 'stronghold',
    title: 'Blind travel + triangulation',
    target: SPLIT_TARGETS.stronghold,
    enter: s => s.dimension === 'nether' && s.inventory.items.some(i => i.name === 'ender_eye'),
    pro: 'Travel in the Nether at 8:1 (ring 1 stronghold = 1280-2816 overworld = 160-352 nether blocks). Throw two eyes, intersect the bearings, then go.',
    miss: 'Walks in the overworld (8x slower) or follows eyes one at a time, wasting the 20%.',
    technique: 'nether_ratio|triangulate',
    skills: ['goto', 'throw_eye', 'enter_portal']
  },
  {
    id: 'end',
    title: 'End portal room',
    target: SPLIT_TARGETS.end_entry,
    enter: s => s.dimension === 'overworld' && s.blocks.endPortalFrame,
    pro: 'Fill only the empty frames: 12 minus pre-filled (10% each). Have spare eyes for the 20% break rate.',
    miss: 'Miscounts frames or eyes.',
    technique: 'frame_count',
    skills: ['goto']
  },
  {
    id: 'dragon',
    title: 'Dragon',
    target: SPLIT_TARGETS.dragon,
    enter: s => s.dimension === 'the_end',
    pro: 'Beds explode in the End: place and detonate when the dragon perches. 4-6 beds is a one-cycle with practice. Do not sword the dragon.',
    miss: 'Bows/swords the dragon for minutes and dies to breath or the void.',
    technique: 'bed_explosion',
    skills: ['goto', 'craft', 'attack']
  }
]

function detectSplit (state) {
  const inv = state.inventory.items
  const hasPearl = inv.some(i => i.name === 'ender_pearl')
  const hasEye = inv.some(i => i.name === 'ender_eye')
  const hasRod = inv.some(i => i.name === 'blaze_rod')
  const hasPick = inv.some(i => /_pickaxe$/.test(i.name))
  const hasStone = inv.some(i => /stone_pickaxe$/.test(i.name))
  const hasIronTool = inv.some(i => /iron_pickaxe$/.test(i.name))
  const hasBucket = inv.some(i => /_bucket$/.test(i.name))
  if (state.dimension === 'the_end') return 'dragon'
  if (state.dimension === 'nether') {
    if (hasEye) return 'stronghold'
    if (hasRod) return 'rods'
    if (hasPearl) return 'pearls'
    return 'pearls'
  }
  if (state.blocks?.endPortalFrame) return 'end'
  if (state.blocks?.netherPortal) return 'portal'
  if (!hasPick) return 'wood'
  if (!hasStone) return 'stone'
  if (!hasIronTool && !hasBucket) return 'iron'
  return 'portal'
}

function routeState (state, startedAt, now = Date.now()) {
  const id = detectSplit(state)
  const split = SPLITS.find(s => s.id === id) || SPLITS[0]
  const elapsed = Math.round((now - startedAt) / 1000)
  const behind = elapsed - split.target
  return {
    split: id,
    title: split.title,
    elapsedS: elapsed,
    targetS: split.target,
    behindS: behind,
    onPace: behind <= 15,
    pro: split.pro,
    expectedMiss: split.miss,
    technique: split.technique,
    nextSkills: split.skills
  }
}

module.exports = { SPLITS, detectSplit, routeState }
