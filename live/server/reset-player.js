#!/usr/bin/env node
// Clean a player to a fresh survival start via RCON (works offline too: clear/gamemode/effect
// apply to stored player data; tp only succeeds while online).
//   node server/reset-player.js [name] [x y z]
const { Rcon } = require('./rcon')

const [name = 'SplitAgent', x = '-181', y = '70', z = '214'] = process.argv.slice(2)

;(async () => {
  const r = await new Rcon().connect()
  const cmds = [
    `gamemode survival ${name}`,
    `clear ${name}`,
    `effect clear ${name}`,
    `experience set ${name} 0`,
    `tp ${name} ${x} ${y} ${z}`
  ]
  for (const c of cmds) {
    const out = await r.cmd(c)
    console.log(`${c} -> ${out.trim() || '(ok)'}`)
  }
  const inv = await r.cmd(`data get entity ${name} Inventory`)
  console.log(`inventory now -> ${inv.trim()}`)
  r.close()
  process.exit(0)
})().catch(e => { console.error(e.message); process.exit(1) })
