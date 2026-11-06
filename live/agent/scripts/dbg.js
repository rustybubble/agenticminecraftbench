const mineflayer=require('mineflayer'); const mcDataFor=require('minecraft-data')
const bot=mineflayer.createBot({host:'127.0.0.1',port:25576,username:'DbgBot',version:'1.16.5',auth:'offline'})
bot.once('spawn',async()=>{
 const mc=mcDataFor(bot.version)
 const id=mc.blocksByName.oak_log.id
 console.log('oak_log id',id)
 const pos=bot.findBlocks({matching:id,maxDistance:40,count:24})
 console.log('found',pos.length,pos.slice(0,3))
 for(const p of pos.slice(0,5)){const b=bot.blockAt(p); console.log(b.name, 'canDig', bot.canDigBlock(b), 'digTime', b.digTime)}
 const b0=bot.blockAt(pos[0])
 console.log('distance', bot.entity.position.distanceTo(b0.position))
 console.log('heldItem', bot.heldItem)
 try { await bot.dig(b0); console.log('dug ok') } catch(e){ console.log('dig err', e.message) }
 setTimeout(()=>{console.log('inv', bot.inventory.items().map(i=>i.name+'x'+i.count)); bot.quit();process.exit(0)},1500)
})
setTimeout(()=>{console.log('timeout');process.exit(1)},25000)
