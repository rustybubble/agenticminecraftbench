const mineflayer=require('mineflayer'); const mcDataFor=require('minecraft-data')
const bot=mineflayer.createBot({host:'127.0.0.1',port:25576,username:'RecipeBot',version:'1.16.5',auth:'offline'})
bot.once('spawn',()=>{
 const mc=mcDataFor(bot.version)
 for(const name of ['crafting_table','wooden_pickaxe','stick','oak_planks','furnace']){
   const id=mc.itemsByName[name].id
   const rNo=bot.recipesFor(id,null,1,null)
   const rAll=bot.recipesAll(id,null,null)
   const rTrue=bot.recipesAll(id,null,true)
   console.log(name, 'recipesFor(null):', rNo.length, rNo.map(r=>'table='+r.requiresTable).join(','), '| recipesAll(null):', rAll.length, '| recipesAll(true):', rTrue.length)
 }
 bot.quit();process.exit(0)
})
setTimeout(()=>{console.log('timeout');process.exit(1)},20000)
