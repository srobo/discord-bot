from typing import TYPE_CHECKING, Iterable

import discord
from discord import app_commands, role

from src.commands.ui import TeamDeleteConfirm

if TYPE_CHECKING:
    from src.bot import BotClient

from src.constants import (
    ROLE_PREFIX,
    TEAM_CATEGORY_NAME,
    PASSWORDS_CHANNEL_NAME,
    TEAM_VOICE_CATEGORY_NAME,
)

TEAM_CREATED_REASON = "Created via command by "


@app_commands.guild_only()
@app_commands.default_permissions()
class Team(app_commands.Group):
    pass


group = Team()


def permissions(client: "BotClient", team: discord.Role) -> dict[discord.Role, discord.PermissionOverwrite]:
    return {
        client.guild.default_role: discord.PermissionOverwrite(
            read_messages=False,
            send_messages=False),
        client.volunteer_role: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
        ),
        team: discord.PermissionOverwrite(
            read_messages=True,
            send_messages=True,
        )
    }


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
        reason=TEAM_CREATED_REASON + interaction.user.name,
        name=role_name,
    )
    channel = await guild.create_text_channel(
        reason=TEAM_CREATED_REASON + interaction.user.name,
        name=f"team-{tla.lower()}",
        topic=name,
        category=category,
        overwrites=permissions(interaction.client, role)
    )
    await _save_password(guild, tla, password)
    await interaction.response.send_message(f"{role.mention} and {channel.mention} created!", ephemeral=True)


async def _save_password(guild: discord.Guild, tla: str, password: str) -> None:
    channel: discord.TextChannel | None = discord.utils.get(guild.text_channels, name=PASSWORDS_CHANNEL_NAME)
    if channel is not None:
        await channel.send(f"```\n{tla.upper()}:{password}\n```")


@group.command(
    name='delete',
    description='Deletes a role and channel for a team',
)
@app_commands.describe(
    tla='Three Letter Acronym (e.g. SRZ)',
)
async def delete_team(interaction: discord.interactions.Interaction["BotClient"], tla: str) -> None:
    guild: discord.Guild | None = interaction.guild
    role: discord.Role | None = discord.utils.get(guild.roles, name=f"{ROLE_PREFIX}{tla.upper()}")
    if guild is None:
        return

    if role is None:
        await interaction.response.send_message(f"Team {tla.upper()} does not exist", ephemeral=True)
        return

    view = TeamDeleteConfirm(guild, tla)

    await interaction.response.send_message(f"Are you sure you want to delete Team {tla.upper()}\n\n"
                                            f"This will kick all of its members.", view=view, ephemeral=True)
    await view.wait()
    if view.value:
        await interaction.edit_original_response(content=f"_Deleting Team {tla.upper()}..._", view=None)
        guild: discord.Guild | None = interaction.guild
        reason = f"Team removed by {interaction.user.name}"
        if role is not None:
            for member in role.members:
                await member.send(f"Your {guild.name} team has been removed.")
                await member.kick(reason=reason)

            for channel in guild.channels:
                if channel.name.startswith(f"team-{tla.lower()}"):
                    await channel.delete(reason=reason)

            await role.delete(reason=reason)

            if not interaction.channel.name.startswith(f"team-{tla.lower()}"):
                await interaction.edit_original_response(content=f"Team {tla.upper()} has been deleted")


@group.command(
    name='voice',
    description='Create a voice channel for a team',
)
@app_commands.describe(
    tla='Three Letter Acronym (e.g. SRZ)',
)
async def create_voice(interaction: discord.interactions.Interaction["BotClient"], tla: str) -> None:
    guild: discord.Guild | None = interaction.guild
    role: discord.Role | None = discord.utils.get(guild.roles, name=f"{ROLE_PREFIX}{tla.upper()}")
    if guild is None:
        return

    if role is None:
        await interaction.response.send_message(f"Team {tla.upper()} does not exist", ephemeral=True)
        return

    category = discord.utils.get(guild.categories, name=TEAM_VOICE_CATEGORY_NAME)
    channel = await guild.create_voice_channel(
        f"team-{tla.lower()}",
        category=category,
        overwrites=permissions(interaction.client, role)
    )
    await interaction.response.send_message(f"{channel.mention} created!", ephemeral=True)


@group.command(
    name='channel',
    description='Create a secondary channel for a team',
)
@app_commands.describe(
    tla='Three Letter Acronym (e.g. SRZ)',
    suffix='Channel name suffix (e.g. design)',
)
async def create_team_channel(
    interaction: discord.interactions.Interaction["BotClient"],
    tla: str,
    suffix: str,
) -> None:
    guild: discord.Guild | None = interaction.guild
    if guild is None:
        return

    main_channel = discord.utils.get(guild.text_channels, name=f"team-{tla.lower()}")
    category = discord.utils.get(guild.categories, name=TEAM_CATEGORY_NAME)

    if category is None or main_channel is None:
        await interaction.response.send_message(f"Team {tla.upper()} does not exist", ephemeral=True)
        return

    new_channel = await guild.create_text_channel(
        name=f"team-{tla.lower()}-{suffix.lower()}",
        category=category,
        overwrites=main_channel.overwrites,
        position=main_channel.position + 1,
        reason=TEAM_CREATED_REASON
    )
    await interaction.response.send_message(f"{new_channel.mention} created!", ephemeral=True)
