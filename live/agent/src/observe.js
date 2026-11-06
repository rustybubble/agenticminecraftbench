// Observation layer: turn the bot's packet-level world into a compact, stable state object
// an LLM can reason about. One world scan per snapshot (findBlocks over a single id set),
// so cost is O(radius^3) once instead of per-material.
const config = require('./config')

const NAMES = [
  'oak_log', 'birch_log', 'spruce_log', 'jungle_log', 'acacia_log', 'dark_oak_log', 'log', 'log2',
  'crafting_table', 'furnace', 'chest', 'barrel', 'water', 'lava', 'obsidian', 'gravel', 'sand',
  'iron_ore', 'coal_ore', 'diamond_ore', 'gold_ore', 'redstone_ore', 'stone', 'cobblestone',
  'grass_block', 'dirt', 'netherrack', 'soul_sand', 'nether_gold_ore', 'nether_quartz_ore',
  'bed', 'white_bed', 'red_bed', 'end_portal_frame', 'end_portal', 'nether_portal',
  'bastion_remnant', 'spawner', 'blaze_spawner', 'gold_block', 'ancient_debris'
]

const HOSTILE = new Set([
  'zombie', 'skeleton', 'creeper', 'spider', 'enderman', 'witch', 'slime', 'magma_cube',
  'blaze', 'ghast', 'zombified_piglin', 'piglin', 'hoglin', 'zoglin', 'phantom', 'drowned',
  'pillager', 'vindicator', 'evoker', 'ravager', 'silverfish'
])

class Observer {
  constructor (bot, mcData) {
    this.bot = bot
    this.mcData = mcData
    this.ids = new Map()
    for (const n of NAMES) {
      const b = mcData.blocksByName[n]
      if (b) this.ids.set(b.id, n)
    }
    this.matching = [...this.ids.keys()]
    this.logs = new Map()
    for (const [id, name] of this.ids) if (name.endsWith('_log') || name === 'log' || name === 'log2') this.logs.set(id, name)
  }

  itemName (item) {
    if (!item) return null
    return item.displayName || item.name
  }

  inventory () {
    const counts = new Map()
    for (const it of this.bot.inventory.items()) {
      const key = it.name
      counts.set(key, (counts.get(key) || 0) + it.count)
    }
    const list = [...counts.entries()]
      .sort((a, b) => b[1] - a[1])
      .map(([name, count]) => ({ name, count }))
    const armor = []
    for (const slot of ['head', 'torso', 'legs', 'feet']) {
      const it = this.bot.inventory.slots[this.bot.getEquipmentDestSlot(slot)]
      if (it) armor.push(`${slot}:${it.name}`)
    }
    return {
      items: list,
      totalItems: list.reduce((s, i) => s + i.count, 0),
      held: this.bot.heldItem ? this.bot.heldItem.name : null,
      armor
    }
  }

  blockSummary () {
    const R = 24
    const found = this.bot.findBlocks({ matching: this.matching, maxDistance: R, count: 600 }) || []
    const nearest = new Map()
    const counts = new Map()
    const p = this.bot.entity.position
    for (const pos of found) {
      const b = this.bot.blockAt(pos)
      if (!b) continue
      const name = this.ids.get(b.type) || b.name
      counts.set(name, (counts.get(name) || 0) + 1)
      const d = p.distanceTo(pos)
      const cur = nearest.get(name)
      if (!cur || d < cur.dist) nearest.set(name, { dist: +d.toFixed(1), x: pos.x, y: pos.y, z: pos.z })
    }
    const get = n => nearest.get(n) || null
    const isLog = n => n.endsWith('_log') || n === 'log' || n === 'log2'
    let logCount = 0, logNearest = null
    for (const [name, info] of nearest) if (isLog(name)) { logCount += counts.get(name) || 0; if (!logNearest || info.dist < logNearest.dist) logNearest = info }
    const pick = names => {
      let best = null
      for (const n of names) { const i = get(n); if (i && (!best || i.dist < best.dist)) best = i }
      return best
    }
    return {
      radius: R,
      counts: Object.fromEntries([...counts].sort((a, b) => b[1] - a[1]).slice(0, 18)),
      logs: { count: logCount, nearest: logNearest },
      water: pick(['water']),
      lava: pick(['lava']),
      obsidian: pick(['obsidian']),
      ironOre: pick(['iron_ore']),
      coalOre: pick(['coal_ore']),
      diamondOre: pick(['diamond_ore']),
      gravel: pick(['gravel']),
      sand: pick(['sand']),
      craftingTable: pick(['crafting_table']),
      furnace: pick(['furnace']),
      chest: pick(['chest', 'barrel']),
      bed: pick(['bed', 'white_bed', 'red_bed']),
      netherPortal: pick(['nether_portal']),
      endPortalFrame: pick(['end_portal_frame']),
      goldBlock: pick(['gold_block']),
      netherGoldOre: pick(['nether_gold_ore']),
      blazeSpawner: pick(['spawner']),
      netherrack: pick(['netherrack']),
      soulSand: pick(['soul_sand'])
    }
  }

