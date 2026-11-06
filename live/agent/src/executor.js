// Executor: runs one skill with a hard timeout, cancels the bot's motion on timeout, and
// returns a normalized result. This is what keeps a stuck pathfinder from eating the run.
const { Skills } = require('./skills')

// Model output is untrusted: clamp numeric args so "count":80 cannot turn into an 80-block
// detour (a real classifier output we observed).
const clamp = (v, lo, hi, d) => {
  const n = Number(v)
  return Number.isFinite(n) ? Math.max(lo, Math.min(hi, n)) : d
}

// Registry name -> internal method. Keeps the LLM contract (snake_case, args object) separate
// from the implementation (positional helpers that are also called internally).
const DISPATCH = {
  goto: (s, a) => s.goto(a.x, a.y, a.z, a.range ?? 2),
  collect_wood: (s, a) => s.ensureWood(clamp(a.count, 1, 16, 8)),
  craft: (s, a) => {
    // a tool request implies its intermediates (planks, sticks); models skip that step
    const m = String(a.name || '').match(/^(wooden|stone|iron|golden|diamond)_(pickaxe|axe|sword|shovel)$/)
    if (m) {
      const tier = m[1]
      if (m[2] === 'pickaxe') return s.ensurePickaxe(tier)
      if (m[2] === 'axe') return s.ensureAxe(tier)
      if (m[2] === 'sword') return s.ensureSword(tier)
    }
    return s.craft(a.name, clamp(a.count, 1, 8, 1))
  },
  ensure_pickaxe: (s, a) => s.ensurePickaxe(a.tier || 'wooden'),
  ensure_sword: (s, a) => s.ensureSword(a.tier || 'wooden'),
  ensure_axe: (s, a) => s.ensureAxe(a.tier || 'wooden'),
  dig_staircase: (s, a) => s.digStaircase(clamp(a.depth, 1, 12, 6)),
  mine_blocks: (s, a) => s.collectBlocks([].concat(a.names || a.block || []), clamp(a.count, 1, 16, 1)),
  eat: s => s.eat(),
  attack: (s, a) => s.attackNearest(a.kind || 'hostile', a.maxRange ?? 4),
  flee: (s, a) => s.flee(clamp(a.blocks, 4, 32, 16)),
  water_on_lava: (s, a) => s.waterOnLava(clamp(a.times, 1, 10, 1)),
  light_portal: s => s.lightPortal(),
  build_portal_frame: (s, a) => s.buildPortalFrame({ x: a.x, y: a.y, z: a.z, plane: a.plane || 'x' }),
  build_portal: (s, a) => s.buildAndLightPortal(a),
  enter_portal: s => s.enterPortal(),
  barter: (s, a) => s.barter(clamp(a.ingots, 1, 32, 4)),
  throw_eye: s => s.throwEye(),
  smelt: (s, a) => s.smelt(a.input, clamp(a.count, 1, 16, 1)),
  take_from_chest: (s, a) => s.openChestAndTake(a.names, clamp(a.count, 1, 16, 1)),
  loot_chest: s => s.lootChest(),
  drop_junk: s => s.dropJunk(),
  stop: () => ({ ok: true, stopped: true })
}

class Executor {
  constructor ({ bot, mcData, observer, log, timeoutMs = 120000 }) {
    this.skills = new Skills({ bot, mcData, observer, log })
    this.bot = bot
    this.log = log
    this.timeoutMs = timeoutMs
    this.busy = false
    this.current = null
  }

  cancel () {
    try { this.skills.cancel() } catch {}
  }

  call (name, args = {}) {
    const fn = DISPATCH[name]
    if (!fn) throw new Error(`unknown skill ${name}`)
    return fn(this.skills, args || {})
  }

  async run (action, { timeoutMs } = {}) {
    if (this.busy) return { ok: false, error: 'executor busy' }
    const limit = timeoutMs || this.timeoutMs
    const name = action.name
    const args = action.args || {}
    const t0 = Date.now()
    this.busy = true
    this.current = name
    this.skills.reset()
    this.log({ type: 'skill_start', skill: name, args, timeoutMs: limit })
    let timer
    try {
      const result = await Promise.race([
        this.call(name, args),
        new Promise((_, reject) => {
          timer = setTimeout(() => {
            this.cancel()
            reject(new Error(`timeout after ${limit}ms`))
          }, limit)
        })
      ])
      const out = { ok: result?.ok !== false, skill: name, args, ms: Date.now() - t0, result }
      this.log({ type: 'skill_result', ...out })
      return out
    } catch (err) {
      const out = { ok: false, skill: name, args, ms: Date.now() - t0, error: String(err.message) }
      this.log({ type: 'skill_result', ...out })
      return out
    } finally {
      clearTimeout(timer)
      this.busy = false
      this.current = null
    }
  }
}

module.exports = { Executor }
