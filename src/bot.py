import os
import json
import asyncio
import logging

import discord
from discord import app_commands
from discord.ext import tasks

from src.rss import check_posts
from src.constants import (
    SPECIAL_ROLE,
    VERIFIED_ROLE,
    CHANNEL_PREFIX,
    VOLUNTEER_ROLE,
    FEED_CHANNEL_NAME,
    FEED_CHECK_INTERVAL,
    ANNOUNCE_CHANNEL_NAME,
    WELCOME_CATEGORY_NAME,
)
from src.commands.join import join
from src.commands.logs import logs
from src.commands.team import (
    Team,
    new_team,
    delete_team,
    export_team,
    create_voice,
    create_team_channel,
)
from src.commands.passwd import passwd


class BotClient(discord.Client):
    logger: logging.Logger
    guild: discord.Guild | discord.Object
    verified_role: discord.Role
    special_role: discord.Role
    volunteer_role: discord.Role
    welcome_category: discord.CategoryChannel
    announce_channel: discord.TextChannel
    passwords: dict[str, str]
    feed_channel: discord.TextChannel

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
            self.logger.error("Invalid guild ID")
            exit(1)
        self.guild = discord.Object(id=int(guild_id))
        team = Team()
        team.add_command(new_team)
        team.add_command(delete_team)
        team.add_command(create_voice)
        team.add_command(create_team_channel)
        team.add_command(export_team)
        self.tree.add_command(team, guild=self.guild)
        self.tree.add_command(passwd, guild=self.guild)
        self.tree.add_command(join, guild=self.guild)
        self.tree.add_command(logs, guild=self.guild)
        self.load_passwords()

    async def setup_hook(self) -> None:
        # This copies the global commands over to your guild.
        self.tree.copy_global_to(guild=self.guild)
        await self.tree.sync(guild=self.guild)
        self.check_for_new_blog_posts.start()

    async def on_ready(self) -> None:
        self.logger.info(f"{self.user} has connected to Discord!")
        guild = self.get_guild(self.guild.id)
        if guild is None:
            logging.error(f"Guild {self.guild.id} not found!")
            exit(1)
        self.guild = guild

        verified_role = discord.utils.get(guild.roles, name=VERIFIED_ROLE)
        special_role = discord.utils.get(guild.roles, name=SPECIAL_ROLE)
        volunteer_role = discord.utils.get(guild.roles, name=VOLUNTEER_ROLE)
        welcome_category = discord.utils.get(guild.categories, name=WELCOME_CATEGORY_NAME)
        announce_channel = discord.utils.get(guild.text_channels, name=ANNOUNCE_CHANNEL_NAME)
        feed_channel = discord.utils.get(guild.text_channels, name=FEED_CHANNEL_NAME)

        if (
            verified_role is None
            or special_role is None
            or volunteer_role is None
            or welcome_category is None
            or announce_channel is None
            or feed_channel is None
        ):
            logging.error("Roles and channels are not set up")
            exit(1)
        else:
            self.verified_role = verified_role
            self.special_role = special_role
            self.volunteer_role = volunteer_role
            self.welcome_category = welcome_category
            self.announce_channel = announce_channel
            self.feed_channel = feed_channel

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
        await channel.send(
            f"""Welcome {member.mention}!
To gain access, you must use `/join` with the password for your group.

*Don't have the password? it should have been sent with this join link to your team leader*""",
        )
        self.logger.info(f"Created welcome channel for '{name}'")

    async def on_member_remove(self, member: discord.Member) -> None:
        name = member.display_name
        self.logger.info(f"Member '{name}' left")
        for channel in self.welcome_category.channels:
            # If the only user able to see it is the bot, then delete it.
            if channel.overwrites.keys() == {member.guild.default_role, member.guild.me}:
                await channel.delete()
                self.logger.info(f"Deleted channel '{channel.name}', because it has no users.")

    @tasks.loop(seconds=FEED_CHECK_INTERVAL)
    async def check_for_new_blog_posts(self) -> None:
        self.logger.info("Checking for new blog posts")
        await check_posts(self.feed_channel)

    @check_for_new_blog_posts.before_loop
    async def before_check_for_new_blog_posts(self) -> None:
        await self.wait_until_ready()

    def load_passwords(self) -> None:
        """
        Returns a mapping from role name to the password for that role.

        The format should be as follows:
        ```
        teamname:password
        ```
        """
        try:
            with open('passwords.json') as f:
                self.passwords = json.load(f)
        except (json.JSONDecodeError, FileNotFoundError):
            with open('passwords.json', 'w') as f:
                f.write('{}')
                self.passwords = {}

    def set_password(self, tla: str, password: str) -> None:
        self.passwords[tla.upper()] = password
        with open('passwords.json', 'w') as f:
            json.dump(self.passwords, f)

    def remove_password(self, tla: str) -> None:
        del self.passwords[tla.upper()]
        with open('passwords.json', 'w') as f:
            json.dump(self.passwords, f)
