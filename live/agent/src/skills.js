// Deterministic skill library. This is the "hands" layer: every skill is plain code, so it is
// fast, testable and repeatable. The LLM only chooses which one to run and with what args.
//
// Why not let the model emit raw controls? The Gemini 4 Argon run needed 27h and 605 deaths,
// and rmalde/minecraft-agent needed a separate JEV action model for exactly this layer.
// Skills are the substitute for that action model here.
const { goals } = require('mineflayer-pathfinder')

const LOG_NAMES = [
  'oak_log', 'birch_log', 'spruce_log', 'jungle_log', 'acacia_log', 'dark_oak_log'
]
const FOOD = ['cooked_beef', 'cooked_porkchop', 'cooked_mutton', 'cooked_chicken', 'bread',
  'baked_potato', 'apple', 'carrot', 'golden_carrot', 'cooked_salmon', 'cooked_cod', 'beef', 'porkchop']
const TOOL_MAT = ['netherite', 'diamond', 'iron', 'stone', 'golden', 'wooden']
const PICKAXE = TOOL_MAT.map(m => `${m}_pickaxe`)
const AXE = TOOL_MAT.map(m => `${m}_axe`)
const SHOVEL = TOOL_MAT.map(m => `${m}_shovel`)
const SWORD = TOOL_MAT.map(m => `${m}_sword`)

const sleep = ms => new Promise(r => setTimeout(r, ms))

class Skills {
  constructor ({ bot, mcData, observer, log = () => {} }) {
    this.bot = bot
    this.mcData = mcData
    this.observer = observer
    this.log = log
    this.cancelled = false
  }

  cancel () {
    this.cancelled = true
    try { this.bot.pathfinder.stop() } catch {}
    try { this.bot.stopDigging() } catch {}
    try { this.bot.clearControlStates() } catch {}
  }

  reset () { this.cancelled = false }

  check () { if (this.cancelled) throw new Error('cancelled') }

  count (name) {
    let n = 0
    for (const it of this.bot.inventory.items()) if (it.name === name) n += it.count
    return n
  }

  has (name, n = 1) { return this.count(name) >= n }

  item (name) { return this.mcData.itemsByName[name] }

  blockId (name) { return this.mcData.blocksByName[name]?.id ?? null }

  async waitTicks (n) {
    const start = this.bot.time.age
    while (this.bot.time.age - start < n) {
      this.check()
      await sleep(50)
    }
  }

  async equip (name) {
    const it = this.bot.inventory.items().find(i => i.name === name)
    if (!it) return false
    if (this.bot.heldItem?.name === name) return true
    await this.bot.equip(it, 'hand')
    return true
  }

  bestToolFor (blockName) {
    const pool = /log|wood|planks|crafting_table|chest/.test(blockName) ? AXE
      : /dirt|grass|sand|gravel|clay|soul_sand/.test(blockName) ? SHOVEL
        : /stone|ore|cobble|obsidian|netherrack|furnace|brick/.test(blockName) ? PICKAXE
          : null
    if (!pool) return null
    for (const t of pool) if (this.has(t)) return t
    return null
  }

  async equipBestFor (blockName) {
    const t = this.bestToolFor(blockName)
    if (t) await this.equip(t)
    return t
  }

  findBlock (name, maxDistance = 32) {
    const id = this.blockId(name)
    if (id == null) return null
    const p = this.bot.findBlocks({ matching: id, maxDistance, count: 1 })
    return p.length ? this.bot.blockAt(p[0]) : null
  }

  findBlocks (names, maxDistance = 32, count = 32) {
    const ids = names.map(n => this.blockId(n)).filter(x => x != null)
    if (!ids.length) return []
    const pos = this.bot.findBlocks({ matching: ids, maxDistance, count })
    const p = this.bot.entity.position
    return pos.map(x => this.bot.blockAt(x)).filter(Boolean)
      .sort((a, b) => a.position.distanceTo(p) - b.position.distanceTo(p))
  }

  // mineflayer 4.39's bot.canDigBlock() returns false for ordinary blocks in 1.16.5, so use
  // the block table's hardness instead (bedrock/barriers are -1).
  canDig (block) {
    if (!block) return false
    if (/air|water|lava|bedrock|barrier|portal/.test(block.name)) return false
    return block.hardness === undefined || block.hardness >= 0
  }

  async goto (x, y, z, range = 2) {
    this.check()
    const { pathfinder } = require('mineflayer-pathfinder')
    if (!this.bot.pathfinder) throw new Error('pathfinder plugin missing')
    const goal = range <= 0 ? new goals.GoalBlock(Math.floor(x), Math.floor(y), Math.floor(z))
      : new goals.GoalNear(Math.floor(x), Math.floor(y), Math.floor(z), range)
    await this.bot.pathfinder.goto(goal)
    return { ok: true, pos: { ...this.bot.entity.position } }
  }

