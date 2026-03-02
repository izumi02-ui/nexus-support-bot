import discord
from discord.ext import commands
from discord import app_commands
import os
from keep_alive import keep_alive

# Bot Setup
TOKEN = os.environ.get("DISCORD_TOKEN")
LOG_CHANNEL_ID = 1477923902834475080 # Jo ID tumne di thi

intents = discord.Intents.default()
intents.message_content = True

class MyBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix="!", intents=intents)

    async def setup_hook(self):
        # Slash commands ko register karne ke liye
        await self.tree.sync()
        print(f"Synced slash commands for {self.user}")

bot = MyBot()

# --- Modal (Pop-up Form) Logic ---
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
        
        # User Info Embed for Admin
        embed = discord.Embed(title="📩 New Support Ticket", color=discord.Color.green())
        embed.add_field(name="User", value=f"{interaction.user.mention} ({interaction.user.name})", inline=True)
        embed.add_field(name="User ID", value=interaction.user.id, inline=True)
        embed.add_field(name="Message", value=self.user_msg.value, inline=False)
        embed.set_thumbnail(url=interaction.user.display_avatar.url)

        if log_channel:
            await log_channel.send(embed=embed)
            await interaction.response.send_message("Your message has been sent to the NEXUS team! We will get back to you soon.", ephemeral=True)
        else:
            await interaction.response.send_message("Error: Log channel not found. Please contact admin.", ephemeral=True)

# --- Button Logic ---
class HelpView(discord.ui.View):
    def __init__(self):
        super().__init__(timeout=None)

    @discord.ui.button(label="Contact Support", style=discord.ButtonStyle.primary, emoji="📩")
    async def contact_callback(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.send_modal(SupportModal())

# --- Slash Command (/help) ---
@bot.tree.command(name="help", description="Get professional support from NEXUS Team")
async def help_slash(interaction: discord.Interaction):
    description = (
        "**Welcome to NEXUS Support™**\n\n"
        "We are dedicated to providing seamless assistance and top-tier solutions "
        "for all your queries. Our automated system ensures your concerns reach "
        "our experts instantly.\n\n"
        "**Click the button below to submit your request.**"
    )
    embed = discord.Embed(
        title="NEXUS | Professional Support Portal",
        description=description,
        color=discord.Color.blue()
    )
    embed.set_footer(text="NEXUS Support - Excellence in Service")
    embed.set_thumbnail(url=bot.user.display_avatar.url)
    
    await interaction.response.send_message(embed=embed, view=HelpView())

@bot.event
async def on_ready():
    print(f'Logged in as {bot.user}')

keep_alive()
bot.run(TOKEN)
