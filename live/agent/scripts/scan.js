const mineflayer=require('mineflayer'); const mcDataFor=require('minecraft-data')
const bot=mineflayer.createBot({host:'127.0.0.1',port:25576,username:'ScanBot',version:'1.16.5',auth:'offline'})
bot.once('spawn',()=>{
 const mc=mcDataFor(bot.version)
 const logs=mc.blocksArray.filter(b=>/_log$|^log$|^log2$/.test(b.name)).map(b=>b.id)
 for (const R of [32,48,64,96,120]) {
   const pos=bot.findBlocks({matching:logs,maxDistance:R,count:500})
   console.log('R',R,'logs',pos.length)
 }
 const names=['oak_log','birch_log','spruce_log','jungle_log','acacia_log','dark_oak_log']
 for(const n of names){const b=mc.blocksByName[n]; if(!b)continue; const p=bot.findBlocks({matching:b.id,maxDistance:120,count:3}); if(p.length) console.log(n,p.map(x=>`${x.x},${x.y},${x.z}`).join(' '))}
 const ch=bot.findBlocks({matching:mc.blocksByName.oak_leaves.id,maxDistance:120,count:3}); console.log('leaves',ch.length)
 console.log('chunks loaded', Object.keys(bot.world.chunks||{}).length)
 console.log('biome at bot', bot.world.getBiome ? bot.world.getBiome(bot.entity.position) : 'n/a')
 bot.quit();process.exit(0)
})
setTimeout(()=>{console.log('timeout');process.exit(1)},20000)
