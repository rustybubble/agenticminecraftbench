const mineflayer=require('mineflayer')
const { Rcon } = require('../../server/rcon')
const bot=mineflayer.createBot({host:'127.0.0.1',port:25576,username:'SplitAgent',version:'1.16.5',auth:'offline'})
bot.once('spawn', async()=>{
  await new Promise(r=>setTimeout(r,800))
  const r = await new Rcon().connect()
  for (const q of ['FoodLevel','foodLevel','Inventory[0]','Inventory[3]','Inventory[10]','Inventory[30]','Inventory[40]','Inventory[41]']) {
    const out = await r.cmd(`data get entity SplitAgent ${q}`)
    console.log(q, '=>', out.slice(0,200))
  }
  r.close(); bot.quit(); process.exit(0)
})
setTimeout(()=>{console.log('timeout');process.exit(1)},25000)