  // Dig one block, standing somewhere legal. Guards the failure rmalde documented: mining a
  // block that touches water and losing the drop.
  async dig (block) {
    this.check()
    if (!block || block.name === 'air') return { ok: false, error: 'no block' }
    if (/water|lava/.test(block.name)) return { ok: false, error: 'refusing to dig fluid' }
    const above = this.bot.blockAt(block.position.offset(0, 1, 0))
    const below = this.bot.blockAt(block.position.offset(0, -1, 0))
    if (/lava/.test(above?.name || '') || /lava/.test(below?.name || '')) {
      return { ok: false, error: 'block touches lava' }
    }
    await this.equipBestFor(block.name)
    const dist = this.bot.entity.position.distanceTo(block.position)
    if (dist > 4) await this.goto(block.position.x, block.position.y, block.position.z, 2)
    try { this.bot.pathfinder.stop() } catch {}
    await sleep(120)
    // if the drop would land in water, dig from the dry side: stand on the opposite side
    await this.bot.lookAt(block.position.offset(0.5, 0.5, 0.5), true)
    let lastErr
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await this.bot.dig(block)
        if (!this.bot.blockAt(block.position) || this.bot.blockAt(block.position).name === 'air') {
          return { ok: true, block: block.name, pos: { ...block.position } }
        }
      } catch (e) {
        lastErr = e
        await sleep(150)
      }
    }
    return { ok: false, error: `dig failed: ${lastErr ? lastErr.message : 'block still present'}` }
  }

  async collectDrops (radius = 8, ms = 2500) {
    const t0 = Date.now()
    while (Date.now() - t0 < ms) {
      this.check()
      const drop = this.bot.nearestEntity(e => e.name === 'item' && e.position &&
        e.position.distanceTo(this.bot.entity.position) <= radius)
      if (!drop) break
      try {
        await this.bot.pathfinder.goto(new goals.GoalBlock(
          Math.floor(drop.position.x), Math.floor(drop.position.y), Math.floor(drop.position.z)))
      } catch {}
      await sleep(150)
    }
  }

  async collectBlocks (names, count) {
    this.check()
    names = [].concat(names)
    const start = this.countTotal(names)
    let dug = 0
    let walked = 0
    const t0 = Date.now()
    while (this.countTotal(names) - start < count && Date.now() - t0 < 180000) {
      this.check()
      // widen the search before giving up; server view-distance is 8 chunks (~128 blocks)
      let next = null
      for (const R of [40, 64, 96]) {
        const blocks = this.findBlocks(names, R, 40)
        next = blocks.find(b => this.canDig(b))
        if (next) break
      }
      if (!next) {
        // nothing in view: sweep outward in a spiral and rescan
        if (walked >= 4) break
        const p = this.bot.entity.position
        const angle = (walked / 4) * Math.PI * 2
        const d = 48
        try {
          await this.bot.pathfinder.goto(new goals.GoalXZ(
            Math.floor(p.x + Math.cos(angle) * d), Math.floor(p.z + Math.sin(angle) * d)))
        } catch {}
        walked++
        continue
      }
      try {
        await this.dig(next)
        dug++
      } catch (e) {
        if (String(e.message).includes('cancelled')) throw e
        this.log({ type: 'skill_warn', skill: 'collectBlocks', error: String(e.message) })
      }
      await this.collectDrops(8, 1800)
    }
    const got = this.countTotal(names) - start
    return { ok: got >= count, got, target: count, dug, walked, elapsedMs: Date.now() - t0 }
  }

  countTotal (names) {
    return names.reduce((s, n) => s + this.count(n), 0)
  }

  // Can the current inventory satisfy this recipe? mineflayer recipes expose a `delta` list
  // (negative count = consumed), which is more reliable than `ingredients` for shaped recipes.
  canMake (recipe) {
    const need = new Map()
    for (const d of recipe.delta || []) if (d.count < 0) need.set(d.id, (need.get(d.id) || 0) - d.count)
    const have = new Map()
    for (const it of this.bot.inventory.items()) have.set(it.type, (have.get(it.type) || 0) + it.count)
    for (const [id, n] of need) if ((have.get(id) || 0) < n) return false
    return true
  }

  // Craft with the 2x2 grid or a nearby crafting table, placing one if needed.
  async craft (name, count = 1) {
    this.check()
    const item = this.item(name)
    if (!item) return { ok: false, error: `unknown item ${name}` }
    const all = this.bot.recipesAll(item.id, null, true)
    const twoByTwo = all.filter(r => !r.requiresTable)
    let needTable = twoByTwo.length === 0
    let table = null
    let recipe = (needTable ? all : twoByTwo).find(r => this.canMake(r))
    if (!recipe && !needTable) {
      needTable = true
      recipe = all.find(r => this.canMake(r))
    }
    if (needTable) {
      table = this.findBlock('crafting_table', 24)
      if (!table) {
        const placed = await this.placeCraftingTable()
        if (!placed.ok) return placed
        table = placed.block
      }
      if (table && this.bot.entity.position.distanceTo(table.position) > 4) {
        await this.goto(table.position.x, table.position.y, table.position.z, 2)
      }
    }
    if (!recipe) {
      const missing = (all[0]?.delta || []).filter(d => d.count < 0)
        .map(d => `${this.mcData.items[d.id]?.name || d.id}x${-d.count}`).join(', ')
      return { ok: false, error: `no recipe for ${name}: missing ${missing || 'ingredients'}` }
    }
    const made = []
    for (let i = 0; i < count; i++) {
      recipe = (needTable ? all : twoByTwo).find(r => this.canMake(r))
      if (!recipe) break
      await this.bot.craft(recipe, 1, needTable ? table : null)
      made.push(name)
    }
    return { ok: made.length === count, made: made.length, have: this.count(name) }
  }

  async placeCraftingTable () {
    this.check()
    const it = this.bot.inventory.items().find(i => i.name === 'crafting_table')
    if (!it) return { ok: false, error: 'no crafting_table item' }
    const p = this.bot.entity.position
    const offsets = [[1, 0, 0], [-1, 0, 0], [0, 0, 1], [0, 0, -1], [1, 0, 1], [-1, 0, -1], [0, 1, 0]]
    await this.equip('crafting_table')
    for (const [dx, dy, dz] of offsets) {
      const target = p.offset(dx, dy, dz).floored()
      const ground = this.bot.blockAt(target.offset(0, -1, 0))
      const here = this.bot.blockAt(target)
      if (!ground || ground.name === 'air' || !here || here.name !== 'air') continue
      try {
        await this.bot.lookAt(ground.position.offset(0.5, 1, 0.5), true)
        await this.bot.placeBlock(ground, new (require('vec3'))(0, 1, 0))
      } catch (e) {
        // mineflayer throws "the block is still air" when the update lags; verify directly
      }
      await sleep(350)
      const b = this.bot.blockAt(target)
      if (b && b.name === 'crafting_table') return { ok: true, block: b }
    }
    return { ok: false, error: 'no place to put crafting table' }
  }

  async ensureWood (target = 8) {
    const planks = this.count('oak_planks') + this.count('birch_planks') + this.count('spruce_planks') +
      this.count('jungle_planks') + this.count('acacia_planks') + this.count('dark_oak_planks')
    const logs = this.countTotal(LOG_NAMES)
    if (logs >= target) return { ok: true, logs, planks, skipped: true }
    return this.collectBlocks(LOG_NAMES, target - logs)
  }

  async ensurePlanks (n = 4) {
    const planksNames = LOG_NAMES.map(l => l.replace('_log', '_planks'))
    let have = this.countTotal(planksNames)
    while (have < n) {
      const log = this.bot.inventory.items().find(i => LOG_NAMES.includes(i.name))
      if (!log) return { ok: false, error: 'no logs to make planks' }
      const r = await this.craft(log.name.replace('_log', '_planks'), 1)
      if (!r.ok) return r
      have = this.countTotal(planksNames)
    }
    return { ok: true, planks: have }
  }

  async ensureSticks (n = 4) {
    while (this.count('stick') < n) {
      const r = await this.craft('stick', 1)
      if (!r.ok) return r
    }
    return { ok: true, sticks: this.count('stick') }
  }

  async ensurePickaxe (tier = 'wooden') {
    const name = `${tier}_pickaxe`
    if (this.has(name)) return { ok: true, skipped: true, have: name }
    await this.ensurePlanks(3)
    await this.ensureSticks(2)
    return this.craft(name, 1)
  }

  async ensureSword (tier = 'wooden') {
    const name = `${tier}_sword`
    if (this.has(name)) return { ok: true, skipped: true }
    await this.ensurePlanks(2)
    await this.ensureSticks(1)
    return this.craft(name, 1)
  }

  async ensureAxe (tier = 'wooden') {
    const name = `${tier}_axe`
    if (this.has(name)) return { ok: true, skipped: true }
    await this.ensurePlanks(3)
    await this.ensureSticks(2)
    return this.craft(name, 1)
  }

  async eat () {
    this.check()
    const foodName = FOOD.find(f => this.has(f))
    if (!foodName) return { ok: false, error: 'no food' }
    if (this.bot.food >= 20 && this.bot.health >= 20) return { ok: true, skipped: true }
    await this.equip(foodName)
    await this.bot.consume()
    return { ok: true, ate: foodName, food: this.bot.food }
  }

  // Simple melee. Deliberately bounded: no heroics, flee at low health.
  async attackNearest (kind = 'hostile', maxRange = 4, maxMs = 15000) {
    this.check()
    const t0 = Date.now()
    const isHostile = e => ['zombie', 'skeleton', 'creeper', 'spider', 'enderman', 'witch', 'slime',
      'magma_cube', 'blaze', 'zombified_piglin', 'piglin', 'hoglin', 'drowned', 'phantom'].includes(e.name)
    while (Date.now() - t0 < maxMs) {
      this.check()
      const p = this.bot.entity.position
      const target = this.bot.nearestEntity(e => e.position && e.name !== 'item' &&
        (kind === 'hostile' ? isHostile(e) : e.name === kind) &&
        e.position.distanceTo(p) <= maxRange + 8)
      if (!target) return { ok: true, killed: false, note: 'no target' }
      if (this.bot.health <= 6) return { ok: false, error: 'low health, aborting fight' }
      const d = target.position.distanceTo(p)
      if (d > 2.6) {
        try {
          await this.bot.pathfinder.goto(new goals.GoalNear(
            Math.floor(target.position.x), Math.floor(target.position.y), Math.floor(target.position.z), 2))
        } catch {}
      }
      const sword = SWORD.find(s => this.has(s))
      if (sword) await this.equip(sword)
      await this.bot.lookAt(target.position.offset(0, 1.5, 0), true)
      this.bot.attack(target)
      await sleep(620)
    }
    return { ok: true, killed: null, note: 'timeout' }
  }

  async flee (blocks = 16) {
    this.check()
    const p = this.bot.entity.position
    const hostile = this.bot.nearestEntity(e => e.position && ['zombie', 'skeleton', 'creeper', 'spider',
      'enderman', 'witch', 'blaze', 'piglin', 'hoglin', 'magma_cube', 'drowned'].includes(e.name) &&
      e.position.distanceTo(p) < 16)
    if (!hostile) return { ok: true, note: 'nothing to flee' }
    const dx = p.x - hostile.position.x
    const dz = p.z - hostile.position.z
    const len = Math.hypot(dx, dz) || 1
    const target = p.offset((dx / len) * blocks, 0, (dz / len) * blocks)
    try {
      await this.bot.pathfinder.goto(new goals.GoalNear(
        Math.floor(target.x), Math.floor(p.y), Math.floor(target.z), 3))
    } catch {}
    return { ok: true, fledFrom: hostile.name }
  }

  // Dig a safe 1x2 staircase down. Refuses if the next cell is fluid.
  async digStaircase (depth = 6) {
    this.check()
    let dug = 0
    for (let i = 0; i < depth; i++) {
      this.check()
      const p = this.bot.entity.position
      const feet = this.bot.blockAt(p)
      const below = this.bot.blockAt(p.offset(0, -1, 0))
      const ahead = this.bot.blockAt(p.offset(1, -1, 0))
      if (!below || !ahead) break
      if (/lava|water/.test(below.name) || /lava/.test(ahead.name)) break
      const target = ahead.name === 'air' ? below : ahead
      if (!this.canDig(target)) break
      await this.dig(target)
      // clear headroom too, otherwise the bot cannot step into the new cell
      const head = this.bot.blockAt(p.offset(1, 0, 0))
      if (head && head.name !== 'air' && this.canDig(head)) await this.dig(head)
      await this.collectDrops(5, 900)
      try { await this.goto(p.x + 1, target.position.y, p.z, 1) } catch {}
      dug++
    }
    return { ok: true, dug, y: Math.floor(this.bot.entity.position.y) }
  }

  // Pour water on lava to make obsidian in place. Needs a water bucket and a lava source.
  async waterOnLava (times = 1) {
    this.check()
    let made = 0
    for (let i = 0; i < times; i++) {
      if (!this.has('water_bucket')) {
        const empty = this.bot.inventory.items().find(it => it.name === 'bucket')
        if (empty) {
          const water = this.findBlock('water', 24)
          if (water) {
            await this.goto(water.position.x, water.position.y, water.position.z, 2)
            await this.bot.lookAt(water.position.offset(0, 0, 0), true)
            await this.bot.activateItem()
            await sleep(400)
          }
        }
      }
      if (!this.has('water_bucket')) return { ok: made > 0, made, error: 'no water bucket' }
      const lava = this.findLavaSurface()
      if (!lava) return { ok: made > 0, made, error: 'no lava surface' }
      await this.goto(lava.position.x + 2, lava.position.y + 1, lava.position.z, 2)
      await this.equip('water_bucket')
      await this.bot.lookAt(lava.position.offset(0.5, 1, 0.5), true)
      await this.bot.activateItem()
      await sleep(700)
      made++
    }
    return { ok: true, made }
  }

  findLavaSurface () {
    const lavas = this.findBlocks(['lava'], 32, 30)
    return lavas.find(b => {
      const above = this.bot.blockAt(b.position.offset(0, 1, 0))
      return above && above.name === 'air'
    }) || null
  }

  // Find a place to build a nether portal near the bot: a 4x5 plane of air with solid ground
  // under the bottom row and standing room in front. Prefers the nearest valid site.
  findPortalSite ({ plane = 'x' } = {}) {
    const p = this.bot.entity.position
    const solid = b => b && b.name !== 'air' && !/water|lava|fire/.test(b.name)
    const air = b => b && b.name === 'air'
    for (let r = 2; r <= 10; r++) {
      for (const [dx, dz] of [[r, 0], [-r, 0], [0, r], [0, -r], [r, r], [-r, -r], [r, -r], [-r, r]]) {
        const bx = Math.floor(p.x) + dx
        const bz = Math.floor(p.z) + dz
        for (let dy = -2; dy <= 1; dy++) {
          const by = Math.floor(p.y) + dy
          const at = (d, h) => plane === 'x' ? this.bot.blockAt(new (require('vec3'))(bx, by + h, bz + d))
            : this.bot.blockAt(new (require('vec3'))(bx + d, by + h, bz))
          let ok = true
          for (let d = 0; d < 4 && ok; d++) {
            if (!air(at(d, 0))) ok = false
            if (!air(at(d, 4))) ok = false
            if (d === 0 || d === 3) for (let h = 1; h <= 3; h++) if (!air(at(d, h))) ok = false
            const ground = plane === 'x' ? this.bot.blockAt(new (require('vec3'))(bx, by - 1, bz + d))
              : this.bot.blockAt(new (require('vec3'))(bx + d, by - 1, bz))
            if (!solid(ground)) ok = false
          }
          // interior must be open
          for (let d = 1; d <= 2; d++) for (let h = 1; h <= 3; h++) if (!air(at(d, h))) ok = false
          if (!ok) continue
          // stand in front of the plane, not inside it
          const front = plane === 'x' ? { x: bx + 1, y: by, z: bz + 1 } : { x: bx + 1, y: by, z: bz + 1 }
          return { x: bx, y: by, z: bz, plane, front }
        }
      }
    }
    return null
  }

  // Build a nether portal frame out of obsidian at a surveyed site. `plane` is the axis the
  // frame is flat on: 'x' = fixed x, spans z (this seed's entry portal); 'z' = fixed z, spans x.
  // (x, y, z) is the bottom-min corner. Placing only into air keeps an existing partial frame.
  async buildPortalFrame ({ x, y, z, plane = 'x' }) {
    this.check()
    if (!this.has('obsidian', 1)) return { ok: false, error: 'no obsidian in inventory' }
    const at = (dz, dy) => plane === 'x'
      ? { x: Math.round(x), y: Math.round(y + dy), z: Math.round(z + dz) }
      : { x: Math.round(x + dz), y: Math.round(y + dy), z: Math.round(z) }
    const targets = []
    for (const dz of [0, 1, 2, 3]) targets.push(at(dz, 0))
    for (const dz of [0, 1, 2, 3]) targets.push(at(dz, 4))
    for (const dy of [1, 2, 3]) { targets.push(at(0, dy)); targets.push(at(3, dy)) }

    const placed = []
    const failed = []
    for (const t of targets) {
      this.check()
      const cur = this.bot.blockAt(new (require('vec3'))(t.x, t.y, t.z))
      if (cur && cur.name === 'obsidian') continue
      if (cur && cur.name === 'crying_obsidian') { failed.push({ ...t, reason: 'crying_obsidian' }); continue }
      if (cur && cur.name !== 'air') {
        // a tree or grass in the way: clear what a player could clear
        if (/log|leaves|grass|fern|flower|dirt|gravel|snow/.test(cur.name)) {
          try { await this.dig(cur) } catch (e) { failed.push({ ...t, reason: `clear failed: ${e.message}` }); continue }
        } else { failed.push({ ...t, reason: `occupied by ${cur.name}` }); continue }
      }
      if (this.bot.entity.position.distanceTo(new (require('vec3'))(t.x, t.y, t.z)) > 4) {
        try { await this.goto(t.x, t.y, t.z, 3) } catch {}
      }
      let ok = false
      for (let attempt = 0; attempt < 4 && !ok; attempt++) {
        await this.equip('obsidian')
        const faces = [[0, -1, 0, 0, 1, 0], [0, 1, 0, 0, -1, 0], [0, 0, 1, 0, 0, -1], [0, 0, -1, 0, 0, 1],
          [1, 0, 0, -1, 0, 0], [-1, 0, 0, 1, 0, 0]]
        const [ox, oy, oz, fx, fy, fz] = faces[attempt % faces.length]
        const ref = this.bot.blockAt(new (require('vec3'))(t.x + ox, t.y + oy, t.z + oz))
        if (!ref || ref.name === 'air' || ref.name === 'obsidian') continue
        try {
          await this.bot.lookAt(ref.position.offset(0.5 + fx, 0.5 + fy, 0.5 + fz))
          await this.bot.placeBlock(ref, new (require('vec3'))(fx, fy, fz))
          await sleep(180)
        } catch {}
        const got = this.bot.blockAt(new (require('vec3'))(t.x, t.y, t.z))
        ok = !!got && got.name === 'obsidian'
      }
      if (ok) placed.push(t); else failed.push({ ...t, reason: 'placement failed' })
    }
    return { ok: failed.length === 0, placed: placed.length, failed, targets: targets.length }
  }

  async buildAndLightPortal (args = {}) {
    this.check()
    if (!this.has('flint_and_steel')) {
      if (this.has('flint') && this.has('iron_ingot')) {
        const crafted = await this.craft('flint_and_steel', 1)
        if (!crafted.ok) return { ok: false, error: `cannot craft flint_and_steel: ${crafted.error}` }
      } else {
        return { ok: false, error: 'need flint + iron_ingot for flint_and_steel' }
      }
    }
    const site = args.x != null ? { x: args.x, y: args.y, z: args.z, plane: args.plane || 'x' } : this.findPortalSite({ plane: args.plane || 'x' })
    if (!site) return { ok: false, error: 'no clear 4x5 site near the bot' }
    let frame = await this.buildPortalFrame(site)
    if (!frame.ok && frame.failed && frame.failed.length) {
      // retry once at the same site: placement can miss while the server catches up
      await sleep(400)
      frame = await this.buildPortalFrame(site)
    }
    if (!frame.ok) return { ok: false, error: 'frame incomplete', site, frame }
    await this.goto(site.x, site.y, site.z, 3)
    const lit = await this.lightPortal()
    const entered = lit.ok ? await this.enterPortal() : { ok: false, error: lit.error }
    return { ok: entered.ok, site, frame, lit, entered, dimension: this.bot.game.dimension }
  }

  async lightPortal () {
    this.check()
    const portal = this.findBlock('nether_portal', 16)
    if (portal) return { ok: true, skipped: true, note: 'portal already lit' }
    let igniter = this.bot.inventory.items().find(i => /flint_and_steel|fire_charge/.test(i.name))
    if (!igniter) return { ok: false, error: 'no flint_and_steel or fire_charge' }
    await this.equip(igniter.name)
    // find the bottom frame block whose top face opens into the portal interior
    const obsidian = this.findBlocks(['obsidian'], 16, 40)
    let frame = obsidian.find(b => {
      const above = this.bot.blockAt(b.position.offset(0, 1, 0))
      const above2 = this.bot.blockAt(b.position.offset(0, 2, 0))
      const below = this.bot.blockAt(b.position.offset(0, -1, 0))
      return above && above.name === 'air' && above2 && above2.name === 'air' &&
        below && below.name !== 'air' && below.name !== 'obsidian'
    })
    if (!frame) {
      // fallback: lowest obsidian with air above (bottom row)
      frame = obsidian.sort((a, b) => a.position.y - b.position.y).find(b => {
        const above = this.bot.blockAt(b.position.offset(0, 1, 0))
        return above && above.name === 'air'
      })
    }
    if (!frame) return { ok: false, error: 'no obsidian frame' }
    await this.goto(frame.position.x, frame.position.y, frame.position.z, 3)
    await this.bot.lookAt(frame.position.offset(0, 1, 0), true)
    await this.bot.activateItem()
    await sleep(900)
    return { ok: !!this.findBlock('nether_portal', 16), note: 'lit frame' }
  }

  async enterPortal (ms = 15000) {
    const t0 = Date.now()
    const dim0 = this.bot.game.dimension
    const portal = this.findBlock('nether_portal', 24)
    if (!portal) return { ok: false, error: 'no portal in range' }
    try {
      await this.goto(portal.position.x, portal.position.y, portal.position.z, 1)
    } catch {}
    while (Date.now() - t0 < ms) {
      this.check()
      if (this.bot.game.dimension !== dim0) return { ok: true, dimension: this.bot.game.dimension }
      await sleep(500)
    }
    return { ok: false, error: 'portal did not transfer' }
  }

  // Barter with piglins. Gold armor is checked and logged because aggro is the classic miss.
  async barter (ingots = 4) {
    this.check()
    const gold = this.bot.inventory.items().find(i => i.name === 'gold_ingot')
    if (!gold) return { ok: false, error: 'no gold_ingot' }
    const protectedByGold = this.bot.inventory.slots.some(s => s && /golden_(helmet|chestplate|leggings|boots)/.test(s.name))
    if (!protectedByGold) this.log({ type: 'warn', msg: 'bartering without gold armor: piglins will aggro' })
    let done = 0
    const t0 = Date.now()
    while (done < ingots && Date.now() - t0 < 60000) {
      this.check()
      const pig = this.bot.nearestEntity(e => e.name === 'piglin' &&
        e.position.distanceTo(this.bot.entity.position) < 12)
      if (!pig) break
      const count = Math.min(this.count('gold_ingot'), ingots - done)
      if (count <= 0) break
      await this.equip('gold_ingot')
      const d = pig.position.distanceTo(this.bot.entity.position)
      if (d > 3) {
        try {
          await this.bot.pathfinder.goto(new goals.GoalNear(
            Math.floor(pig.position.x), Math.floor(pig.position.y), Math.floor(pig.position.z), 2))
        } catch {}
      }
      await this.bot.lookAt(pig.position.offset(0, 1, 0), true)
      for (let i = 0; i < count; i++) {
        try { await this.bot.activateEntity(pig) } catch {}
        await sleep(320)
        done++
      }
      await sleep(1200)
      await this.collectDrops(10, 3000)
    }
    return { ok: done > 0, barters: done, pearls: this.count('ender_pearl'), goldArmor: protectedByGold }
  }

  // Throw an eye of ender and read its travel direction. The eye entity's velocity is the
  // direction of the stronghold, which is what Ninjabrain Bot uses instead of chasing eyes.
  async throwEye (timeoutMs = 6000) {
    this.check()
    if (!this.has('ender_eye')) return { ok: false, error: 'no ender_eye' }
    await this.equip('ender_eye')
    const p = this.bot.entity.position
    const before = new Set(Object.keys(this.bot.entities))
    await this.bot.activateItem()
    const t0 = Date.now()
    let eye = null
    while (Date.now() - t0 < timeoutMs) {
      this.check()
      eye = Object.values(this.bot.entities).find(e =>
        e.name === 'eye_of_ender' && !before.has(String(e.id)))
      if (eye) break
      await sleep(50)
    }
    if (!eye) return { ok: false, error: 'no eye entity observed' }
    // sample velocity for a few ticks
    let vx = 0, vz = 0, n = 0
    for (let i = 0; i < 6; i++) {
      const v = eye.velocity
      if (v && (Math.abs(v.x) + Math.abs(v.z)) > 0.01) { vx += v.x; vz += v.z; n++ }
      await sleep(50)
    }
    if (!n) return { ok: false, error: 'eye entity had no velocity' }
    vx /= n; vz /= n
    const yaw = Math.atan2(-vx, vz) * 180 / Math.PI
    return {
      ok: true, yaw: +yaw.toFixed(1), from: { x: +p.x.toFixed(1), z: +p.z.toFixed(1) },
      note: 'yaw convention: 0=+Z, 90=-X, 180=-Z, 270=+X'
    }
  }

  async smelt (inputName, count = 1) {
    this.check()
    let furnaceBlock = this.findBlock('furnace', 24)
    if (!furnaceBlock) return { ok: false, error: 'no furnace nearby (put one down first)' }
    if (this.bot.entity.position.distanceTo(furnaceBlock.position) > 4) {
      await this.goto(furnaceBlock.position.x, furnaceBlock.position.y, furnaceBlock.position.z, 2)
    }
    const furnace = await this.bot.openFurnace(furnaceBlock)
    try {
      const input = this.bot.inventory.items().find(i => i.name === inputName)
      if (!input) return { ok: false, error: `no ${inputName}` }
      await furnace.putInput(input.type, null, Math.min(count, input.count))
      const fuel = this.bot.inventory.items().find(i => /coal|planks|log|stick/.test(i.name))
      if (fuel) await furnace.putFuel(fuel.type, null, 1)
      await sleep(200)
      const t0 = Date.now()
      while (Date.now() - t0 < 15000) {
        const out = furnace.outputItem()
        if (out) { await furnace.takeOutput(); break }
        await sleep(500)
      }
    } finally {
      furnace.close()
    }
    return { ok: true }
  }

  // Withdraw everything from the nearest chest. The route chests are supply caches; a pro takes
  // the obsidian/flint/tool and leaves the junk, so junk is dropped later by drop_junk.
  async lootChest () {
    this.check()
    const chest = this.findBlock('chest', 24)
    if (!chest) return { ok: false, error: 'no chest nearby' }
    if (this.bot.entity.position.distanceTo(chest.position) > 4) {
      await this.goto(chest.position.x, chest.position.y, chest.position.z, 2)
    }
    const c = await this.bot.openContainer(chest)
    const got = []
    try {
      for (const it of c.containerItems()) {
        try {
          await c.withdraw(it.type, null, it.count)
          got.push(`${it.name}x${it.count}`)
        } catch (e) { /* full inventory or race */ }
      }
    } finally { c.close() }
    return { ok: got.length > 0, got, chest: { ...chest.position } }
  }

  async openChestAndTake (names, count = 1) {
    this.check()
    const chest = this.findBlock('chest', 24)
    if (!chest) return { ok: false, error: 'no chest nearby' }
    if (this.bot.entity.position.distanceTo(chest.position) > 4) {
      await this.goto(chest.position.x, chest.position.y, chest.position.z, 2)
    }
    const c = await this.bot.openContainer(chest)
    const got = []
    try {
      for (const n of [].concat(names)) {
        const it = c.containerItems().find(i => i.name === n)
        if (it) { await c.withdraw(it.type, null, Math.min(count, it.count)); got.push(n) }
      }
    } finally { c.close() }
    return { ok: got.length > 0, got }
  }

  async dropJunk (keep = []) {
    const keepSet = new Set(keep)
    let dropped = 0
    for (const it of this.bot.inventory.items()) {
      if (keepSet.has(it.name)) continue
      if (/rotten_flesh|poisonous_potato|spider_eye|bone|string|feather|flint|gravel|dirt|cobblestone/.test(it.name)) {
        try { await this.bot.toss(it.type, null, it.count); dropped += it.count } catch {}
      }
    }
    return { ok: true, dropped }
  }
}

