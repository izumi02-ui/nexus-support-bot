import discord
from discord.ext import commands
import os
from keep_alive import keep_alive

intents = discord.Intents.default()
intents.message_content = True

bot = commands.Bot(command_prefix='!', intents=intents)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user.name}')
    await bot.change_presence(activity=discord.Game(name="Helping THE NEXUS™"))

@bot.command()
async def help_nexus(ctx):
    embed = discord.Embed(title="NEXUS Support™", description="NEXUS Support active hai! Kaise madad karoon?", color=0x3498db)
    await ctx.send(embed=embed)

keep_alive()
token = os.environ.get("DISCORD_TOKEN")
bot.run(token)
