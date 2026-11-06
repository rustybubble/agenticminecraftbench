#!/usr/bin/env node
// Entry point.
//   node run.js --goal "get 3 iron" --minutes 10
//   node run.js --manual              (bot obeys !wood / !pick / !goto from chat)
//   node run.js --once --goal "..."   (one planner decision, print it, exit)
//   node run.js --classify            (one classifier decision, print it, exit)
const { Run } = require('./src/loop')
const { plan } = require('./src/planner')
const { classify } = require('./src/router')
const { routeState } = require('./src/route')
const config = require('./src/config')

function parseArgs (argv) {
  const out = { _: [] }
  for (let i = 0; i < argv.length; i++) {
    const a = argv[i]
    if (a.startsWith('--')) {
      const [k, v] = a.slice(2).split('=')
      if (v !== undefined) out[k] = v
      else if (argv[i + 1] && !argv[i + 1].startsWith('--')) out[k] = argv[++i]
      else out[k] = true
    } else out._.push(a)
  }
  return out
}

async function main () {
  const args = parseArgs(process.argv.slice(2))
  const goal = args.goal || null
  const runOpts = {
    goal,
    minutes: args.minutes ? Number(args.minutes) : null,
    runId: args.run || undefined,
    autoPlanner: args['no-planner'] ? false : true
  }
  if (args.help) {
    console.log(`usage: node run.js [--goal text] [--minutes N] [--manual] [--once|--classify] [--run id]
env: MC_HOST MC_PORT MC_USER MC_VERSION PLANNER_MODEL CLASSIFIER_MODEL PLANNER_EVERY_MS`)
    return
  }
  const run = new Run(runOpts)
  await run.connect()
  const t0 = Date.now()
  while (!run.ready && Date.now() - t0 < 20000) await new Promise(r => setTimeout(r, 200))
  if (!run.ready) throw new Error('bot did not spawn')

  if (args.once) {
    const state = run.observer.snapshot({ recent: [], goal })
    const route = routeState(state, Date.now())
    const compact = run.observer.compact(state)
    const p = await plan({ state, compact, route, calculators: run.calculators(state), last: null, memory: [] })
    console.log(JSON.stringify(p, null, 2))
    console.log('\n--- compact ---\n' + compact)
    run.events.end(); run.bot.quit(); return
  }
  if (args.classify) {
    const state = run.observer.snapshot({ recent: [], goal })
    const compact = run.observer.compact(state)
    const split = args.split || 'wood'
    const c = await classify({ compact, split, last: null })
    console.log(JSON.stringify(c, null, 2))
    run.events.end(); run.bot.quit(); return
  }
  if (args.clean) {
    // Repeatable run start. The bot is opped on the live server; this uses the server's own
    // commands so the reset is authoritative, not a client-side assumption.
    const cmds = [
      '/clear @s', '/gamemode survival @s', '/effect clear @s', '/experience set @s 0',
      `/tp @s ${args.x || -181} ${args.y || 70} ${args.z || 214}`,
      '/time set day', '/weather clear'
    ]
    for (const c of cmds) { run.bot.chat(c); await new Promise(r => setTimeout(r, 120)) }
    run.log({ type: 'clean', cmds })
    await new Promise(r => setTimeout(r, 800))
  }
  if (args.viewer) {
    // prismarine-viewer renders the bot's own world in a browser: this is our footage source,
    // no Minecraft client needed. firstPerson = the agent's POV.
    const { mineflayer: viewer } = require('prismarine-viewer')
    const port = Number(args['viewer-port'] || 3007)
    viewer(run.bot, { port, firstPerson: true, viewDistance: Number(args['view-distance'] || 6) })
    run.log({ type: 'viewer', port, url: `http://localhost:${port}` })
    console.log(`viewer: http://localhost:${port} (first person)`)
  }
  if (args.manual) {
    console.log(`manual mode: chat !state !wood 8 !pick stone !table !goto x y z !mine iron_ore !plan !stop`)
    run.log({ type: 'mode', msg: 'manual' })
    await new Promise(resolve => {
      run.bot.on('end', resolve)
      process.on('SIGINT', () => { run.running = false; resolve() })
    })
    await run.finish()
    return
  }
  console.log(`run ${run.runId} -> ${run.dir}`)
  await run.loop()
}

main().catch(err => { console.error(err); process.exit(1) })
