// Fast finish: return through the entry portal, run to the active End portal, enter the End.
const { Run } = require('../src/loop')
;(async () => {
  const run = new Run({ runId: process.argv[2] || 'demo-07', autoPlanner: false })
  await run.connect()
  const t0 = Date.now()
  while (!run.ready && Date.now() - t0 < 20000) await new Promise(r => setTimeout(r, 200))
  const { mineflayer: viewer } = require('prismarine-viewer')
  viewer(run.bot, { port: 3007, firstPerson: true, viewDistance: 8 })
  run.log({ type: 'stream', dimension: run.bot.game.dimension })
  await new Promise(r => setTimeout(r, 1000))

  // 1) back to the entry portal (-36, 77, 32) in the nether
  await run.executor.run({ name: 'travel_legs', args: { x: -36, z: 32, legs: 8, legLen: 32 } }, { timeoutMs: 180000 })
  const back = await run.executor.run({ name: 'enter_portal', args: {} }, { timeoutMs: 40000 })
  run.log({ type: 'route_back', result: back.result, dimension: run.bot.game.dimension })
  console.log('back:', JSON.stringify(back.result), run.bot.game.dimension)

  if (run.bot.game.dimension === 'overworld') {
    // 2) long run to the End portal; legs re-plan every 48 blocks
    const legs = await run.executor.run({ name: 'travel_legs', args: { x: -1130, z: 856, legs: 40, legLen: 48 } }, { timeoutMs: 600000 })
    run.log({ type: 'route_to_end', result: legs.result, pos: { ...run.bot.entity.position } })
    console.log('to end portal:', JSON.stringify(legs.result), run.bot.entity.position)
    await run.executor.run({ name: 'goto', args: { x: -1130, y: 34, z: 856, range: 3 } }, { timeoutMs: 120000 })
    const end = await run.executor.run({ name: 'enter_portal', args: {} }, { timeoutMs: 45000 })
    run.log({ type: 'route_end', result: end.result, dimension: run.bot.game.dimension })
    console.log('END:', JSON.stringify(end.result), run.bot.game.dimension)
  }
  await new Promise(r => setTimeout(r, 45000))
  await run.finish(); process.exit(0)
})().catch(e => { console.error(e); process.exit(1) })
