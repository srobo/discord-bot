from typing import TYPE_CHECKING

import discord
from discord import app_commands

if TYPE_CHECKING:
    from sr.discord_bot.bot import BotClient


@app_commands.command(  # type:ignore[arg-type]
    name='passwd',
    description='Outputs or changes team passwords',
)
@app_commands.describe(
    tla='Three Letter Acronym (e.g. SRZ)',
    new_password='New password',
)
async def passwd(
    interaction: discord.interactions.Interaction["BotClient"],
    tla: str | None = None,
    new_password: str | None = None,
) -> None:
    if tla is None:
        passwords = interaction.client.passwords.items()
        message = "No team passwords set. The password for joining as a blueshirt is set using the TLA `SRZ`."
        if passwords:
            message = '\n'.join([f"**{team}:** {password}" for team, password in passwords])
        await interaction.response.send_message(message, ephemeral=True)
    else:
        tla = tla.upper()
        if new_password is not None:
            if isinstance(interaction.user, discord.Member) and not interaction.user.guild_permissions.administrator:
                await interaction.response.send_message(
                    "You do not have permission to change team passwords.",
                    ephemeral=True,
                )
                return
            interaction.client.set_password(tla, new_password)
            await interaction.response.send_message(f"The password for {tla} has been changed.", ephemeral=True)
        else:
            password = interaction.client.passwords[tla]
            await interaction.response.send_message(f"The password for {tla} is `{password}`", ephemeral=True)
