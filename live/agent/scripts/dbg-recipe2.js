const mineflayer=require('mineflayer'); const mcDataFor=require('minecraft-data')
const bot=mineflayer.createBot({host:'127.0.0.1',port:25576,username:'RecipeBot2',version:'1.16.5',auth:'offline'})
bot.once('spawn',()=>{
 const mc=mcDataFor(bot.version)
 const id=mc.itemsByName.crafting_table.id
 const all=bot.recipesAll(id,null,true)
 console.log(JSON.stringify(all[0], (k,v)=> typeof v==='bigint'?String(v):v, 1).slice(0,1200))
 const pick=mc.itemsByName.wooden_pickaxe.id
 const p=bot.recipesAll(pick,null,true)
 console.log('pick recipes', p.length, 'requiresTable', p.map(r=>r.requiresTable))
 console.log(JSON.stringify(p[0], (k,v)=> typeof v==='bigint'?String(v):v, 1).slice(0,800))
 bot.quit();process.exit(0)
})
setTimeout(()=>{console.log('timeout');process.exit(1)},20000)
