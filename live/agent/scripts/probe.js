#!/usr/bin/env node
// Connectivity + observation smoke test: connect, spawn, print one compact state, quit.
const path = require('path')
const mineflayer = require('mineflayer')
const { pathfinder, Movements } = require('mineflayer-pathfinder')
const mcDataFor = require('minecraft-data')
const config = require('../src/config')
const { Observer } = require('../src/observe')

const bot = mineflayer.createBot({
  host: config.mc.host, port: config.mc.port, username: config.mc.username,
  version: config.mc.version, auth: 'offline'
})
bot.loadPlugin(pathfinder)

bot.once('spawn', async () => {
  const mc = mcDataFor(bot.version)
  const mv = new Movements(bot, mc)
  mv.canDig = true; mv.maxDropDown = 3
  bot.pathfinder.setMovements(mv)
  const ob = new Observer(bot, mc)
  await new Promise(r => setTimeout(r, 700))
  const s = ob.snapshot()
  console.log(JSON.stringify({
    spawned: true, pos: s.pos, dimension: s.dimension, health: s.health, food: s.food,
    version: bot.version, players: s.entities.players.map(p => p.name)
  }, null, 2))
  console.log('\n--- compact ---\n' + ob.compact(s))
  setTimeout(() => { bot.quit(); process.exit(0) }, 500)
})

bot.on('error', e => console.error('ERR', e.message))
bot.on('kicked', r => console.error('KICKED', r))
setTimeout(() => { console.error('TIMEOUT: no spawn in 25s'); process.exit(1) }, 25000)