  entities () {
    const p = this.bot.entity.position
    const hostiles = [], passives = [], items = [], players = []
    for (const e of Object.values(this.bot.entities)) {
      if (!e || e === this.bot.entity || !e.position) continue
      const d = p.distanceTo(e.position)
      if (d > 24) continue
      const rec = { name: e.name || e.username || e.type, dist: +d.toFixed(1), x: Math.round(e.position.x), y: Math.round(e.position.y), z: Math.round(e.position.z) }
      if (e.type === 'player') players.push({ ...rec, name: e.username || 'player' })
      else if (e.type === 'object' && (e.name === 'item' || e.objectType === 'Item')) items.push(rec)
      else if (HOSTILE.has(e.name)) hostiles.push(rec)
      else if (e.type === 'mob' || e.type === 'animal') passives.push(rec)
    }
    hostiles.sort((a, b) => a.dist - b.dist)
    items.sort((a, b) => a.dist - b.dist)
    return { hostiles, passives: passives.slice(0, 8), items: items.slice(0, 8), players }
  }

  danger (blocks) {
    const feet = this.bot.blockAt(this.bot.entity.position)
    const head = this.bot.blockAt(this.bot.entity.position.offset(0, 1.6, 0))
    const name = b => (b ? b.name : null)
    return {
      lavaWithin3: !!(blocks.lava && blocks.lava.dist <= 3),
      waterAtFeet: name(feet) === 'water',
      headInWater: name(head) === 'water',
      inPortal: name(feet) === 'nether_portal',
      onGround: this.bot.entity.onGround,
      falling: this.bot.entity.velocity ? this.bot.entity.velocity.y < -0.7 : false
    }
  }

  snapshot ({ recent = [], route = null, goal = null } = {}) {
    const b = this.bot
    const pos = b.entity.position
    const blocks = this.blockSummary()
    const ents = this.entities()
    const inv = this.inventory()
    const timeOfDay = b.time.timeOfDay
    return {
      t: Date.now(),
      username: b.username,
      dimension: (b.game.dimension || '').replace('minecraft:', ''),
      pos: { x: +pos.x.toFixed(1), y: +pos.y.toFixed(1), z: +pos.z.toFixed(1) },
      look: { yaw: +(b.entity.yaw * 180 / Math.PI).toFixed(1), pitch: +(b.entity.pitch * 180 / Math.PI).toFixed(1) },
      health: b.health,
      food: b.food,
      saturation: b.foodSaturation,
      air: b.air ?? null,
      xp: b.experience?.level ?? 0,
      time: { ticks: timeOfDay, isDay: timeOfDay < 13000, day: b.time.day },
      difficulty: b.game.difficulty,
      inventory: inv,
      blocks,
      entities: ents,
      danger: this.danger(blocks),
      route,
      goal,
      recent: recent.slice(-8)
    }
  }

  // Compact textual form for prompts. Keep under ~1800 chars.
  compact (s) {
    const i = s.inventory
    const items = i.items.slice(0, 14).map(x => `${x.name}x${x.count}`).join(', ') || 'empty'
    const hosts = s.entities.hostiles.slice(0, 4).map(h => `${h.name}@${h.dist}`).join(', ') || 'none'
    const drops = s.entities.items.slice(0, 3).map(h => `item@${h.dist}`).join(', ') || 'none'
    const bl = s.blocks
    const near = []
    const add = (label, v) => { if (v) near.push(`${label}@${v.dist}(${v.x},${v.y},${v.z})`) }
    add('logs', bl.logs.nearest); add('water', bl.water); add('lava', bl.lava)
    add('craftTable', bl.craftingTable); add('furnace', bl.furnace); add('chest', bl.chest)
    add('ironOre', bl.ironOre); add('coalOre', bl.coalOre); add('gravel', bl.gravel); add('sand', bl.sand)
    add('obsidian', bl.obsidian); add('netherPortal', bl.netherPortal); add('bed', bl.bed)
    add('goldBlock', bl.goldBlock); add('netherGoldOre', bl.netherGoldOre); add('blazeSpawner', bl.blazeSpawner)
    const danger = []
    if (s.danger.lavaWithin3) danger.push('LAVA<=3')
    if (s.danger.waterAtFeet) danger.push('in-water')
    if (s.danger.falling) danger.push('falling')
    if (s.danger.inPortal) danger.push('in-portal')
    if (s.health <= 8) danger.push('low-hp')
    if (s.food <= 6) danger.push('hungry')
    return [
      `dim=${s.dimension} pos=${s.pos.x},${s.pos.y},${s.pos.z} look=${s.look.yaw}/${s.look.pitch} t=${s.time.ticks}(${s.time.isDay ? 'day' : 'night'}) day=${s.time.day}`,
      `hp=${s.health} food=${s.food} air=${s.air} xp=${s.xp} held=${i.held || 'none'}`,
      `inv[${i.totalItems}]: ${items}`,
      `armor: ${i.armor.join(',') || 'none'}`,
      `near: ${near.join(' ') || 'nothing notable'}`,
      `counts: ${Object.entries(bl.counts).slice(0, 8).map(([k, v]) => `${k}:${v}`).join(' ')}`,
      `hostiles: ${hosts}; drops: ${drops}; players: ${s.entities.players.map(p => p.name).join(',') || 'none'}`,
      `danger: ${danger.join(',') || 'clear'}`,
      s.route ? `route: ${JSON.stringify(s.route)}` : null,
      s.goal ? `goal: ${s.goal}` : null,
      s.recent && s.recent.length ? `recent: ${s.recent.map(r => r.msg).join(' | ')}` : null
    ].filter(Boolean).join('\n')
  }
}

module.exports = { Observer, HOSTILE }
