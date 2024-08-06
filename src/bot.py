import os
import asyncio
import logging
import textwrap

import discord

from discord import app_commands

from typing import Tuple, AsyncGenerator

from src.constants import (
    ROLE_PREFIX,
    SPECIAL_ROLE,
    SPECIAL_TEAM,
    VERIFIED_ROLE,
    CHANNEL_PREFIX,
    ANNOUNCE_CHANNEL_NAME,
    WELCOME_CATEGORY_NAME,
    PASSWORDS_CHANNEL_NAME,
)

from src.commands.new_team import new_team


class BotClient(discord.Client):
    logger: logging.Logger
    guild: discord.Object
    verified_role: discord.Role
    special_role: discord.Role
    welcome_category: discord.CategoryChannel
    announce_channel: discord.TextChannel
    passwords_channel: discord.TextChannel

    def __init__(
        self,
        logger: logging.Logger,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        intents: discord.Intents = discord.Intents.none(),
    ):
        super().__init__(loop=loop, intents=intents)
        self.logger = logger
        self.tree = app_commands.CommandTree(self)
        guild_id = os.getenv('DISCORD_GUILD_ID')
        if guild_id is None or not guild_id.isnumeric():
            logger.error("Invalid guild ID")
            exit(1)
        self.guild = discord.Object(id=int())
        self.tree.add_command(new_team, guild=self.guild)

    async def setup_hook(self):
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)

    async def on_ready(self) -> None:
        self.logger.info(f"{self.user} has connected to Discord!")
        guild = self.get_guild(self.guild.id)
        if guild is None:
            logging.error(f"Guild {self.guild.id} not found!")
            exit(1)

        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE)
        special_role = discord.utils.get(guild.roles, name=SPECIAL_ROLE)
        welcome_category = discord.utils.get(guild.categories, name=WELCOME_CATEGORY_NAME)
        announce_channel = discord.utils.get(guild.text_channels, name=ANNOUNCE_CHANNEL_NAME)
        passwords_channel = discord.utils.get(guild.text_channels, name=PASSWORDS_CHANNEL_NAME)

        if (
            verified_role is None
            or special_role is None
            or welcome_category is None
            or announce_channel is None
            or passwords_channel is None
        ):
            logging.error("Roles and channels are not set up")
            exit(1)
        else:
            self.verified_role = verified_role
            self.special_role = special_role
            self.welcome_category = welcome_category
            self.announce_channel = announce_channel
            self.passwords_channel = passwords_channel

    async def on_member_join(self, member: discord.Member) -> None:
        name = member.display_name
        self.logger.info(f"Member {name} joined")
        guild: discord.Guild = member.guild
        # Create a new channel with that user able to write
        channel: discord.TextChannel = await guild.create_text_channel(
            f'{CHANNEL_PREFIX}{name}',
            category=self.welcome_category,
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
        for channel in self.welcome_category.channels:
            # If the only user able to see it is the bot, then delete it.
            if channel.overwrites.keys() == {member.guild.me}:
                await channel.delete()
                self.logger.info(f"Deleted channel '{channel.name}', because it has no users.")

    async def on_message(self, message: discord.Message) -> None:
        if not isinstance(message.channel, discord.TextChannel):
            return
        channel: discord.TextChannel = message.channel
        if channel is None or message.guild is None or not channel.name.startswith(CHANNEL_PREFIX):
            return
        if isinstance(message.author, discord.User):
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

                await message.author.add_roles(
                    self.verified_role,
                    reason="A correct password was entered.",
                )

                role_name = f"{ROLE_PREFIX}{chosen_team}"

            # Add them to that specific role
            specific_role = discord.utils.get(message.guild.roles, name=role_name)
            if specific_role is None:
                self.logger.error(f"Specified role '{chosen_team}' does not exist")
            else:
                await message.author.add_roles(
                    specific_role,
                    reason="Correct password for this role was entered.",
                )
                self.logger.info(f"gave user '{message.author.name}' the {role_name} role.")

            if chosen_team != SPECIAL_TEAM:
                await self.announce_channel.send(
                    f"Welcome {message.author.mention} from team {chosen_team}",
                )
                self.logger.info(f"Sent welcome announcement for '{message.author.name}'")

            await channel.delete()
            self.logger.info(
                f"deleted channel '{channel.name}' because verification has completed.",
            )

    async def load_passwords(self, guild: discord.Guild) -> AsyncGenerator[Tuple[str, str], None]:
        """
        Returns a mapping from role name to the password for that role.

        Reads from the first message of the channel named {PASSWORDS_CHANNEL_NAME}.
        The format should be as follows:
        ```
        teamname:password
        ```
        """
        message: discord.Message
        async for message in self.passwords_channel.history(limit=100, oldest_first=True):
            content: str = message.content.replace('`', '').strip()
            team, password = content.split(':')
            yield team.strip(), password.strip()