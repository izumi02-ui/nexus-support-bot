import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
import json
from datetime import datetime, timedelta
from keep_alive import keep_alive
from discord.ui import Select, View, Button

# --- Bot Configuration ---
TOKEN = os.environ.get("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1477923902834475080 
ADMIN_CONTROL_CHANNEL = 1477954227442679910 
DB_FILE = "punishments.json"

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 

# --- [Database Logic] ---
def load_db():
    if os.path.exists(DB_FILE):
        try:
            with open(DB_FILE, "r") as f:
                return json.load(f)
        except: return {}
    return {}

def save_db(data):
    with open(DB_FILE, "w") as f:
        json.dump(data, f, indent=4)

punishments = load_db()

# --- [1] Persistent Punishment Logic ---
class PunishDropdown(Select):
    def __init__(self, user_id):
        self.target_id = str(user_id)
        options = [
            discord.SelectOption(label="10 Minutes Timeout", value=f"10_{user_id}"),
            discord.SelectOption(label="1 Hour Timeout", value=f"60_{user_id}"),
            discord.SelectOption(label="12 Hours Timeout", value=f"720_{user_id}"),
            discord.SelectOption(label="24 Hours Timeout", value=f"1440_{user_id}"),
            discord.SelectOption(label="Permanent Ban", value=f"ban_{user_id}"),
        ]
        # Custom ID zaroori hai taaki interaction fail na ho
        super().__init__(placeholder="Apply Punishment...", options=options, custom_id=f"punish_sel_{user_id}")

    async def callback(self, interaction: discord.Interaction):
        val_parts = self.values[0].split("_")
        action = val_parts[0]
        target_id = val_parts[1]

        if action == "ban":
            punishments[target_id] = {"type": "ban", "expiry": None}
            res = f"User <@{target_id}> banned permanently."
        else:
            mins = int(action)
            expiry = datetime.utcnow() + timedelta(minutes=mins)
            punishments[target_id] = {"type": "timeout", "expiry": expiry.isoformat()}
            res = f"User <@{target_id}> put on {mins}m timeout."
        
        save_db(punishments)
        await interaction.response.send_message(f"✅ **Action:** {res}", ephemeral=True)

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"NEXUS System: Commands synced.")

bot = MyBot()

# --- [Restriction Check Helper] ---
def check_restriction(user_id):
    uid = str(user_id)
    if uid in punishments:
        data = punishments[uid]
        if data["type"] == "ban":
            return True, "Permanent Ban"
        if data["type"] == "timeout":
            expiry = datetime.fromisoformat(data["expiry"])
            if datetime.utcnow() < expiry:
                rem = expiry - datetime.utcnow()
                mins = int(rem.total_seconds() / 60)
                return True, f"Timeout ({mins}m remaining)"
            else:
                del punishments[uid]
                save_db(punishments)
    return False, None

# --- [2] Status & Rotating Activity ---
@tasks.loop(seconds=10)
async def change_status():
    status_list = [
        discord.Streaming(name="NEXUS Support | /help", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="📩 Dm me for help", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="Excellence in Service", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="Processing Tickets...", url="https://www.twitch.tv/discord")
    ]
    for status in status_list:
        await bot.change_presence(activity=status)
        await asyncio.sleep(10)

