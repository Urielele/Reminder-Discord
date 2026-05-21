import discord
from discord.ext import commands
import logging
from dotenv import load_dotenv
import os
import asyncio

# load file .env
load_dotenv()
token = os.getenv('DISCORD_TOKEN')


# 
handler = logging.FileHandler(filename='discord.log', encoding='utf-8', mode='w')
logging.basicConfig(level=logging.DEBUG,handlers=[handler])

# intent (izin bot)
intents = discord.Intents.default()
intents.message_content = True
intents.members = True


# buat bot dengan prefix !
bot = commands.Bot(command_prefix='!', intents=intents)


@bot.event
# menunggu bot ready
async def on_ready():
    await bot.change_presence(activity=discord.Activity(type=discord.ActivityType.playing, name="!help"))
    print(f"{bot.user.name.upper()} IS READY :D")

async def load():
    for filename in os.listdir("./cogs"):
        if filename.endswith(".py"):
            await bot.load_extension(f"cogs.{filename[:-3]}")

async def main():
    async with bot:
        await load()
        await bot.start(token)


asyncio.run(main())
