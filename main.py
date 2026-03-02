import discord
from discord.ext import commands
from discord import app_commands
import os
from keep_alive import keep_alive
from discord.ui import Select, View, Button

# --- Bot Setup ---
TOKEN = os.environ.get("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1477923902834475080 # Tickets ke liye
ADMIN_CONTROL_CHANNEL = 1477954227442679910 # Isme Panel chalega

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")

bot = MyBot()

# --- [1] Support System (Tickets) ---
class SupportModal(discord.ui.Modal, title='NEXUS Support Form'):
    user_msg = discord.ui.TextInput(
        label='How can we help you?',
        style=discord.TextStyle.paragraph,
        placeholder='Type your message or query here...',
        required=True,
        min_length=10,
    )

    async def on_submit(self, interaction: discord.Interaction):
        log_channel = bot.get_channel(LOG_CHANNEL_ID)
        embed = discord.Embed(title="📩 New Support Ticket", color=discord.Color.green())
        embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.name})", inline=True)
        embed.add_field(name="User ID", value=interaction.user.id, inline=True)
        embed.add_field(name="Message", value=self.user_msg.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if log_channel:
            await log_channel.send(embed=embed)
            await interaction.response.send_message("Sent to NEXUS team!", ephemeral=True)
        else:
            await interaction.response.send_message("Error: Log channel not found!", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary, emoji="📩")
    async def contact_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportModal())

@bot.tree.command(name="help", description="Get professional support from NEXUS Team")
async def help_slash(interaction: discord.Interaction):
    embed = discord.Embed(title="NEXUS | Professional Support Portal", color=discord.Color.blue())
    await interaction.response.send_message(embed=embed, view=HelpView())

# --- [2] Master Control Panel (Dropdown & Buttons) ---

class MessageFormatView(View):
    """Buttons to choose Normal or Embed message"""
    def __init__(self, target_channel, content):
        super().__init__(timeout=60)
        self.target_channel = target_channel
        self.content = content

    @discord.ui.button(label="Normal Text", style=discord.ButtonStyle.secondary, emoji="📝")
    async def send_normal(self, interaction: discord.Interaction, button: Button):
        await self.target_channel.send(self.content)
        await interaction.response.send_message(f"✅ Sent to {self.target_channel.mention}", ephemeral=True)

    @discord.ui.button(label="Embed Message", style=discord.ButtonStyle.success, emoji="💎")
    async def send_embed(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(description=self.content, color=discord.Color.blue())
        embed.set_author(name="NEXUS Support™", icon_url=bot.user.display_avatar.url)
        await self.target_channel.send(embed=embed)
        await interaction.response.send_message(f"✅ Embed sent to {self.target_channel.mention}", ephemeral=True)

class ChannelDropdown(Select):
    """Dropdown to list server channels"""
    def __init__(self, content):
        self.msg_content = content
        options = []
        # Pehle 25 text channels fetch karega
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        for channel in channels[:25]:
            options.append(discord.SelectOption(label=channel.name, value=str(channel.id), emoji="📁"))
        
        super().__init__(placeholder="Kahan bhejna hai? Channel chuno...", options=options)

    async def callback(self, interaction: discord.Interaction):
        target_ch = bot.get_channel(int(self.values[0]))
        view = MessageFormatView(target_ch, self.msg_content)
        await interaction.response.send_message(f"📍 Target: {target_ch.mention}\nAb format chuno:", view=view, ephemeral=True)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Master Control Logic
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        # Bas normal message type karo, bot dropdown dikha dega
        view = View()
        view.add_item(ChannelDropdown(message.content))
        await message.reply("🚀 **NEXUS Control Panel**\nChannel select karein:", view=view)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

keep_alive()
bot.run(TOKEN)