# --- [3] Support System ---
class SupportModal(discord.ui.Modal, title='NEXUS Support Form'):
    user_msg = discord.ui.TextInput(label='How can we help you?', style=discord.TextStyle.paragraph, placeholder='Describe in detail...', required=True, min_length=5)

    async def on_submit(self, interaction: discord.Interaction):
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        location = "DM" if interaction.guild is None else f"Server: {interaction.guild.name}"
        
        embed = discord.Embed(title="New Support Ticket", color=discord.Color.green())
        embed.add_field(name="User", value=f"{interaction.user.mention} (`{interaction.user.id}`)", inline=True)
        embed.add_field(name="Source", value=location, inline=True)
        embed.add_field(name="Message", value=self.user_msg.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if log_channel:
            # Timeout=None se interaction fail nahi hoga
            view = View(timeout=None).add_item(PunishDropdown(interaction.user.id))
            await log_channel.send(embed=embed, view=view)
            await interaction.response.send_message("Sent to NEXUS team.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary, emoji="📩")
    async def contact_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        restricted, reason = check_restriction(interaction.user.id)
        if restricted: return await interaction.response.send_message(f"Restricted: {reason}", ephemeral=True)
        await interaction.response.send_modal(SupportModal())

@bot.tree.command(name="help", description="Get professional support")
async def help_slash(interaction: discord.Interaction):
    restricted, reason = check_restriction(interaction.user.id)
    if restricted: return await interaction.response.send_message(f"Access Denied: {reason}", ephemeral=True)
    
    embed = discord.Embed(
        title="NEXUS | Professional Support Portal", 
        description=(
            "👋 **Welcome to NEXUS Support.**\n\n"
            "We provide high-speed automated assistance to bridge the gap "
            "between users and creators. Our team is available 24/7.\n\n"
            "**Guidelines:**\n"
            "• Be clear and descriptive in your message.\n"
            "• Do not spam the support system.\n"
            "• Staff will respond as soon as possible."
        ), 
        color=discord.Color.blue()
    )
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    embed.set_footer(text="Excellence in Service • Powered by NEXUS™")
    await interaction.response.send_message(embed=embed, view=HelpView())

# --- [4] Management Panel ---
@bot.tree.command(name="list_punishments", description="Manage restricted users")
async def list_punishments(interaction: discord.Interaction):
    if interaction.channel_id != ADMIN_CONTROL_CHANNEL:
        return await interaction.response.send_message("❌ Admin Only.", ephemeral=True)

    data = load_db()
    if not data: return await interaction.response.send_message("✅ No active punishments.", ephemeral=True)

    options = [discord.SelectOption(label=f"ID: {uid}", value=uid) for uid in list(data.keys())[:25]]
    select = Select(placeholder="Select user to clear...", options=options)

    async def select_callback(inter: discord.Interaction):
        target = select.values[0]
        data.pop(target, None)
        save_db(data)
        await inter.response.send_message(f"✅ User `{target}` cleared.", ephemeral=True)

    select.callback = select_callback
    await interaction.response.send_message("**NEXUS Management Panel**\nRemove bans or timeouts below:", view=View().add_item(select), ephemeral=True)

# --- [5] Admin Control Panel ---
class MessageFormatView(View):
    def __init__(self, target_channel, content):
        super().__init__(timeout=60)
        self.target_channel, self.content = target_channel, content

    @discord.ui.button(label="Normal Text", style=discord.ButtonStyle.secondary)
    async def send_normal(self, interaction, button):
        await self.target_channel.send(self.content)
        await interaction.response.send_message("Sent.", ephemeral=True)

    @discord.ui.button(label="Embed Message", style=discord.ButtonStyle.success)
    async def send_embed(self, interaction, button):
        embed = discord.Embed(description=self.content, color=discord.Color.blue())
        embed.set_author(name="NEXUS Support™", icon_url=bot.user.display_avatar.url)
        if any(ext in self.content.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif']):
            embed.set_image(url=self.content)
            embed.description = ""
        await self.target_channel.send(embed=embed)
        await interaction.response.send_message("Embed Sent.", ephemeral=True)

class ChannelDropdown(Select):
    def __init__(self, content):
        self.msg_content = content
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        options = [discord.SelectOption(label=f"#{c.name}", value=str(c.id)) for c in channels[:25]]
        super().__init__(placeholder="Select channel...", options=options)

    async def callback(self, interaction: discord.Interaction):
        target_ch = bot.get_channel(int(self.values[0]))
        await interaction.response.send_message(f"Target: {target_ch.mention}", view=MessageFormatView(target_ch, self.msg_content), ephemeral=True)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        description_text = (
            "**NEXUS Master Control Panel**\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "Select a destination channel to deliver your message. "
            "You can choose between **Normal Text** or **Professional Embed** format."
        )
        await message.reply(description_text, view=View().add_item(ChannelDropdown(message.content)))
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'NEXUS System Online.')
    if not change_status.is_running(): change_status.start()

keep_alive()
bot.run(TOKEN)
