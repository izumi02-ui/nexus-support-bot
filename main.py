import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import json
import io
from datetime import datetime, timedelta
from keep_alive import keep_alive
from discord.ui import Select, View, Button

# --- Bot Configuration ---
TOKEN = os.environ.get("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1477923902834475080 
ADMIN_CONTROL_CHANNEL = 1477954227442679910 
DB_FILE = "punishments.json"

intents = discord.Intents.all()

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"NEXUS System: All commands synced for {self.user}")

bot = MyBot()

# --- [Formatting View for Media Support] ---

class FormatView(View):
    def __init__(self, ch, content, files):
        super().__init__(timeout=120)
        self.ch = ch
        self.content = content or ""
        self.files = files or []

    async def get_discord_files(self):
        """Attachments ko asli files mein convert karne ke liye"""
        actual_files = []
        for f in self.files:
            try:
                # File ko memory mein download karna
                fp = io.BytesIO()
                await f.save(fp)
                actual_files.append(discord.File(fp, filename=f.filename))
            except:
                continue
        return actual_files

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.secondary)
    async def normal(self, inter: discord.Interaction, btn: Button):
        await inter.response.defer(ephemeral=True)
        files_to_send = await self.get_discord_files()
        await self.ch.send(content=self.content if self.content else None, files=files_to_send)
        await inter.followup.send("✅ Sent as Normal Message.", ephemeral=True)

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.success)
    async def embed(self, inter: discord.Interaction, btn: Button):
        await inter.response.defer(ephemeral=True)
        
        embed = discord.Embed(description=self.content or "‎", color=discord.Color.blue())
        embed.set_author(name="NEXUS Announcement", icon_url=bot.user.display_avatar.url)
        
        files_to_send = await self.get_discord_files()
        
        # Agar image hai toh usse Embed mein set karna
        if self.files:
            for f in self.files:
                if any(f.filename.lower().endswith(ext) for ext in [".png", ".jpg", ".jpeg", ".gif", ".webp"]):
                    embed.set_image(url=f"attachment://{f.filename}")
                    break

        await self.ch.send(embed=embed, files=files_to_send)
        await inter.followup.send("✅ Sent as Embed with Media Support.", ephemeral=True)

# --- [Dashboard Channel Selection] ---

class ChannelSel(Select):
    def __init__(self, content, attachments):
        self.content = content
        self.attachments = attachments
        # Sirf text channels ki list
        options = []
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        for c in channels[:25]:
            options.append(discord.SelectOption(label=f"#{c.name}", value=str(c.id)))
            
        super().__init__(placeholder="Select Target Channel...", options=options)
    
    async def callback(self, inter: discord.Interaction):
        target_ch = bot.get_channel(int(self.values[0]))
        if target_ch:
            view = FormatView(target_ch, self.content, self.attachments)
            await inter.response.send_message(f"Selected: {target_ch.mention}\nAb format choose karein:", view=view, ephemeral=True)

# --- [Events & Core Logic] ---

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    
    # Dashboard Logic
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        view = View().add_item(ChannelSel(message.content, message.attachments))
        await message.reply("**NEXUS Media Dashboard**", view=view)
        
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'NEXUS SUPREME ONLINE.')
    if not change_status.is_running():
        change_status.start()

@tasks.loop(seconds=20)
async def change_status():
    await bot.change_presence(activity=discord.Streaming(name="NEXUS | /help", url="https://twitch.tv/discord"))

@bot.tree.command(name="help", description="Get Support")
async def help_slash(interaction: discord.Interaction):
    # Short help command for testing
    await interaction.response.send_message("NEXUS Support is active. Use the dashboard for announcements.", ephemeral=True)

keep_alive()
bot.run(TOKEN)
