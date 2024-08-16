from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from src.bot import BotClient

from src.constants import (
    ROLE_PREFIX,
    SPECIAL_ROLE,
    SPECIAL_TEAM,
    CHANNEL_PREFIX,
)

REASON = "A correct password was entered."


@discord.app_commands.command(  # type:ignore[arg-type]
    name='join',
    description='Join a team using a password',
)
@app_commands.describe(
    password="Your team's password",
)
async def join(interaction: discord.Interaction["BotClient"], password: str) -> None:
    member: discord.User | discord.Member | None = interaction.user
    if member is None or isinstance(member, discord.User):
        return

    if interaction.guild is None or not isinstance(interaction.channel, discord.TextChannel):
        return
    guild: discord.Guild = interaction.guild

    channel: discord.TextChannel = interaction.channel
    if channel is None or not channel.name.startswith(CHANNEL_PREFIX):
        return

    chosen_team = await find_team(interaction.client, member, password)
    if chosen_team:
        if chosen_team == SPECIAL_TEAM:
            role_name = SPECIAL_ROLE
        else:
            # Add them to the 'verified' role.
            # This doesn't happen in special cases because we expect a second
            # step (outside of this bot) before verifying them.

            await member.add_roles(
                interaction.client.verified_role,
                reason="A correct password was entered.",
            )

            role_name = f"{ROLE_PREFIX}{chosen_team}"

        # Add them to that specific role
        specific_role = discord.utils.get(guild.roles, name=role_name)
        if specific_role is None:
            interaction.client.logger.error(f"Specified role '{chosen_team}' does not exist")
        else:
            await member.add_roles(
                specific_role,
                reason="Correct password for this role was entered.",
            )
            interaction.client.logger.info(f"gave user '{member.name}' the {role_name} role.")

        if chosen_team != SPECIAL_TEAM:
            await interaction.client.announce_channel.send(
                f"Welcome {member.mention} from team {chosen_team}",
            )
            interaction.client.logger.info(f"Sent welcome announcement for '{member.name}'")

        await interaction.response.defer()
        await channel.delete()
        interaction.client.logger.info(
            f"deleted channel '{channel.name}' because verification has completed.",
        )
    else:
        await interaction.response.send_message("Incorrect password.", ephemeral=True)


async def find_team(client: "BotClient", member: discord.Member, entered: str) -> str | None:
    async for team_name, password in client.load_passwords():
        if password in entered.lower():
            client.logger.info(
                f"'{member.name}' entered the correct password for {team_name}",
            )
            # Password was correct!
            return team_name
    return None
