import textwrap

import discord
import logging

from .constants import *
from typing import Tuple, AsyncGenerator


class BotClient(discord.Client):
    logger: logging.Logger

    def __init__(self, logger: logging.Logger, *, loop=None, **options):
        super().__init__(loop=loop, **options)
        self.logger = logger

    async def on_ready(self) -> None:
        self.logger.info(f"{self.user} has connected to Discord!")

    async def on_member_join(self, member: discord.Member) -> None:
        name = member.display_name
        self.logger.info(f"Member {name} joined")
        guild: discord.Guild = member.guild
        join_channel_category = discord.utils.get(guild.categories, name=WELCOME_CATEGORY_NAME)
        # Create a new channel with that user able to write
        channel: discord.TextChannel = await guild.create_text_channel(
            f'{CHANNEL_PREFIX}{name}',
            category=join_channel_category,
            reason="User joined server, creating welcome channel.",
            overwrites={
                guild.default_role: discord.PermissionOverwrite(
                    read_messages=False,
                    send_messages=False),
                member: discord.PermissionOverwrite(read_messages=True, send_messages=True),
                guild.me: discord.PermissionOverwrite(read_messages=True, send_messages=True),
            },
        )
        await channel.send(textwrap.dedent(
            f"""Welcome {member.mention}!
            To gain access, you must send a message in this channel with the password for your group.

            *Don't have the password? it should have been sent with this join link to your team leader*
            """,
        ))
        self.logger.info(f"Created welcome channel for '{name}'")

    async def on_member_remove(self, member: discord.Member) -> None:
        name = member.display_name
        self.logger.info(f"Member '{name}' left")
        join_channel_category: discord.CategoryChannel = discord.utils.get(
            member.guild.categories,
            name=WELCOME_CATEGORY_NAME,
        )
        channel: discord.TextChannel
        for channel in join_channel_category.channels:
            # If the only user able to see it is the bot, then delete it.
            if channel.overwrites.keys() == {member.guild.me}:
                await channel.delete()
                self.logger.info(f"Deleted channel '{channel.name}', because it has no users.")

    async def on_message(self, message: discord.Message) -> None:
        channel: discord.TextChannel = message.channel
        if not channel.name.startswith(CHANNEL_PREFIX):
            return

        chosen_team = ""
        async for team_name, password in self.load_passwords(message.guild):
            if password in message.content.lower():
                self.logger.info(
                    f"'{message.author.name}' entered the correct password for {team_name}",
                )
                # Password was correct!
                chosen_team = team_name

        if chosen_team:
            if chosen_team == SPECIAL_TEAM:
                role_name = SPECIAL_ROLE
            else:
                # Add them to the 'verified' role.
                # This doesn't happen in special cases because we expect a second
                # step (outside of this bot) before verifying them.
                role: discord.Role = discord.utils.get(message.guild.roles, name=VERIFIED_ROLE)
                await message.author.add_roles(role, reason="A correct password was entered.")

                role_name = f"{ROLE_PREFIX}{chosen_team}"

            # Add them to that specific role
            specific_role = discord.utils.get(message.guild.roles, name=role_name)
            await message.author.add_roles(
                specific_role,
                reason="Correct password for this role was entered.",
            )
            self.logger.info(f"gave user '{message.author.name}' the {role_name} role.")

            if chosen_team != SPECIAL_TEAM:
                announce_channel: discord.TextChannel = discord.utils.get(
                    message.guild.channels,
                    name=ANNOUNCE_CHANNEL_NAME,
                )
                await announce_channel.send(
                    f"Welcome {message.author.mention} from team {chosen_team}",
                )
                self.logger.info(f"Sent welcome announcement for '{message.author.name}'")

            await channel.delete()
            self.logger.info(f"deleted channel '{channel.name}' because verification has completed.")

    async def load_passwords(self, guild: discord.Guild) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Returns a mapping from role name to the password for that role.

        Reads from the first message of the channel named {PASSWORDS_CHANNEL_NAME}.
        The format should be as follows:
        ```
        teamname:password
        ```
        """
        channel: discord.TextChannel = discord.utils.get(
            guild.channels,
            name=PASSWORDS_CHANNEL_NAME,
        )
        message: discord.Message
        async for message in channel.history(limit=100, oldest_first=True):
            content: str = message.content.replace('`', '').strip()
            team, password = content.split(':')
            yield team.strip(), password.strip()
