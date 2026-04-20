import discord
import datetime
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

# --- [1] Userinfo & Utility Commands ---

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
            # FIX: Try block for PyNaCl error handling
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
    if not data: return await interaction.response.send_message("✅ No restrictions found.", ephemeral=True)
    
    options = []
    for uid, info in list(data.items())[:25]:
        # Removing user objects from the bot's cache
        user = bot.get_user(int(uid))

        # If you find a user, show their name, otherwise just their ID.
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
    await interaction.response.send_message("NEXUS Security Management", view=View().add_item(select), ephemeral=True)

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

@bot.tree.command(name="help", description="NEXUS Support Portal")
async def help_slash(interaction: discord.Interaction):
    # Restriction Check
    res, reason = check_restriction(interaction.user.id)
    if res: 
        return await interaction.response.send_message(f"❌ Denied: {reason}", ephemeral=True)
    
    # --- Professional Embed Styling ---
    embed = discord.Embed(
        title="NEXUS SYSTEM ™ | Support Portal",
        description=(
            "**Welcome to NEXUS Support Portal™**\n"
            "We provide high-end assistance and automated solutions for your queries. "
            "Click the button below to submit your ticket directly to our staff.\n"
            "**━━━━━━━━━━━━━━━━━━━━━━━━━━**"
        ),
        color=0x2b2d31 
    )

    # --- LOGO / THUMBNAIL ---
    # This will display the bot logo on the top right.
    embed.set_thumbnail(url=bot.user.display_avatar.url)

    # Grid fields
    embed.add_field(name="📊 **Status**", value="`Online`", inline=True)
    embed.add_field(name="📡 **Ping**", value=f"`{round(bot.latency * 1000)}ms`", inline=True)
    embed.add_field(name="👥 **Users**", value=f"`{len(bot.users)}`", inline=True)

    # Support Instructions
    embed.add_field(
        name="🛠️ **Support Instructions**", 
        value=(
            "1. Click the **Contact Support** button below.\n"
            "2. Fill in your issue details in the form.\n"
            "3. Wait for a staff member to reach out."
        ), 
        inline=False
    )

    # Footer with Icon
    embed.set_footer(
        text=f"ID: {interaction.user.id} • NEXUS Security", 
        icon_url=bot.user.display_avatar.url
    )
    embed.timestamp = datetime.utcnow()

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

class ChannelSel(discord.ui.View):
    def __init__(self, content, attachments):
        super().__init__(timeout=None)
        self.msg_content = content
        self.msg_attachments = attachments
        
        # Priority Channels ki list (put your channel here)
        priority_names = ["staff-talk", "tickets-🎫-✓", "general-chat-💬", "rulebook-📜", "announcements", "rulebook-for-sutffs-📑", "polls", "media-saver-🎞️", "🎼-music-vc-guide", "store", "1487895838083514622"]
        options = []
        for name in priority_names:
            ch = discord.utils.get(bot.get_all_channels(), name=name)
            if ch:
                options.append(discord.SelectOption(label=f"#{ch.name}", value=str(ch.id)))
        
        if options:
            select = discord.ui.Select(
                custom_id="nexus_new_menu_v2", # This custom_id is required!
                placeholder="Select a priority channel...", 
                options=options
            )
            select.callback = self.callback
            self.add_item(select)

    async def callback(self, inter: discord.Interaction):
        ch = inter.guild.get_channel(int(inter.data['values'][0]))
        await inter.response.send_message(
            f"Target: {ch.mention}", 
            view=FormatView(ch, self.msg_content, self.msg_attachments), 
            ephemeral=True
        )


@bot.event
async def on_message(message):
    # 1. The rule to ignore bots (must have)
    if message.author == bot.user: 
        return

    # 2. [NEW] DM System: Welcome & Auto-Clean
    if isinstance(message.channel, discord.DMChannel):
        history = []
        # Will check only last 10 messages for speed
        async for msg in message.channel.history(limit=10):
            history.append(msg)
        
        # First message? Welcome embed send
        if len(history) <= 1:
            welcome_dm = discord.Embed(
                title="NEXUS SYSTEM ™ | DM Gateway",
                description=(
                    "Hello! You have reached the **NEXUS Support DM Gateway**.\n\n"
                    "**Quick Commands:**\n"
                    "• Use `/help` in a server for tickets.\n"
                    "• Describe your issue here for staff review.\n\n"
                    "**━━━━━━━━━━━━━━━━━━━━━━━━━━**"
                ),
                color=0x2b2d31
            )
            welcome_dm.set_thumbnail(url=bot.user.display_avatar.url)
            await message.channel.send(embed=welcome_dm)
        else:
            # Delete the rest of the messages except the Welcome message.
            for old_msg in history:
                if old_msg.author == bot.user:
                    # Gateway checks the word so that I don't delete the message
                    is_welcome = any("Gateway" in str(e.title) for e in old_msg.embeds)
                    if not is_welcome:
                        try: await old_msg.delete()
                        except: pass

    # 3. [KEEPING] Admin Dashboard Logic (what you asked for)
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        await message.reply("**NEXUS Dashboard**", view=ChannelSel(message.content, message.attachments))
    
    # 4. [CRITICAL] Connection Line: Without this, slash commands will not run
    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'NEXUS SUPREME ONLINE.'); 
    if not change_status.is_running():
        change_status.start()

@tasks.loop(seconds=20)
async def change_status():
    status = discord.Streaming(name="NEXUS | DM me for any queries 📩", url="https://twitch.tv/discord")
    await bot.change_presence(activity=status)


