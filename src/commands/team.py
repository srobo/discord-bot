from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from src.bot import BotClient

from src.constants import (
    ROLE_PREFIX,
    TEAM_CATEGORY_NAME,
    PASSWORDS_CHANNEL_NAME,
)

REASON = "Created via command by "


@app_commands.guild_only()
@app_commands.default_permissions()
class Team(app_commands.Group):
    pass


group = Team()


@group.command(
    name='new',
    description='Creates a role and channel for a team',
)
@app_commands.describe(
    tla='Three Letter Acronym (e.g. SRZ)',
    name='Name of the team',
    password="Password required for joining the team",
)
async def new_team(interaction: discord.interactions.Interaction["BotClient"], tla: str, name: str,
                   password: str) -> None:
    guild: discord.Guild | None = interaction.guild
    if guild is None:
        await interaction.response.send_message("No guild found", ephemeral=True)
        return

    category = discord.utils.get(guild.categories, name=TEAM_CATEGORY_NAME)
    role_name = f"{ROLE_PREFIX}{tla.upper()}"

    if discord.utils.get(guild.roles, name=role_name) is not None:
        await interaction.response.send_message(f"{role_name} already exists", ephemeral=True)
        return

    role = await guild.create_role(
        reason=REASON + interaction.user.name,
        name=role_name,
    )
    channel = await guild.create_text_channel(
        reason=REASON + interaction.user.name,
        name=f"team-{tla.lower()}",
        topic=name,
        category=category,
        overwrites={
            guild.default_role: discord.PermissionOverwrite(
                read_messages=False,
                send_messages=False),
            interaction.client.volunteer_role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            ),
            role: discord.PermissionOverwrite(
                read_messages=True,
                send_messages=True,
            )
        }
    )
    await _save_password(guild, tla, password)
    await interaction.response.send_message(f"{role.mention} and {channel.mention} created!", ephemeral=True)


async def _save_password(guild: discord.Guild, tla: str, password: str) -> None:
    channel: discord.TextChannel | None = discord.utils.get(guild.text_channels, name=PASSWORDS_CHANNEL_NAME)
    if channel is not None:
        await channel.send(f"```\n{tla}:{password}\n```")