// Registry handed to the LLM. Descriptions are the contract: the model may only pick from here.
const REGISTRY = {
  goto: {
    args: { x: 'number', y: 'number', z: 'number', range: 'number=2' },
    desc: 'pathfind to coordinates (Baritone-style, avoids lava, max 3 block drops)'
  },
  collect_wood: { args: { count: 'number=8' }, desc: 'find and chop logs, collect drops' },
  craft: { args: { name: 'item id', count: 'number=1' }, desc: 'craft an item, placing/using a crafting table if needed' },
  ensure_pickaxe: { args: { tier: 'wooden|stone|iron|diamond=wooden' }, desc: 'craft a pickaxe from available materials' },
  ensure_sword: { args: { tier: 'wooden|stone|iron|diamond=wooden' }, desc: 'craft a sword' },
  ensure_axe: { args: { tier: 'wooden|stone|iron|diamond=wooden' }, desc: 'craft an axe' },
  dig_staircase: { args: { depth: 'number=6' }, desc: 'safe 1x2 staircase down, collects drops' },
  mine_blocks: { args: { names: 'block id or array', count: 'number=1' }, desc: 'mine specific blocks (e.g. iron_ore, gravel)' },
  eat: { args: {}, desc: 'eat best available food' },
  attack: { args: { kind: 'hostile|mob name=hostile', maxRange: 'number=4' }, desc: 'melee nearest hostile; aborts at low health' },
  flee: { args: { blocks: 'number=16' }, desc: 'run away from the nearest hostile' },
  water_on_lava: { args: { times: 'number=1' }, desc: 'pour water on lava to create obsidian (needs bucket)' },
  light_portal: { args: {}, desc: 'use flint and steel on an obsidian frame' },
  build_portal_frame: { args: { x: 'number (bottom-min corner)', y: 'number', z: 'number', plane: 'x|z=x' }, desc: 'place obsidian into a partial nether portal frame at a surveyed site' },
  build_portal: { args: { x: 'number?', y: 'number?', z: 'number?', plane: 'x|z=x' }, desc: 'craft an igniter if needed, build a 4x5 obsidian frame at a clear site, light it and enter the Nether' },
  enter_portal: { args: {}, desc: 'walk into a nether portal and wait for the dimension change' },
  barter: { args: { ingots: 'number=4' }, desc: 'barter gold ingots with piglins; warns if no gold armor' },
  throw_eye: { args: {}, desc: 'throw an eye of ender and return its bearing (for triangulation)' },
  smelt: { args: { input: 'item id', count: 'number=1' }, desc: 'smelt in a nearby furnace' },
  take_from_chest: { args: { names: 'item id or array', count: 'number=1' }, desc: 'withdraw specific items from a nearby chest' },
  loot_chest: { args: {}, desc: 'withdraw everything from the nearest chest (supply cache)' },
  drop_junk: { args: {}, desc: 'drop worthless items to free inventory' },
  stop: { args: {}, desc: 'stop the run: goal reached or provably blocked' }
}

module.exports = { Skills, REGISTRY, LOG_NAMES, FOOD, PICKAXE, AXE, SHOVEL, SWORD }
