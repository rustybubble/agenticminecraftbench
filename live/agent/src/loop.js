// Main loop: reflexes (250ms) -> classifier (idle, ~1-3s) -> planner (rare) -> skill -> log.
// Every decision and every result is appended to runs/<id>/events.jsonl with wall + game time,
// which is the artifact Person A consumes to diff our live run against the pro splits.
const fs = require('fs')
const path = require('path')
const mineflayer = require('mineflayer')
const { pathfinder, Movements, goals } = require('mineflayer-pathfinder')
const mcDataFor = require('minecraft-data')

const config = require('./config')
const { Observer } = require('./observe')
const { Executor } = require('./executor')
const { plan } = require('./planner')
const { classify } = require('./router')
const { routeState, detectSplit, SPLITS } = require('./route')
const { SPLIT_TARGETS } = require('./math')

const sleep = ms => new Promise(r => setTimeout(r, ms))

class Run {
  constructor (opts = {}) {
    this.opts = opts
    this.runId = opts.runId || `run-${new Date().toISOString().replace(/[:.]/g, '-')}`
    this.dir = path.join(config.paths.runs, this.runId)
    fs.mkdirSync(this.dir, { recursive: true })
    this.events = fs.createWriteStream(path.join(this.dir, 'events.jsonl'), { flags: 'a' })
    this.startedAt = Date.now()
    this.deaths = 0
    this.actions = 0
    this.failures = 0
    this.consecutiveFailures = 0
    this.recent = []
    this.memory = []
    this.lastResult = null
    this.lastPlanAt = 0
    this.currentSplit = null
    this.splitLog = []
    this.running = true
    this.goal = opts.goal || null
    this.compactCache = null
    this.llmCalls = 0
    this.urgency = null
    this.stuckSince = null
    this.lastPos = null
    this.lastDeadAt = 0
    this.wake = null
  }

  log (ev) {
    const rec = { ts: new Date().toISOString(), epoch: Date.now(), ...ev }
    try { this.events.write(JSON.stringify(rec) + '\n') } catch {}
    if (ev.type === 'decision' || ev.type === 'skill_result' || ev.type === 'warn' ||
        ev.type === 'death' || ev.type === 'split' || ev.type === 'error') {
      const tag = ev.type.toUpperCase()
      const extra = ev.skill ? `${ev.skill}${ev.error ? ' ERR:' + ev.error : ''}` : (ev.msg || ev.split || '')
      console.log(`[${new Date().toISOString().slice(11, 19)}] ${tag} ${extra}`)
    }
    this.recent.push({ t: Date.now(), msg: `${ev.type}:${ev.skill || ev.msg || ev.split || ''}` })
    if (this.recent.length > 40) this.recent.shift()
  }

  async connect () {
    const bot = this.bot = mineflayer.createBot({
      host: config.mc.host,
      port: config.mc.port,
      username: config.mc.username,
      version: config.mc.version,
      auth: 'offline',
      hideErrors: false
    })
    bot.loadPlugin(pathfinder)
    this.mcData = mcDataFor(bot.version)
    this.observer = new Observer(bot, this.mcData)

    bot.once('spawn', () => {
      const movements = new Movements(bot, this.mcData)
      movements.canDig = true
      movements.allow1by1towers = true
      movements.allowParkour = true
      movements.allowSprinting = true
      movements.maxDropDown = 3
      movements.dontMineUnderFallingBlock = true
      // rmalde notes + our own run: the bot walks into ponds and sinks. Make liquid impassable
      // for the pathfinder and handle "already in water" in the reflex loop.
      movements.liquidCost = -1
      movements.infiniteLiquidDropdownDistance = false
      const avoid = ['lava', 'fire', 'magma_block', 'cactus', 'sweet_berry_bush', 'powder_snow']
      movements.blocksToAvoid = new Set(avoid.map(n => this.mcData.blocksByName[n]?.id).filter(x => x != null))
      bot.pathfinder.setMovements(movements)
      this.executor = new Executor({
        bot, mcData: this.mcData, observer: this.observer,
        log: ev => this.log(ev),
        timeoutMs: config.loop.skillTimeoutMs
      })
      this.log({ type: 'spawn', pos: bot.entity.position, dimension: bot.game.dimension, version: bot.version })
      this.ready = true
    })

    bot.on('death', () => {
      this.deaths++
      this.lastDeadAt = Date.now()
      this.log({ type: 'death', pos: this.bot.entity?.position, total: this.deaths })
    })
    bot.on('kicked', r => this.log({ type: 'kicked', reason: String(r).slice(0, 300) }))
    bot.on('error', e => this.log({ type: 'error', msg: String(e.message).slice(0, 300) }))
    bot.on('end', () => { this.running = false; this.log({ type: 'disconnect' }) })
    bot.on('chat', (username, message) => {
      if (username === bot.username) return
      if (message.startsWith('!')) this.command(message.slice(1).trim())
    })
    return bot
  }

