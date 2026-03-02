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
intents.voice_states = True # VC features ke liye

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

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"NEXUS System: All commands synced successfully.")

bot = MyBot()

# --- [1] Persistent Punishment Logic ---
class PunishDropdown(Select):
    def __init__(self, user_id):
        self.target_id = str(user_id)
        options = [
            discord.SelectOption(label="10 Minutes Timeout", value=f"10_{user_id}", emoji="⏳"),
            discord.SelectOption(label="1 Hour Timeout", value=f"60_{user_id}", emoji="🕒"),
            discord.SelectOption(label="12 Hours Timeout", value=f"720_{user_id}", emoji="🌑"),
            discord.SelectOption(label="24 Hours Timeout", value=f"1440_{user_id}", emoji="📅"),
            discord.SelectOption(label="Permanent Ban", value=f"ban_{user_id}", emoji="🔨"),
        ]
        super().__init__(placeholder="Apply Punishment...", options=options, custom_id=f"punish_sel_{user_id}")

    async def callback(self, interaction: discord.Interaction):
        val_parts = self.values[0].split("_")
        action, target_id = val_parts[0], val_parts[1]

        if action == "ban":
            punishments[target_id] = {"type": "ban", "expiry": None}
            res = f"User <@{target_id}> has been permanently banned from NEXUS services."
        else:
            mins = int(action)
            expiry = datetime.utcnow() + timedelta(minutes=mins)
            punishments[target_id] = {"type": "timeout", "expiry": expiry.isoformat()}
            res = f"User <@{target_id}> is on timeout for {mins} minutes."
        
        save_db(punishments)
        await interaction.response.send_message(f"✅ **Security Action:** {res}", ephemeral=True)

# --- [2] Voice & Utility Commands (New) ---

@bot.tree.command(name="join", description="Make the bot join your voice channel")
@app_commands.checks.has_permissions(administrator=True)
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        await channel.connect()
        await interaction.response.send_message(f"📡 Joined **{channel.name}**", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Join a VC first!", ephemeral=True)

@bot.tree.command(name="leave", description="Make the bot leave the voice channel")
@app_commands.checks.has_permissions(administrator=True)
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🔌 Disconnected from VC.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ I am not in a VC.", ephemeral=True)

@bot.tree.command(name="clear", description="Bulk delete messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted `{len(deleted)}` messages.", ephemeral=True)

@bot.tree.command(name="user_info", description="Get detailed info about a user")
async def user_info(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    embed = discord.Embed(title=f"User Stats - {member.name}", color=discord.Color.random())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=member.id, inline=True)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%d %b %Y"), inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%d %b %Y"), inline=True)
    embed.add_field(name="Top Role", value=member.top_role.mention, inline=True)
    await interaction.response.send_message(embed=embed)

# --- [3] Status & Restriction Check ---
def check_restriction(user_id):
    uid = str(user_id)
    if uid in punishments:
        data = punishments[uid]
        if data["type"] == "ban": return True, "Permanent Ban"
        if data["type"] == "timeout":
            expiry = datetime.fromisoformat(data["expiry"])
            if datetime.utcnow() < expiry:
                rem = expiry - datetime.utcnow()
                return True, f"Timeout ({int(rem.total_seconds() / 60)}m left)"
            else:
                del punishments[uid]
                save_db(punishments)
    return False, None

@tasks.loop(seconds=10)
async def change_status():
    status_list = [
        discord.Streaming(name="NEXUS Support | /help", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="📩 Dm me for help", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="Excellence in Service", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="Monitoring Systems...", url="https://www.twitch.tv/discord")
    ]
    for status in status_list:
        await bot.change_presence(activity=status)
        await asyncio.sleep(10)

# --- [4] Support System ---
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
            view = View(timeout=None).add_item(PunishDropdown(interaction.user.id))
            await log_channel.send(embed=embed, view=view)
            await interaction.response.send_message("Ticket sent to NEXUS staff.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary, emoji="📩")
    async def contact_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        restricted, reason = check_restriction(interaction.user.id)
        if restricted: return await interaction.response.send_message(f"Denied: {reason}", ephemeral=True)
        await interaction.response.send_modal(SupportModal())

@bot.tree.command(name="help", description="Get professional support")
async def help_slash(interaction: discord.Interaction):
    restricted, reason = check_restriction(interaction.user.id)
    if restricted: return await interaction.response.send_message(f"Restricted: {reason}", ephemeral=True)
    
    embed = discord.Embed(title="NEXUS | Support Portal", description="Click the button to open a ticket.", color=discord.Color.blue())
    embed.set_footer(text="NEXUS Excellence")
    await interaction.response.send_message(embed=embed, view=HelpView())

# --- [5] Admin Management & Control ---
@bot.tree.command(name="list_punishments", description="Manage restricted users")
async def list_punishments(interaction: discord.Interaction):
    if interaction.channel_id != ADMIN_CONTROL_CHANNEL:
        return await interaction.response.send_message("❌ Admin Only.", ephemeral=True)
    data = load_db()
    if not data: return await interaction.response.send_message("✅ No restrictions.", ephemeral=True)
    options = [discord.SelectOption(label=f"ID: {uid}", value=uid) for uid in list(data.keys())[:25]]
    select = Select(placeholder="Select user to clear...", options=options)
    async def callback(inter):
        data.pop(select.values[0], None)
        save_db(data)
        await inter.response.send_message("✅ Cleared.", ephemeral=True)
    select.callback = callback
    await interaction.response.send_message("NEXUS Management", view=View().add_item(select), ephemeral=True)

class MessageFormatView(View):
    def __init__(self, target_channel, content):
        super().__init__(timeout=60)
        self.target_channel, self.content = target_channel, content
    @discord.ui.button(label="Normal", style=discord.ButtonStyle.secondary)
    async def normal(self, interaction, button):
        await self.target_channel.send(self.content)
        await interaction.response.send_message("Sent.", ephemeral=True)
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.success)
    async def embed(self, interaction, button):
        e = discord.Embed(description=self.content, color=discord.Color.blue())
        e.set_author(name="NEXUS Support™")
        await self.target_channel.send(embed=e)
        await interaction.response.send_message("Embed Sent.", ephemeral=True)

class ChannelDropdown(Select):
    def __init__(self, content):
        self.msg_content = content
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        options = [discord.SelectOption(label=f"#{c.name}", value=str(c.id)) for c in channels[:25]]
        super().__init__(placeholder="Select channel...", options=options)
    async def callback(self, interaction):
        ch = bot.get_channel(int(self.values[0]))
        await interaction.response.send_message(f"Target: {ch.mention}", view=MessageFormatView(ch, self.msg_content), ephemeral=True)

# --- [6] Events & Auto-Mod ---
@bot.event
async def on_message(message):
    if message.author == bot.user: return
    
    # Simple Anti-Link (Exclude Admins)
    if "http" in message.content.lower() and not message.author.guild_permissions.administrator:
        if message.guild:
            await message.delete()
            return await message.channel.send(f"⚠️ {message.author.mention}, links are not allowed here!", delete_after=5)

    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        await message.reply("**NEXUS Panel**", view=View().add_item(ChannelDropdown(message.content)))
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'NEXUS ULTRA ONLINE.')
    if not change_status.is_running(): change_status.start()

keep_alive()
bot.run(TOKEN)
