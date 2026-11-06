#!/usr/bin/env node
// Reference-seed route, phase 1: the supply chests the human run loots, then the entry portal.
// Same seed / version / difficulty as rmalde/minecraft-agent (8398967436125155523, 1.16.5,
// Peaceful); coordinates come from that repo's optimization/nether/config.json and were
// re-verified against our server with live/server/verify-groundtruth.js.
//
//   node scripts/play-route.js --viewer --run route-01
const { Run } = require('../src/loop')
const config = require('../src/config')

const route = [
  { step: 'chest_village_weaponsmith', x: -228, y: 71, z: 240 },
  { step: 'chest_west', x: -290, y: 68, z: 253 },
  { step: 'chest_ruined_portal', x: -284, y: 66, z: 262 },
  { step: 'entry_portal_site', x: -285, y: 67, z: 259 }
]

function parseArgs (argv) {
  const out = {}
  for (let i = 0; i < argv.length; i++) if (argv[i].startsWith('--')) {
    const k = argv[i].slice(2)
    out[k] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true
  }
  return out
}

;(async () => {
  const args = parseArgs(process.argv.slice(2))
  const run = new Run({ runId: args.run || `route-${Date.now()}`, autoPlanner: false })
  await run.connect()
  const t0 = Date.now()
  while (!run.ready && Date.now() - t0 < 20000) await new Promise(r => setTimeout(r, 200))
  if (!run.ready) throw new Error('bot did not spawn')

  run.bot.chat('/clear @s')
  await new Promise(r => setTimeout(r, 300))

  if (args.viewer) {
    const { mineflayer: viewer } = require('prismarine-viewer')
    const port = Number(args['viewer-port'] || 3007)
    viewer(run.bot, { port, firstPerson: !args['third-person'], viewDistance: 6 })
    run.log({ type: 'viewer', port })
    console.log(`viewer http://localhost:${port}`)
  }

  run.log({ type: 'route_start', route, seed: config.seed, version: config.mc.version })
  for (const point of route) {
    const isChest = point.step.startsWith('chest')
    run.log({ type: 'route_step', step: point.step, target: { x: point.x, y: point.y, z: point.z }, action: isChest ? 'loot_chest' : 'goto' })
    const go = await run.executor.run({ name: 'goto', args: { x: point.x, y: point.y, z: point.z, range: 2 } }, { timeoutMs: 90000 })
    if (!go.ok) {
      run.log({ type: 'route_warn', step: point.step, error: go.error })
      // short approach segments: the reference repo found long village approaches time out
      await run.executor.run({ name: 'goto', args: { x: point.x, y: point.y, z: point.z, range: 6 } }, { timeoutMs: 45000 })
    }
    if (isChest) {
      const loot = await run.executor.run({ name: 'loot_chest', args: {} }, { timeoutMs: 45000 })
      run.log({ type: 'route_loot', step: point.step, result: loot.result })
      console.log(`${point.step}: ${JSON.stringify(loot.result)}`)
    }
    await new Promise(r => setTimeout(r, 400))
  }

  if (args.portal) {
    // build the 7 missing obsidian into the surveyed frame, light it, go through
    run.log({ type: 'route_step', step: 'build_entry_frame', action: 'build_portal_frame',
      target: { x: -285, y: 66, z: 258, plane: 'x' } })
    const built = await run.executor.run({ name: 'build_portal', args: {} }, { timeoutMs: 240000 })
    console.log('portal:', JSON.stringify(built.result))
    run.log({ type: 'route_portal', result: built.result, dimension: run.bot.game.dimension })
  }

  // what the frame looks like now
  const frame = run.observer.snapshot().blocks
  run.log({ type: 'route_state', obsidian: frame.obsidian, netherPortal: frame.netherPortal })
  const inv = run.bot.inventory.items().map(i => `${i.name}x${i.count}`)
  run.log({ type: 'route_inventory', items: inv })
  console.log('inventory:', inv.join(', '))

  // Keep the world streaming for the recorder: idle look-around plus a short walk, no new work.
  const linger = Number(args.linger || 0)
  if (linger > 0) {
    run.log({ type: 'linger', seconds: linger })
    const until = Date.now() + linger * 1000
    let phase = 0
    while (Date.now() < until) {
      phase++
      try {
        await run.bot.look(run.bot.entity.yaw + 0.6, 0, true)
        run.bot.setControlState('forward', phase % 4 === 0)
        run.bot.setControlState('sprint', false)
      } catch {}
      await new Promise(r => setTimeout(r, 800))
    }
    try { run.bot.clearControlStates() } catch {}
  }
  await run.finish()
  process.exit(0)
})().catch(e => { console.error(e); process.exit(1) })