  // Chat control for the demo: a human in the Prism client can drive the bot.
  async command (line) {
    const [cmd, ...rest] = line.split(/\s+/)
    const num = (i, d) => (rest[i] === undefined ? d : Number(rest[i]))
    this.log({ type: 'command', msg: line })
    switch (cmd) {
      case 'state': {
        const s = this.observer.snapshot({ recent: this.recent })
        console.log(this.observer.compact(s))
        this.bot.chat(`split=${detectSplit(s)} pos=${Math.round(s.pos.x)},${Math.round(s.pos.y)},${Math.round(s.pos.z)} hp=${s.health} food=${s.food}`)
        break
      }
      case 'wood': return this.force({ name: 'collect_wood', args: { count: num(0, 8) } })
      case 'pick': return this.force({ name: 'ensure_pickaxe', args: { tier: rest[0] || 'wooden' } })
      case 'table': return this.force({ name: 'craft', args: { name: 'crafting_table', count: 1 } })
      case 'goto': return this.force({ name: 'goto', args: { x: num(0, 0), y: num(1, 64), z: num(2, 0), range: num(3, 2) } })
      case 'eat': return this.force({ name: 'eat', args: {} })
      case 'flee': return this.force({ name: 'flee', args: {} })
      case 'mine': return this.force({ name: 'mine_blocks', args: { names: rest, count: 1 } })
      case 'plan': return this.planNow(true)
      case 'stop': this.executor.cancel(); break
      default: this.bot.chat(`unknown command ${cmd}`)
    }
  }

  async force (action) {
    if (this.executor.busy) return this.bot.chat('busy')
    this.log({ type: 'decision', source: 'manual', skill: action.name, args: action.args, why: 'human command' })
    const res = await this.executor.run(action, { timeoutMs: Math.min(config.loop.skillTimeoutMs, 90000) })
    this.lastResult = res
    this.bot.chat(`${action.name}: ${res.ok ? 'ok' : 'FAIL'} ${res.error || ''} ${Math.round(res.ms / 1000)}s`)
    return res
  }

  splitUpdate (state) {
    const split = detectSplit(state)
    if (split !== this.currentSplit) {
      const prev = this.currentSplit
      this.currentSplit = split
      const rec = {
        split, prev, elapsedS: Math.round((Date.now() - this.startedAt) / 1000),
        targetS: SPLIT_TARGETS[split] ?? null, at: new Date().toISOString()
      }
      this.splitLog.push(rec)
      this.log({ type: 'split', ...rec })
      fs.writeFileSync(path.join(this.dir, 'splits.json'), JSON.stringify({
        runId: this.runId, startedAt: new Date(this.startedAt).toISOString(), splits: this.splitLog
      }, null, 2))
    }
    return split
  }

  calculators (state) {
    const { enderRequirement, barterMath, portalTarget, triangulate } = require('./math')
    const out = {}
    const pearls = state.inventory.items.find(i => i.name === 'ender_pearl')?.count || 0
    const rods = state.inventory.items.find(i => i.name === 'blaze_rod')?.count || 0
    out.eyes = enderRequirement({ pearls, rods })
    out.barter = barterMath(16)
    if (this.eyeThrows && this.eyeThrows.length >= 2) out.triangulation = triangulate(this.eyeThrows)
    if (state.dimension === 'overworld' && state.blocks?.netherPortal) {
      out.portalTarget = portalTarget(state.blocks.netherPortal)
    }
    return out
  }

