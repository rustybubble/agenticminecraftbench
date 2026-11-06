// Demo: End entry + dragon, for the "complete run" footage. The teleport and the kill are staged
// and logged as `staged`; the walk into the portal is the agent's real enter_portal skill.
const { Run } = require('../src/loop')
;(async () => {
  const run = new Run({ runId: process.argv[2] || 'end-run', autoPlanner: false })
  await run.connect()
  const t0 = Date.now()
  while (!run.ready && Date.now() - t0 < 20000) await new Promise(r => setTimeout(r, 200))
  const { mineflayer: viewer } = require('prismarine-viewer')
  viewer(run.bot, { port: 3007, firstPerson: true, viewDistance: 8 })
  await new Promise(r => setTimeout(r, 1500))
  run.log({ type: 'staged', msg: 'demo jump-cut: End portal room' })
  run.bot.chat('/tp @s -1130.5 34.5 856.5')
  await new Promise(r => setTimeout(r, 4000))
  const end = await run.executor.run({ name: 'enter_portal', args: {} }, { timeoutMs: 45000 })
  run.log({ type: 'staged', msg: 'enter the End', dimension: run.bot.game.dimension })
  console.log('END:', JSON.stringify(end.result), run.bot.game.dimension)
  if (run.bot.game.dimension === 'the_end') {
    await new Promise(r => setTimeout(r, 5000))
    run.bot.chat('/kill @e[type=ender_dragon]')
    run.log({ type: 'staged', msg: 'dragon killed by command (demo only)' })
    await new Promise(r => setTimeout(r, 60000))
  }
  await run.finish(); process.exit(0)
})().catch(e => { console.error(e); process.exit(1) })
