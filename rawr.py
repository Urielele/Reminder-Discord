@bot.event
async def on_message(message):
    if message.author == bot.user:
        return
    
    if "hai" in message.content.lower():
        await message.channel.send(f"hai {message.author.name}")
    
    await bot.process_commands(message)




@bot.command()
async def hello(ctx):
    await ctx.send(f"Hello {ctx.author.mention}!")

@bot.command()
async def poll(ctx, *, question):
    embed = discord.Embed(title="New Poll", description=question)
    poll_message = await ctx.send(embed=embed)
    await poll_message.add_reaction("😾")
    await poll_message.add_reaction("😺")

@bot.command()
async def pujideveloper(ctx):
     await ctx.send(f"beemo ganteng bgt jangan lupa follow @ciqmol_ di instagram")

