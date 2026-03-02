import discord
from discord.ext import commands, tasks
from discord import app_commands
import os
import asyncio
from keep_alive import keep_alive
from discord.ui import Select, View, Button

# --- Bot Configuration ---
TOKEN = os.environ.get("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1477923902834475080  # Tickets log channel
ADMIN_CONTROL_CHANNEL = 1477954227442679910  # Admin dashboard channel

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Globally syncing commands for Servers and DMs
        await self.tree.sync()
        print(f"NEXUS System: Commands synced for {self.user}")

bot = MyBot()

# --- [Rotating Streaming Status Task] ---
@tasks.loop(seconds=10)
async def change_status():
    # Professional rotating streaming status (Purple Icon)
    # Note: Twitch URL is used only to trigger the purple 'Live' status
    status_list = [
        discord.Streaming(name="NEXUS Support | /help", url="https://www.twitch.tv/discord"),
        discord.Streaming(name=f"over {len(bot.users)} members", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="DM me for any queries 📩", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="Excellence in Service", url="https://www.twitch.tv/discord"),
        discord.Streaming(name="Processing Tickets...", url="https://www.twitch.tv/discord")
    ]
    for status in status_list:
        await bot.change_presence(activity=status)
        await asyncio.sleep(10)

# --- [1] Support System (Modal & Buttons) ---
class SupportModal(discord.ui.Modal, title='NEXUS Support Form'):
    user_msg = discord.ui.TextInput(
        label='How can we help you?',
        style=discord.TextStyle.paragraph,
        placeholder='Please describe your request in detail...',
        required=True,
        min_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        
        # Checking if request is from DM or Server
        location = "Direct Message" if interaction.guild is None else f"Server: {interaction.guild.name}"
        
        embed = discord.Embed(title="New Support Ticket", color=discord.Color.green())
        embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.name})", inline=True)
        embed.add_field(name="Source", value=location, inline=True)
        embed.add_field(name="Message", value=self.user_msg.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)
        embed.set_footer(text=f"User ID: {interaction.user.id}")

        if log_channel:
            await log_channel.send(embed=embed)
            await interaction.response.send_message("Your message has been successfully sent to the NEXUS team.", ephemeral=True)
        else:
            await interaction.response.send_message("Error: Log channel not found. Contact Admin.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary, emoji="📩")
    async def contact_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportModal())

# Help command set for both Servers and DMs
@bot.tree.command(name="help", description="Get professional support from NEXUS Team")
@app_commands.allowed_contexts(guilds=True, dms=True, private_channels=True)
@app_commands.allowed_installs(guilds=True, users=True)
async def help_slash(interaction: discord.Interaction):
    description = (
        "**Welcome to NEXUS Support Portal™**\n\n"
        "We provide high-end assistance and automated solutions for your queries. "
        "Click the button below to submit your ticket directly to our staff."
    )
    embed = discord.Embed(
        title="NEXUS | Professional Support",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text="Excellence in Service")
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed, view=HelpView())

# --- [2] Master Control Panel (Admin Logic) ---

class MessageFormatView(View):
    def __init__(self, target_channel, content):
        super().__init__(timeout=60)
        self.target_channel = target_channel
        self.content = content

    @discord.ui.button(label="Normal Text", style=discord.ButtonStyle.secondary)
    async def send_normal(self, interaction: discord.Interaction, button: Button):
        await self.target_channel.send(self.content)
        await interaction.response.send_message(f"Delivered to {self.target_channel.mention}", ephemeral=True)

    @discord.ui.button(label="Embed Message", style=discord.ButtonStyle.success)
    async def send_embed(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(description=self.content, color=discord.Color.blue())
        embed.set_author(name="NEXUS Support™", icon_url=bot.user.display_avatar.url)
        
        # Advanced Image/GIF Detection
        if any(ext in self.content.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            embed.set_image(url=self.content)
            embed.description = "" 

        await self.target_channel.send(embed=embed)
        await interaction.response.send_message(f"Embed delivered to {self.target_channel.mention}", ephemeral=True)

class ChannelDropdown(Select):
    def __init__(self, content):
        self.msg_content = content
        options = []
        # Dynamic channel list
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        for channel in channels[:25]:
            options.append(discord.SelectOption(label=f"#{channel.name}", value=str(channel.id)))
        
        super().__init__(placeholder="Select the destination channel...", options=options)

    async def callback(self, interaction: discord.Interaction):
        target_ch = bot.get_channel(int(self.values[0]))
        view = MessageFormatView(target_ch, self.msg_content)
        await interaction.response.send_message(f"Target: {target_ch.mention}. Choose Format:", view=view, ephemeral=True)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Master Control for Admin Channel
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        view = View()
        view.add_item(ChannelDropdown(message.content))
        await message.reply("**NEXUS Control Panel**\nSelect a channel for message delivery:", view=view)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'NEXUS Bot is online: {bot.user}')
    # Start streaming status rotation loop
    if not change_status.is_running():
        change_status.start()

keep_alive()
bot.run(TOKEN)
