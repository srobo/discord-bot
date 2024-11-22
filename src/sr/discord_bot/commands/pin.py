from typing import cast, TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from sr.discord_bot.bot import BotClient

@app_commands.command(
    name='pin',
    description='Pin a message to the channel'
)
@app_commands.describe(
    message_url='Link of the message to pin',
)
@app_commands.rename(message_url='message')
async def pin_message(
    interaction: discord.interactions.Interaction["BotClient"],
    message_url: str,
) -> None:
    """Pin a message to the channel."""
    channel = cast(discord.TextChannel, interaction.channel)
    message_id = int(message_url.split('/')[-1])
    message = await channel.fetch_message(message_id)
    if message is None:
        return
    reason = "Pinned by " + interaction.user.mention
    await message.pin(reason=reason)
    await interaction.response.send_message(f"_{reason}_")

@app_commands.command(
    name='unpin',
    description='Unpin a message from the channel'
)
@app_commands.describe(
    message_url='Link of the message to unpin',
)
@app_commands.rename(message_url='message')
async def unpin_message(
    interaction: discord.interactions.Interaction["BotClient"],
    message_url: str,
) -> None:
    """Unpin a message from the channel."""
    channel = cast(discord.TextChannel, interaction.channel)
    message_id = int(message_url.split('/')[-1])
    message = await channel.fetch_message(message_id)
    if message is None:
        return
    reason = "Unpinned by " + interaction.user.mention
    await message.unpin(reason=reason)
    await interaction.response.send_message(f"_{reason}_")