  async step () {
    if (!this.ready || this.executor.busy || !this.bot.entity) return
    if (Date.now() - this.lastDeadAt < 3000) return

    const state = this.observer.snapshot({
      recent: this.recent, goal: this.goal
    })
    const split = this.splitUpdate(state)
    const route = routeState(state, this.startedAt)
    const compact = this.observer.compact(state)
    const failedTwice = this.consecutiveFailures >= 2
    const splitChanged = this.lastSplitSeen !== split
    const due = Date.now() - this.lastPlanAt > config.loop.plannerEveryMs
    const wantPlanner = this.opts.autoPlanner !== false &&
      (!this.lastPlanAt || failedTwice || splitChanged || due || this.urgency === 'high')
    this.lastSplitSeen = split

    let action = null
    let source = null
    try {
      if (wantPlanner) {
        source = 'planner'
        const p = await plan({
          state, compact, route, calculators: this.calculators(state),
          last: this.lastResult, memory: this.memory
        })
        this.lastPlanAt = Date.now()
        if (p.memory) this.memory.push(p.memory)
        if (p.done) {
          this.log({ type: 'run_end', reason: 'planner_done', why: p.why, elapsedS: Math.round((Date.now() - this.startedAt) / 1000) })
          this.running = false
          return
        }
        action = p.skill
        this.log({
          type: 'decision', source, skill: p.skill.name, args: p.skill.args,
          why: p.why, risk: p.risk, split: p.split, ms: p.ms, model: p.model,
          fallback: p.fallback, usage: p.usage
        })
        this.urgency = null
      } else {
        source = 'classifier'
        const c = await classify({ compact, split, last: this.lastResult })
        action = { name: c.name, args: c.args }
        this.log({
          type: 'decision', source, skill: c.name, args: c.args, why: c.why,
          urgency: c.urgency, ms: c.ms, model: c.model
        })
        if (c.urgency === 'high') this.urgency = 'high'
      }
    } catch (err) {
      this.log({ type: 'error', msg: `decision failed: ${String(err.message).slice(0, 300)}` })
      // deterministic fallback so the bot never just stands still
      action = this.fallbackAction(state, split)
      source = 'fallback'
      this.log({ type: 'decision', source, skill: action.name, args: action.args, why: 'LLM unavailable' })
    }

    if (!action) return
    this.actions++
    const res = await this.executor.run(action)
    this.lastResult = { ...res, result: summarise(res.result) }
    if (res.ok) this.consecutiveFailures = 0
    else this.consecutiveFailures++
    if (!res.ok) this.failures++
    await sleep(150)
  }

  fallbackAction (state, split) {
    if (state.danger.lavaWithin3) return { name: 'flee', args: { blocks: 12 } }
    if (state.health <= 8 && state.inventory.items.some(i => /cooked|bread|apple|carrot/.test(i.name))) return { name: 'eat', args: {} }
    if (split === 'wood' || split === 'spawn') return { name: 'collect_wood', args: { count: 6 } }
    if (split === 'stone') return { name: 'dig_staircase', args: { depth: 4 } }
    if (split === 'iron') return { name: 'mine_blocks', args: { names: 'iron_ore', count: 3 } }
    if (split === 'portal') return { name: 'light_portal', args: {} }
    if (split === 'pearls') return { name: 'barter', args: { ingots: 4 } }
    if (split === 'rods') return { name: 'attack', args: { kind: 'blaze' } }
    if (split === 'stronghold' || split === 'end') return { name: 'throw_eye', args: {} }
    return { name: 'collect_wood', args: { count: 4 } }
  }

  async planNow (verbose = false) {
    const state = this.observer.snapshot({ recent: this.recent, goal: this.goal })
    const route = routeState(state, this.startedAt)
    const compact = this.observer.compact(state)
    const p = await plan({
      state, compact, route, calculators: this.calculators(state),
      last: this.lastResult, memory: this.memory
    })
    this.log({ type: 'decision', source: 'planner_manual', skill: p.skill.name, args: p.skill.args, why: p.why, ms: p.ms })
    if (verbose) {
      console.log('--- compact state ---\n' + compact)
      console.log('--- planner ---\n' + JSON.stringify(p, null, 2))
    }
    return p
  }