# --- 6. Advanced Admin Action System (Final Version) ---

ADMIN_PIN = "1234"  # Is PIN ko aap yahan se badal sakte hain

class FinalExecutionModal(discord.ui.Modal, title='⚠️ FINAL SECURITY CHECK'):
    pin_confirm = discord.ui.TextInput(label='Confirm PIN to Execute', placeholder='Enter PIN again...', min_length=4, max_length=4)

    def __init__(self, action_type, scope, targets=None):
        super().__init__()
        self.action_type = action_type
        self.scope = scope
        self.targets = targets

    async def on_submit(self, interaction: discord.Interaction):
        # Double PIN verification check
        if self.pin_confirm.value != ADMIN_PIN:
            return await interaction.response.send_message("❌ PIN mismatch! Operation aborted.", ephemeral=True)
        
        await interaction.response.defer(ephemeral=True)
        count = 0
        
        # Action Loop Logic
        for member in self.targets:
            # Safety Check: Apne se upar ke roles ya owner ko touch nahi karega
            if member.top_role >= interaction.guild.me.top_role or member.id == interaction.guild.owner_id:
                continue
            
            try:
                if self.action_type == "ban":
                    await member.ban(reason="NEXUS Admin Action")
                elif self.action_type == "kick":
                    await member.kick(reason="NEXUS Admin Action")
                elif self.action_type == "timeout":
                    await member.timeout(datetime.timedelta(days=1), reason="NEXUS Admin Action")
                elif self.action_type == "mute":
                    # Mute ke liye 'Muted' role hona zaroori hai
                    role = discord.utils.get(interaction.guild.roles, name="Muted")
                    if role: await member.add_roles(role)
                count += 1
            except:
                continue

        await interaction.followup.send(f"✅ **{self.action_type.upper()}** completed! Total: {count} members affected.", ephemeral=True)

class AmountInputModal(discord.ui.Modal, title='Enter Member Count'):
    amount = discord.ui.TextInput(label='How many members?', placeholder='Example: 10, 50, 100', required=True)

    def __init__(self, action_type):
        super().__init__()
        self.action_type = action_type

    async def on_submit(self, interaction: discord.Interaction):
        try:
            num = int(self.amount.value)
            # Server ke sabse purane (oldest) members ki list lega amount ke hisaab se
            targets = [m for m in interaction.guild.members if not m.bot][:num]
            await interaction.response.send_modal(FinalExecutionModal(self.action_type, "Amount", targets))
        except ValueError:
            await interaction.response.send_message("❌ Please enter a valid number!", ephemeral=True)

class ActionDetailsView(discord.ui.View):
    def __init__(self, action_type):
        super().__init__(timeout=60)
        self.action_type = action_type

    @discord.ui.button(label="Entire Server", style=discord.ButtonStyle.danger, emoji="☢️")
    async def entire_server(self, interaction: discord.Interaction, button: discord.ui.Button):
        targets = [m for m in interaction.guild.members if not m.bot]
        await interaction.response.send_modal(FinalExecutionModal(self.action_type, "Entire", targets))

    @discord.ui.button(label="By Amount", style=discord.ButtonStyle.primary, emoji="🔢")
    async def by_amount(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(AmountInputModal(self.action_type))

    @discord.ui.button(label="Specific Members", style=discord.ButtonStyle.secondary, emoji="👤")
    async def specific_members(self, interaction: discord.Interaction, button: discord.ui.Button):
        view = discord.ui.View()
        select = discord.ui.UserSelect(placeholder="Select up to 25 members...", max_values=25)
        
        async def select_callback(inter: discord.Interaction):
            await inter.response.send_modal(FinalExecutionModal(self.action_type, "Specific", select.values))
            
        select.callback = select_callback
        view.add_item(select)
        await interaction.response.send_message("Choose targets:", view=view, ephemeral=True)

class ActionSelectView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=60)

    @discord.ui.select(
        placeholder="Choose Moderation Action...",
        options=[
            discord.SelectOption(label="Ban", value="ban", emoji="🔨"),
            discord.SelectOption(label="Kick", value="kick", emoji="👢"),
            discord.SelectOption(label="Timeout", value="timeout", emoji="⏳"),
            discord.SelectOption(label="Mute", value="mute", emoji="🔇")
        ]
    )
    async def select_callback(self, interaction: discord.Interaction, select: discord.ui.Select):
        await interaction.response.send_message(f"Selected: **{select.values[0]}**. Choose scope:", view=ActionDetailsView(select.values[0]), ephemeral=True)

class InitialPinModal(discord.ui.Modal, title='Admin Authentication'):
    pin_input = discord.ui.TextInput(label='Enter Admin Key', placeholder='4-digit PIN required', min_length=4, max_length=4)

    async def on_submit(self, interaction: discord.Interaction):
        if self.pin_input.value == ADMIN_PIN:
            await interaction.response.send_message("✅ Identity Verified. Select Action:", view=ActionSelectView(), ephemeral=True)
        else:
            await interaction.response.send_message("❌ Access Denied! Invalid PIN.", ephemeral=True)

@bot.tree.command(name="action", description="High-level secure admin actions")
@app_commands.checks.has_permissions(administrator=True)
async def action_command(interaction: discord.Interaction):
    await interaction.response.send_modal(InitialPinModal())


# Most niche connection lines
keep_alive()
bot.run(TOKEN)
