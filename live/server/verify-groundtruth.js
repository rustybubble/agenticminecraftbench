#!/usr/bin/env node
// F2 ground-truth check, server-side, no client UI.
// `execute if block ... run say` returns nothing over RCON, so a conditional probe runs
// `time query gametime` instead: empty output = condition false.
//
//   node live/server/verify-groundtruth.js [radius]
const fs = require('fs')
const path = require('path')
const { Rcon } = require('./rcon')

const TARGETS = [
  { name: 'end_portal', dim: 'overworld', x: -1130, y: 34, z: 856, want: ['end_portal', 'end_portal_frame'] },
  { name: 'exit_portal', dim: 'the_nether', x: -141, y: 40, z: 104, want: ['nether_portal', 'obsidian'] },
  { name: 'entry_portal', dim: 'overworld', x: -285, y: 67, z: 259, want: ['nether_portal', 'obsidian'] },
  { name: 'village_chest', dim: 'overworld', x: -228, y: 71, z: 240, want: ['chest', 'barrel'] }
]
const CANDIDATES = ['air', 'stone', 'dirt', 'grass_block', 'sand', 'gravel', 'obsidian', 'nether_portal',
  'end_portal', 'end_portal_frame', 'chest', 'barrel', 'cobblestone', 'netherrack', 'bedrock']

const R = Number(process.argv[2] || 5)

async function probe (rcon, dim, x, y, z, block) {
  const out = await rcon.cmd(`execute in ${dim} if block ${x} ${y} ${z} minecraft:${block} run time query gametime`)
  return /time is/i.test(out)
}

async function identify (rcon, dim, x, y, z) {
  for (const b of CANDIDATES) if (await probe(rcon, dim, x, y, z, b)) return b
  return 'other'
}

async function scan (rcon, t) {
  const dim = t.dim === 'overworld' ? 'minecraft:overworld' : `minecraft:${t.dim}`
  const cx = Math.floor(t.x), cz = Math.floor(t.z)
  await rcon.cmd(`execute in ${dim} run forceload add ${cx - 32} ${cz - 32} ${cx + 32} ${cz + 32}`)
  await new Promise(r => setTimeout(r, 400))
  const exact = await identify(rcon, dim, t.x, t.y, t.z)
  const hits = []
  for (let dx = -R; dx <= R; dx++) {
    for (let dy = -R; dy <= R; dy++) {
      for (let dz = -R; dz <= R; dz++) {
        for (const want of t.want) {
          if (await probe(rcon, dim, t.x + dx, t.y + dy, t.z + dz, want)) {
            hits.push({ block: want, x: t.x + dx, y: t.y + dy, z: t.z + dz, dist: +Math.hypot(dx, dy, dz).toFixed(1) })
          }
        }
      }
    }
    if (hits.length) break
  }
  hits.sort((a, b) => a.dist - b.dist)
  await rcon.cmd(`execute in ${dim} run forceload remove ${cx - 32} ${cz - 32} ${cx + 32} ${cz + 32}`)
  return { ...t, exactBlock: exact, found: hits.length > 0, nearest: hits.slice(0, 5) }
}

;(async () => {
  const rcon = await new Rcon().connect()
  const results = []
  for (const t of TARGETS) {
    const r = await scan(rcon, t)
    results.push(r)
    console.log(`${r.found ? 'OK  ' : 'MISS'} ${r.name} ${r.dim} ${r.x},${r.y},${r.z} exact=${r.exactBlock}` +
      (r.found ? ` nearest: ${r.nearest.map(h => `${h.block}@${h.x},${h.y},${h.z}(${h.dist})`).join(' ')}` : ` nothing within ${R}`))
  }
  const out = path.join(__dirname, '..', '..', 'evidence', 'groundtruth-check.json')
  fs.mkdirSync(path.dirname(out), { recursive: true })
  fs.writeFileSync(out, JSON.stringify({ checkedAt: new Date().toISOString(), radius: R, results }, null, 2))
  console.log(`\nwrote ${path.relative(process.cwd(), out)}`)
  rcon.close()
  process.exit(0)
})().catch(e => { console.error(e); process.exit(2) })
