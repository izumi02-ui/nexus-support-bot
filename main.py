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
intents.voice_states = True 

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
        print(f"NEXUS System: All commands synced for {self.user}")

bot = MyBot()

# --- [1] Security & Punishment System ---
class PunishDropdown(Select):
    def __init__(self, user_id):
        self.target_id = str(user_id)
        options = [
            discord.SelectOption(label="10m Timeout", value=f"10_{user_id}"),
            discord.SelectOption(label="1h Timeout", value=f"60_{user_id}"),
            discord.SelectOption(label="12h Timeout", value=f"720_{user_id}"),
            discord.SelectOption(label="24h Timeout", value=f"1440_{user_id}"),
            discord.SelectOption(label="Permanent Ban", value=f"ban_{user_id}"),
        ]
        super().__init__(placeholder="Security Actions...", options=options, custom_id=f"p_sel_{user_id}")

    async def callback(self, interaction: discord.Interaction):
        val = self.values[0].split("_")
        action, target_id = val[0], val[1]
        if action == "ban":
            punishments[target_id] = {"type": "ban", "expiry": None}
            res = f"User <@{target_id}> banned permanently."
        else:
            mins = int(action)
            expiry = datetime.utcnow() + timedelta(minutes=mins)
            punishments[target_id] = {"type": "timeout", "expiry": expiry.isoformat()}
            res = f"User <@{target_id}> timed out for {mins}m."
        save_db(punishments)
        await interaction.response.send_message(f"✅ {res}", ephemeral=True)

def check_restriction(user_id):
    uid = str(user_id)
    if uid in punishments:
        data = punishments[uid]
        if data["type"] == "ban": return True, "Permanent Ban"
        if data["type"] == "timeout":
            expiry = datetime.fromisoformat(data["expiry"])
            if datetime.utcnow() < expiry:
                return True, f"Timeout ({int((expiry - datetime.utcnow()).total_seconds() / 60)}m left)"
            else:
                del punishments[uid]; save_db(punishments)
    return False, None

# --- [2] Janam Kundli & Utility Commands ---

@bot.tree.command(name="user_info", description="User ki poori janam kundli nikalen")
async def user_info(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    roles = [role.mention for role in reversed(member.roles) if role.name != "@everyone"]
    
    embed = discord.Embed(title=f"👤 User Biodata: {member.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
    embed.add_field(name="Nickname", value=member.display_name, inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%d %b %Y"), inline=False)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%d %b %Y"), inline=False)
    embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles) if roles else "No Roles", inline=False)
    embed.set_footer(text=f"Requested by {interaction.user.name}", icon_url=interaction.user.display_avatar.url)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="list_punishments", description="Manage banned/timeout users")
@app_commands.checks.has_permissions(administrator=True)
async def list_punishments(interaction: discord.Interaction):
    if interaction.channel_id != ADMIN_CONTROL_CHANNEL:
        return await interaction.response.send_message("❌ Admin Only.", ephemeral=True)
    data = load_db()
    if not data: return await interaction.response.send_message("✅ No restrictions found.", ephemeral=True)
    
    options = [discord.SelectOption(label=f"ID: {uid}", value=uid, description=f"Type: {info['type']}") for uid, info in list(data.items())[:25]]
    select = Select(placeholder="Choose user to unban...", options=options)

    async def select_callback(inter):
        data.pop(select.values[0], None)
        save_db(data)
        await inter.response.send_message(f"✅ User `{select.values[0]}` freed.", ephemeral=True)

    select.callback = select_callback
    await interaction.response.send_message("NEXUS Management Panel", view=View().add_item(select), ephemeral=True)

@bot.tree.command(name="join", description="Connect bot to VC")
@app_commands.checks.has_permissions(administrator=True)
async def join(interaction: discord.Interaction):
    if interaction.user.voice:
        await interaction.user.voice.channel.connect()
        await interaction.response.send_message("Connected to VC.", ephemeral=True)
    else: await interaction.response.send_message("Join a VC first!", ephemeral=True)

@bot.tree.command(name="leave", description="Disconnect bot from VC")
@app_commands.checks.has_permissions(administrator=True)
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("Disconnected.", ephemeral=True)

@bot.tree.command(name="clear", description="Delete messages")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"Deleted {len(deleted)} messages.", ephemeral=True)

# --- [3] Status & Support Portal ---
@tasks.loop(seconds=10)
async def change_status():
    status_list = [discord.Streaming(name="NEXUS | /help", url="https://twitch.tv/discord"),
                   discord.Streaming(name="Excellence in Service", url="https://twitch.tv/discord")]
    for s in status_list:
        await bot.change_presence(activity=s); await asyncio.sleep(10)

class SupportModal(discord.ui.Modal, title='NEXUS Support Form'):
    user_msg = discord.ui.TextInput(label='Message', style=discord.TextStyle.paragraph, placeholder='Details...', required=True, min_length=10)
    async def on_submit(self, interaction: discord.Interaction):
        log_ch = bot.get_channel(LOG_CHANNEL_ID)
        embed = discord.Embed(title="New Ticket", color=discord.Color.blue())
        embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.id})")
        embed.add_field(name="Message", value=self.user_msg.value, inline=False)
        if log_ch:
            await log_ch.send(embed=embed, view=View(timeout=None).add_item(PunishDropdown(interaction.user.id)))
            await interaction.response.send_message("Ticket sent.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary)
    async def contact(self, interaction, button): await interaction.response.send_modal(SupportModal())

@bot.tree.command(name="help", description="NEXUS Portal")
async def help_slash(interaction: discord.Interaction):
    res, reason = check_restriction(interaction.user.id)
    if res: return await interaction.response.send_message(f"Denied: {reason}", ephemeral=True)
    embed = discord.Embed(title="NEXUS | Portal", description="Guidelines:\n1. No Spam\n2. Be Clear\n3. Wait for Staff", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=HelpView())

# --- [4] Admin Dashboard (Control Channel) ---
class FormatView(View):
    def __init__(self, ch, content):
        super().__init__(timeout=60); self.ch, self.content = ch, content
    @discord.ui.button(label="Normal", style=discord.ButtonStyle.secondary)
    async def normal(self, inter, btn):
        await self.ch.send(self.content); await inter.response.send_message("Sent.", ephemeral=True)
    @discord.ui.button(label="Embed", style=discord.ButtonStyle.success)
    async def embed(self, inter, btn):
        e = discord.Embed(description=self.content, color=discord.Color.blue())
        e.set_author(name="NEXUS Announcement", icon_url=bot.user.display_avatar.url)
        await self.ch.send(embed=e); await inter.response.send_message("Embed Sent.", ephemeral=True)

class ChannelSel(Select):
    def __init__(self, content):
        self.c = content
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        options = [discord.SelectOption(label=f"#{c.name}", value=str(c.id)) for c in channels[:25]]
        super().__init__(placeholder="Select channel...", options=options)
    async def callback(self, inter):
        ch = bot.get_channel(int(self.values[0]))
        await inter.response.send_message(f"Target: {ch.mention}", view=FormatView(ch, self.c), ephemeral=True)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        await message.reply("**NEXUS Dashboard**", view=View().add_item(ChannelSel(message.content)))
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'NEXUS ULTRA ONLINE.'); change_status.start()

keep_alive()
bot.run(TOKEN)