  // Reflex layer: runs while a skill is executing. Bounded, deterministic, no tokens.
  startReflexes () {
    this.reflexTimer = setInterval(() => {
      if (!this.ready || !this.bot.entity) return
      const b = this.bot
      const p = b.entity.position
      const lava = this.mcData.blocksByName.lava.id
      let lavaNear = false
      for (let dx = -2; dx <= 2 && !lavaNear; dx++) {
        for (let dy = -1; dy <= 2 && !lavaNear; dy++) {
          for (let dz = -2; dz <= 2; dz++) {
            const bl = b.blockAt(p.offset(dx, dy, dz))
            if (bl && bl.type === lava) { lavaNear = true; break }
          }
        }
      }
      // swim up if the head is under water (pathfinder cannot rescue a sinking bot)
      const feet = b.blockAt(p)
      const head = b.blockAt(p.offset(0, 1.6, 0))
      if (feet && feet.name === 'water' && head && head.name === 'water') {
        try { b.setControlState('jump', true); setTimeout(() => b.setControlState('jump', false), 450) } catch {}
      }
      if (lavaNear) {
        this.urgency = 'high'
        if (b.pathfinder.goal) b.pathfinder.stop()
        try {
          b.setControlState('jump', true)
          b.setControlState('sprint', true)
          b.setControlState('forward', true)
          setTimeout(() => b.clearControlStates(), 700)
        } catch {}
      }
      // stuck detection while a movement skill is running
      const movementSkill = this.executor?.busy && ['goto','collect_wood','flee','dig_staircase','enter_portal','attack'].includes(this.executor.current)
      if (movementSkill && !lavaNear) {
        const moved = this.lastPos ? p.distanceTo(this.lastPos) : 1
        if (moved < 0.15) {
          if (!this.stuckSince) this.stuckSince = Date.now()
          else if (Date.now() - this.stuckSince > 5000 && Date.now() - this.stuckSince < 6500) {
            // jump frees the pathfinder from 1-block lips and fence corners
            try { b.setControlState('jump', true); setTimeout(() => b.setControlState('jump', false), 350) } catch {}
          } else if (Date.now() - this.stuckSince > 20000) {
            this.log({ type: 'warn', msg: `stuck ${Math.round((Date.now() - this.stuckSince) / 1000)}s during ${this.executor.current}` })
            this.executor.cancel()
            this.stuckSince = null
          }
        } else this.stuckSince = null
        this.lastPos = p.clone()
      }
      // emergency survival
      if (b.health <= 6 && this.executor?.busy) {
        const hostile = Object.values(b.entities).find(e => e.position &&
          ['zombie', 'skeleton', 'creeper', 'spider', 'blaze', 'piglin', 'hoglin', 'enderman', 'witch']
            .includes(e.name) && e.position.distanceTo(p) < 6)
        if (hostile) {
          this.log({ type: 'warn', msg: `hp=${b.health} next to ${hostile.name}, aborting skill` })
          this.executor.cancel()
        }
      }
    }, config.loop.reflexMs)
  }

  async loop () {
    this.startReflexes()
    while (this.running) {
      try { await this.step() } catch (e) {
        this.log({ type: 'error', msg: String(e.stack || e.message).slice(0, 500) })
      }
      const elapsed = Date.now() - this.startedAt
      if (this.opts.minutes && elapsed > this.opts.minutes * 60000) {
        this.log({ type: 'run_end', reason: 'time limit', elapsedS: Math.round(elapsed / 1000) })
        break
      }
      await sleep(config.loop.tickMs)
    }
    await this.finish()
  }

  async finish () {
    this.running = false
    clearInterval(this.reflexTimer)
    const summary = {
      runId: this.runId,
      startedAt: new Date(this.startedAt).toISOString(),
      endedAt: new Date().toISOString(),
      elapsedS: Math.round((Date.now() - this.startedAt) / 1000),
      actions: this.actions,
      failures: this.failures,
      deaths: this.deaths,
      splits: this.splitLog,
      finalSplit: this.currentSplit,
      positions: this.bot?.entity?.position ? { ...this.bot.entity.position } : null,
      memory: this.memory
    }
    fs.writeFileSync(path.join(this.dir, 'summary.json'), JSON.stringify(summary, null, 2))
    this.log({ type: 'summary', ...summary })
    this.events.end()
    try { this.bot.quit() } catch {}
    console.log(`\nrun ${this.runId}: ${summary.elapsedS}s, ${summary.actions} actions, ${summary.failures} failures, ${summary.deaths} deaths`)
    console.log(`events: ${path.join(this.dir, 'events.jsonl')}`)
  }
}

function summarise (r) {
  if (!r || typeof r !== 'object') return r
  const out = {}
  for (const k of ['ok', 'got', 'made', 'have', 'dug', 'bought', 'barters', 'pearls', 'yaw', 'killed', 'ate', 'note']) {
    if (r[k] !== undefined) out[k] = r[k]
  }
  return out
}

module.exports = { Run }
