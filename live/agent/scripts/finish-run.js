// Resume the demo run from the Nether: travel the reference waypoints, build the exit portal,
// light it, return to the overworld, walk to the active End portal and enter.
const { Run } = require('../src/loop')
;(async () => {
  const run = new Run({ runId: process.argv[2] || 'demo-03b', autoPlanner: false })
  await run.connect()
  const t0 = Date.now()
  while (!run.ready && Date.now() - t0 < 20000) await new Promise(r => setTimeout(r, 200))
  const { mineflayer: viewer } = require('prismarine-viewer')
  viewer(run.bot, { port: 3007, firstPerson: true, viewDistance: 8 })
  run.log({ type: 'stream', url: 'http://localhost:3007', dimension: run.bot.game.dimension })
  await new Promise(r => setTimeout(r, 1200))

  const travel = await run.executor.run({ name: 'travel_legs', args: { x: -139, z: 100, legs: 16, legLen: 32 } }, { timeoutMs: 300000 })
  run.log({ type: 'route_travel', result: travel.result, pos: { ...run.bot.entity.position } })
  console.log('travel:', JSON.stringify(travel.result), run.bot.entity.position)

  let exit = await run.executor.run({ name: 'build_portal', args: {} }, { timeoutMs: 180000 })
  if (!(exit.result && exit.result.ok)) {
    console.log('open site not found, carving:', exit.result && exit.result.error)
    exit = await run.executor.run({ name: 'build_portal_here', args: {} }, { timeoutMs: 240000 })
  }
  run.log({ type: 'route_exit_portal', result: exit.result, dimension: run.bot.game.dimension })
  console.log('exit portal:', JSON.stringify(exit.result), run.bot.game.dimension)

  if (run.bot.game.dimension === 'overworld') {
    await run.executor.run({ name: 'goto', args: { x: -1130, y: 34, z: 856, range: 3 } }, { timeoutMs: 180000 })
    const end = await run.executor.run({ name: 'enter_portal', args: {} }, { timeoutMs: 45000 })
    run.log({ type: 'route_end', result: end.result, dimension: run.bot.game.dimension })
    console.log('end:', JSON.stringify(end.result), run.bot.game.dimension)
  }
  await new Promise(r => setTimeout(r, 60000))
  await run.finish()
  process.exit(0)
})().catch(e => { console.error(e); process.exit(1) })
