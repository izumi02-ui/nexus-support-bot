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

intents = discord.Intents.all()

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

# --- [1] Janam Kundli & Utility Commands ---

@bot.tree.command(name="user_info", description="User ki poori janam kundli nikalen")
async def user_info(interaction: discord.Interaction, member: discord.Member = None):
    member = member or interaction.user
    roles = [role.mention for role in reversed(member.roles) if role.name != "@everyone"]
    embed = discord.Embed(title=f"👤 User Biodata: {member.name}", color=discord.Color.blue())
    embed.set_thumbnail(url=member.display_avatar.url)
    embed.add_field(name="ID", value=f"`{member.id}`", inline=True)
    embed.add_field(name="Account Created", value=member.created_at.strftime("%d %b %Y"), inline=False)
    embed.add_field(name="Joined Server", value=member.joined_at.strftime("%d %b %Y"), inline=False)
    embed.add_field(name=f"Roles [{len(roles)}]", value=" ".join(roles[:10]) if roles else "None", inline=False)
    await interaction.response.send_message(embed=embed)

@bot.tree.command(name="join", description="Connect bot to your VC")
@app_commands.checks.has_permissions(administrator=True)
async def join(interaction: discord.Interaction):
    await interaction.response.defer(ephemeral=True)
    if interaction.user.voice:
        channel = interaction.user.voice.channel
        try:
            # FIX: PyNaCl error handle karne ke liye try block
            if interaction.guild.voice_client:
                await interaction.guild.voice_client.move_to(channel)
            else:
                await channel.connect(timeout=20.0, reconnect=True)
            await interaction.followup.send(f"✅ Successfully joined **{channel.name}**")
        except Exception as e:
            # Screenshot fix: PyNaCl instruction
            await interaction.followup.send(f"❌ Voice Error: Please run `pip install pynacl` in your console.\nDetails: {e}")
    else:
        await interaction.followup.send("❌ Join a VC first!")

@bot.tree.command(name="leave", description="Disconnect bot from VC")
@app_commands.checks.has_permissions(administrator=True)
async def leave(interaction: discord.Interaction):
    if interaction.guild.voice_client:
        await interaction.guild.voice_client.disconnect()
        await interaction.response.send_message("🔌 Disconnected.", ephemeral=True)
    else:
        await interaction.response.send_message("❌ Not in a VC.", ephemeral=True)

@bot.tree.command(name="clear", description="Delete messages (e.g. 10)")
@app_commands.checks.has_permissions(manage_messages=True)
async def clear(interaction: discord.Interaction, amount: int):
    await interaction.response.defer(ephemeral=True)
    deleted = await interaction.channel.purge(limit=amount)
    await interaction.followup.send(f"🧹 Deleted `{len(deleted)}` messages.", ephemeral=True)

# --- [2] Security & Punishment System ---

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
        super().__init__(placeholder="Apply Punishment...", options=options, custom_id=f"p_sel_{user_id}")

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

@bot.tree.command(name="list_punishments", description="Manage banned/timeout users")
@app_commands.checks.has_permissions(administrator=True)
async def list_punishments(interaction: discord.Interaction):
    data = load_db()
    if not data: 
        return await interaction.response.send_message("✅ No restrictions found.", ephemeral=True)
    
    options = []
    # Database se IDs nikal kar unka username dhundna
    for uid, info in list(data.items())[:25]:
        # Bot ki cache se user object nikalna
        user = bot.get_user(int(uid))
        
        # Agar user mil gaya toh uska naam dikhao, nahi toh sirf ID
        display_name = f"{user.name}" if user else f"Unknown ({uid})"
        
        options.append(
            discord.SelectOption(
                label=display_name, 
                value=uid, 
                description=f"ID: {uid} | Type: {info['type']}"
            )
        )

    select = Select(placeholder="Choose user to release...", options=options)

    async def select_callback(inter):
        data.pop(select.values[0], None)
        save_db(data)
        await inter.response.send_message(f"✅ User `{select.values[0]}` restrictions cleared.", ephemeral=True)

    select.callback = select_callback
    await interaction.response.send_message("🛡️ **NEXUS Security Management**", view=View().add_item(select), ephemeral=True)

