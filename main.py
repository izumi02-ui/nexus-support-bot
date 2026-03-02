import discord
from discord.ext import commands
from discord import app_commands
import os
from keep_alive import keep_alive
from discord.ui import Select, View, Button

# --- Bot Configuration ---
TOKEN = os.environ.get("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1477923902834475080  # Support Ticket Logs
ADMIN_CONTROL_CHANNEL = 1477954227442679910  # Admin Control Room

intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True
intents.members = True 

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")

bot = MyBot()

# --- [1] Support System (Modal & Buttons) ---
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
        
        embed = discord.Embed(title="New Support Ticket", color=discord.Color.green())
        embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.name})", inline=True)
        embed.add_field(name="User ID", value=interaction.user.id, inline=True)
        embed.add_field(name="Message", value=self.user_msg.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if log_channel:
            await log_channel.send(embed=embed)
            await interaction.response.send_message("Your message has been sent to the NEXUS team!", ephemeral=True)
        else:
            await interaction.response.send_message("Error: Log channel not found.", ephemeral=True)

class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary, emoji="📩")
    async def contact_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportModal())

@bot.tree.command(name="help", description="Get professional support from NEXUS Team")
async def help_slash(interaction: discord.Interaction):
    description = (
        "**Welcome to NEXUS Support™**\n\n"
        "We provide seamless assistance and top-tier solutions for all your queries. "
        "Click the button below to submit your request."
    )
    embed = discord.Embed(
        title="NEXUS | Professional Support Portal",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text="NEXUS Support - Excellence in Service")
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed, view=HelpView())

# --- [2] Master Control Panel (Dropdown & Media Support) ---

class MessageFormatView(View):
    def __init__(self, target_channel, content):
        super().__init__(timeout=60)
        self.target_channel = target_channel
        self.content = content

    @discord.ui.button(label="Normal Text", style=discord.ButtonStyle.secondary)
    async def send_normal(self, interaction: discord.Interaction, button: Button):
        await self.target_channel.send(self.content)
        await interaction.response.send_message(f"Message delivered to {self.target_channel.mention}", ephemeral=True)

    @discord.ui.button(label="Embed Message", style=discord.ButtonStyle.success)
    async def send_embed(self, interaction: discord.Interaction, button: Button):
        embed = discord.Embed(description=self.content, color=discord.Color.blue())
        embed.set_author(name="NEXUS Support™", icon_url=bot.user.display_avatar.url)
        
        # Check if the content is an image link to show it properly in Embed
        if any(ext in self.content.lower() for ext in ['.jpg', '.jpeg', '.png', '.gif', '.webp']):
            embed.set_image(url=self.content)
            embed.description = "" # Clear text if it's just an image

        await self.target_channel.send(embed=embed)
        await interaction.response.send_message(f"Embed delivered to {self.target_channel.mention}", ephemeral=True)

class ChannelDropdown(Select):
    def __init__(self, content):
        self.msg_content = content
        options = []
        channels = [c for c in bot.get_all_channels() if isinstance(c, discord.TextChannel)]
        for channel in channels[:25]: # Max 25 channels for Discord UI
            options.append(discord.SelectOption(label=channel.name, value=str(channel.id)))
        
        super().__init__(placeholder="Select the target channel...", options=options)

    async def callback(self, interaction: discord.Interaction):
        target_ch = bot.get_channel(int(self.values[0]))
        view = MessageFormatView(target_ch, self.msg_content)
        await interaction.response.send_message(f"Target: {target_ch.mention}. Choose Format:", view=view, ephemeral=True)

@bot.event
async def on_message(message):
    if message.author == bot.user:
        return

    # Master Control Logic for Admin Channel
    if message.channel.id == ADMIN_CONTROL_CHANNEL:
        view = View()
        view.add_item(ChannelDropdown(message.content))
        await message.reply("NEXUS Control Panel: Select a channel for delivery.", view=view)

    await bot.process_commands(message)

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

keep_alive()
bot.run(TOKEN)
