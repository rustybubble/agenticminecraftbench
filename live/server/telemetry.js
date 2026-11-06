#!/usr/bin/env node
// Server-side telemetry. Polls RCON (position, dimension, health, food, selected item,
// inventory) and tails the vanilla log (joins, deaths, advancements). Writes
// runs/live/<runId>/server.jsonl. This is the server-authoritative half of Layer B:
// agent events.jsonl is a claim, this file is evidence.
//
//   node server/telemetry.js --run live-01 --player SplitAgent [--interval 1000]
const fs = require('fs')
const path = require('path')
const { Rcon, parsePos, parseNumber, parseDimension, parseInventory } = require('./rcon')

function parseArgs (argv) {
  const out = {}
  for (let i = 0; i < argv.length; i++) if (argv[i].startsWith('--')) {
    const k = argv[i].slice(2)
    out[k] = argv[i + 1] && !argv[i + 1].startsWith('--') ? argv[++i] : true
  }
  return out
}

const args = parseArgs(process.argv.slice(2))
const runId = args.run || `live-${new Date().toISOString().replace(/[:.]/g, '-')}`
const player = args.player || 'SplitAgent'
const interval = Number(args.interval || 1000)
const outDir = path.join(__dirname, '..', '..', 'runs', 'live', runId)
fs.mkdirSync(outDir, { recursive: true })
const out = fs.createWriteStream(path.join(outDir, 'server.jsonl'), { flags: 'a' })
const logPath = path.join(__dirname, 'logs', 'latest.log')

const write = rec => out.write(JSON.stringify({ ts: new Date().toISOString(), epoch: Date.now(), runId, ...rec }) + '\n')

// --- log tail: deaths, joins, advancements are server-side facts ------------
let logPos = 0
function readLog () {
  if (!fs.existsSync(logPath)) return
  const size = fs.statSync(logPath).size
  if (size < logPos) logPos = 0
  if (size === logPos) return
  const fd = fs.openSync(logPath, 'r')
  const len = size - logPos
  const buf = Buffer.alloc(len)
  fs.readSync(fd, buf, 0, len, logPos)
  fs.closeSync(fd)
  logPos = size
  for (const line of buf.toString('utf8').split('\n')) {
    if (!line.includes(player)) continue
    let kind = null
    if (/joined the game/.test(line)) kind = 'join'
    else if (/left the game/.test(line)) kind = 'leave'
    else if (/was slain by|died|was killed|hit the ground too hard|fell from a high place|tried to swim in lava|burned to death|blew up|went up in flames|was shot by|drowned|withered away/.test(line)) kind = 'death'
    else if (/has made the advancement|has reached the goal|has completed the challenge/.test(line)) kind = 'advancement'
    if (kind) write({ type: 'log', kind, line: line.replace(/^\[[^\]]+\]\s*\[[^\]]+\]:\s*/, '').trim() })
  }
}

async function sample (rcon) {
  const rec = { type: 'sample', player }
  try {
    rec.pos = parsePos(await rcon.cmd(`data get entity ${player} Pos`))
    rec.dimension = parseDimension(await rcon.cmd(`data get entity ${player} Dimension`))
    rec.health = parseNumber(await rcon.cmd(`data get entity ${player} Health`))
    rec.food = parseNumber(await rcon.cmd(`data get entity ${player} foodLevel`))
    const sel = await rcon.cmd(`data get entity ${player} SelectedItem`)
    const idm = sel.match(/id:"minecraft:([a-z0-9_]+)"/)
    rec.selected = idm ? idm[1] : null
    if (!rec.pos) { rec.online = false }
  } catch (e) {
    rec.error = String(e.message).slice(0, 120)
  }
  write(rec)
}

async function main () {
  let rcon = null
  let lastInventory = 0
  write({ type: 'start', player, intervalMs: interval, note: 'server-authoritative telemetry via RCON + log tail' })
  console.log(`telemetry -> ${path.join(outDir, 'server.jsonl')} (player=${player}, ${interval}ms)`)
  setInterval(readLog, 1000)
  readLog()
  while (true) {
    try {
      if (!rcon) rcon = await new Rcon().connect()
      await sample(rcon)
      // Full Inventory NBT is truncated by the server's reply, so read slot by slot.
      // 41 queries ~ 0.4s locally, every 5s.
      if (Date.now() - lastInventory > 5000) {
        const items = {}
        let empties = 0
        for (let slot = 0; slot < 41; slot++) {
          const out = await rcon.cmd(`data get entity ${player} Inventory[${slot}]`)
          if (/Found no elements|No entity was found/.test(out)) {
            if (++empties >= 3) break
            continue
          }
          empties = 0
          const m = out.match(/id:\s*"minecraft:([a-z0-9_]+)",\s*Count:\s*(\d+)b/)
          if (m) items[m[1]] = (items[m[1]] || 0) + Number(m[2])
        }
        write({ type: 'inventory', items })
        lastInventory = Date.now()
      }
    } catch (e) {
      write({ type: 'telemetry_error', error: String(e.message).slice(0, 200) })
      try { rcon?.close() } catch {}
      rcon = null
    }
    await new Promise(r => setTimeout(r, interval))
  }
}

process.on('SIGINT', () => { write({ type: 'stop' }); out.end(); process.exit(0) })
main()
