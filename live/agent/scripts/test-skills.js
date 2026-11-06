#!/usr/bin/env node
// Deterministic skills smoke test. No LLM: proves the hands work.
//   node scripts/test-skills.js wood        -> collect_wood(6)
//   node scripts/test-skills.js tools       -> wood + crafting table + wooden pickaxe
//   node scripts/test-skills.js iron        -> stone pickaxe + mine iron (needs stone)
const mineflayer = require('mineflayer')
const { pathfinder, Movements } = require('mineflayer-pathfinder')
const mcDataFor = require('minecraft-data')
const config = require('../src/config')
const { Observer } = require('../src/observe')
const { Executor } = require('../src/executor')

const mode = process.argv[2] || 'wood'
const bot = mineflayer.createBot({
  host: config.mc.host, port: config.mc.port, username: config.mc.username,
  version: config.mc.version, auth: 'offline'
})
bot.loadPlugin(pathfinder)

const log = ev => {
  if (ev.type === 'skill_start') console.log(`> ${ev.skill} ${JSON.stringify(ev.args || {})}`)
  else if (ev.type === 'skill_result') console.log(`  ${ev.ok ? 'ok' : 'FAIL'} ${Math.round(ev.ms / 1000)}s ${ev.error || JSON.stringify(ev.result || {}).slice(0, 200)}`)
  else if (ev.type === 'skill_warn') console.log('  warn', ev.error)
  else if (ev.type === 'warn') console.log('  warn', ev.msg)
}

bot.once('spawn', async () => {
  const mc = mcDataFor(bot.version)
  const mv = new Movements(bot, mc)
  mv.canDig = true; mv.maxDropDown = 3; mv.allowSprinting = true
  bot.pathfinder.setMovements(mv)
  const observer = new Observer(bot, mc)
  const ex = new Executor({ bot, mcData: mc, observer, log, timeoutMs: 120000 })
  const t0 = Date.now()
  const steps = {
    wood: [['collect_wood', { count: 6 }]],
    tools: [
      ['collect_wood', { count: 6 }],
      ['craft', { name: 'crafting_table', count: 1 }],
      ['ensure_pickaxe', { tier: 'wooden' }],
      ['ensure_axe', { tier: 'wooden' }]
    ],
    iron: [
      ['ensure_pickaxe', { tier: 'wooden' }],
      ['dig_staircase', { depth: 5 }],
      ['ensure_pickaxe', { tier: 'stone' }],
      ['mine_blocks', { names: 'iron_ore', count: 3 }]
    ]
  }[mode] || []
  for (const [name, args] of steps) {
    const r = await ex.run({ name, args })
    if (!r.ok && mode !== 'wood') console.log('  stopping after failure')
  }
  const s = observer.snapshot()
  console.log('\n--- final ---')
  console.log(observer.compact(s))
  console.log(`inventory: ${s.inventory.items.map(i => `${i.name}x${i.count}`).join(', ') || 'empty'}`)
  console.log(`elapsed ${Math.round((Date.now() - t0) / 1000)}s`)
  bot.quit(); process.exit(0)
})

bot.on('error', e => console.error('ERR', e.message))
setTimeout(() => { console.error('TIMEOUT'); process.exit(1) }, 300000)
