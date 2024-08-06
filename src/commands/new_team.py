import discord
from discord import app_commands, interactions
from discord.app_commands import locale_str

from src.constants import TEAM_CATEGORY_NAME, PASSWORDS_CHANNEL_NAME, ROLE_PREFIX

REASON = "Created via command"


@discord.app_commands.command(
    name=locale_str('team_new', en='new team', de='team hinzufügen'),
    description='Creates a role and channel for a team',
    extras={
        'default_member_permissions': 0,
    },
)
@app_commands.describe(
    tla='Three Letter Acronym (e.g. SRZ)',
    name='Name of the team',
    password="Password required for joining the team",
)
async def new_team(interaction: discord.interactions.Interaction, tla: str, name: str, password: str):
    guild: discord.Guild = interaction.guild
    category = discord.utils.get(guild.categories, name=TEAM_CATEGORY_NAME)
    role_name = f"{ROLE_PREFIX}{tla.upper()}"

    if discord.utils.get(guild.roles, name=role_name) is not None:
        await interaction.response.send_message(f"{role_name} already exists", ephemeral=True)
        return

    role = await guild.create_role(
        reason=REASON,
        name=role_name,
    )
    channel = await guild.create_text_channel(
        reason=REASON,
        name=f"team-{tla}",
        topic=name,
        category=category,
        overwrites={
            guild.default_role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False),
            role: discord.PermissionOverwrite()
        }
    )
    await _save_password(guild, tla, password)
    await interaction.response.send_message(f"<@&{role.id}> and <#{channel.id}> created!", ephemeral=True)


async def _save_password(guild: discord.Guild, tla: str, password: str):
    channel: discord.TextChannel = discord.utils.get(guild.channels, name=PASSWORDS_CHANNEL_NAME)
    await channel.send(f"```{tla}:{password}```")