# --- [3] Help Portal ---

class SupportModal(discord.ui.Modal, title='NEXUS Support Form'):
    msg = discord.ui.TextInput(label='Message', style=discord.TextStyle.paragraph, placeholder='Details...', required=True, min_length=10)
    async def on_submit(self, interaction: discord.Interaction):
        log_ch = bot.get_channel(LOG_CHANNEL_ID)
        embed = discord.Embed(title="New Ticket", color=discord.Color.green())
        embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.id})")
        embed.add_field(name="Message", value=self.msg.value, inline=False)
        if log_ch:
            view = View(timeout=None).add_item(PunishDropdown(interaction.user.id))
            await log_ch.send(embed=embed, view=view)
            await interaction.response.send_message("✅ Sent to staff.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self): super().__init__(timeout=None)
    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary, emoji="📩")
    async def contact(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportModal())

@bot.tree.command(name="help", description="NEXUS Portal")
async def help_slash(interaction: discord.Interaction):
    res, reason = check_restriction(interaction.user.id)
    if res: return await interaction.response.send_message(f"❌ Denied: {reason}", ephemeral=True)
    
    embed = discord.Embed(title="NEXUS | Professional Support", color=discord.Color.blue())
    embed.add_field(name="Welcome to NEXUS Support Portal™", 
                    value="We provide high-end assistance and automated solutions for your queries. Click the button below to submit your ticket directly to our staff.", 
                    inline=False)
    embed.set_footer(text="Excellence in Service")
    await interaction.response.send_message(embed=embed, view=HelpView())

# --- [4] Admin Dashboard & Media Support ---

class FormatView(View):
    def __init__(self, ch, content, files):
        super().__init__(timeout=120)
        self.ch = ch
        self.content = content or ""
        self.files = files or []

    async def resend_files(self):
        new_files = []
        for attachment in self.files:
            try:
                file = await attachment.to_file()
                new_files.append(file)
            except:
                pass
        return new_files

    @discord.ui.button(label="Normal", style=discord.ButtonStyle.secondary)
    async def normal(self, inter: discord.Interaction, btn: Button):
        await inter.response.defer(ephemeral=True)

        files = await self.resend_files()
        await self.ch.send(content=self.content if self.content else None, files=files if files else None)

        await inter.followup.send("✅ Sent as Normal Message.", ephemeral=True)

    @discord.ui.button(label="Embed", style=discord.ButtonStyle.success)
    async def embed(self, inter: discord.Interaction, btn: Button):
        await inter.response.defer(ephemeral=True)

        embed = discord.Embed(
            description=self.content if self.content else "‎",
            color=discord.Color.blue()
        )
        embed.set_author(name="NEXUS Announcement", icon_url=bot.user.display_avatar.url)

        files = await self.resend_files()

        # Auto image preview
        for attachment in self.files:
            if attachment.filename.lower().endswith((".png", ".jpg", ".jpeg", ".gif", ".webp")):
                embed.set_image(url=attachment.url)
                break

        await self.ch.send(embed=embed, files=files if files else None)
        await inter.followup.send("✅ Sent as Embed.", ephemeral=True)

class ChannelSel(Select):
    def __init__(self, content, attachments):
        self.c, self.a = content, attachments
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        options = [discord.SelectOption(label=f"#{c.name}", value=str(c.id)) for c in channels[:25]]
        super().__init__(placeholder="Select channel...", options=options)
    
    async def callback(self, inter):
        ch = bot.get_channel(int(self.values[0]))
        await inter.response.send_message(f"Target: {ch.mention}", view=FormatView(ch, self.c, self.a), ephemeral=True)

@bot.event
async def on_message(message):
    if message.author == bot.user: return
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        await message.reply("**NEXUS Dashboard**", view=View().add_item(ChannelSel(message.content, message.attachments)))
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'NEXUS SUPREME ONLINE.'); 
    if not change_status.is_running():
        change_status.start()

@tasks.loop(seconds=20)
async def change_status():
    status = discord.Streaming(name="NEXUS | DM me for any queries 📩", url="https://discord.gg/Dkq6CPWfq")
    await bot.change_presence(activity=status)

keep_alive()
bot.run(TOKEN)
