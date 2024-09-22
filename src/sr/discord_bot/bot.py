import os
import json
import asyncio
import logging
from typing import List

import discord
from discord import app_commands
from discord.ext import tasks

from sr.discord_bot.rss import check_posts
from sr.discord_bot.teams import TeamsData
from sr.discord_bot.constants import (
    SPECIAL_ROLE,
    VERIFIED_ROLE,
    CHANNEL_PREFIX,
    VOLUNTEER_ROLE,
    TEAM_LEADER_ROLE,
    FEED_CHANNEL_NAME,
    FEED_CHECK_INTERVAL,
    ANNOUNCE_CHANNEL_NAME,
    WELCOME_CATEGORY_NAME,
)
from sr.discord_bot.commands.join import join
from sr.discord_bot.commands.logs import logs
from sr.discord_bot.commands.team import (
    Team,
    new_team,
    delete_team,
    export_team,
    create_voice,
    repair_permissions,
    create_team_channel,
)
from sr.discord_bot.commands.stats import (
    Stats,
    post_stats,
    stats_subscribe,
    SubscribedMessage,
    SUBSCRIBE_MSG_FILE,
    load_subscribed_messages,
)
from sr.discord_bot.commands.passwd import passwd


class BotClient(discord.Client):
    logger: logging.Logger
    guild: discord.Guild | discord.Object
    verified_role: discord.Role
    special_role: discord.Role
    volunteer_role: discord.Role
    supervisor_role: discord.Role
    welcome_category: discord.CategoryChannel
    announce_channel: discord.TextChannel
    passwords: dict[str, str]
    feed_channel: discord.TextChannel
    teams_data: TeamsData = TeamsData([])
    subscribed_messages: List[SubscribedMessage]

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
        team.add_command(repair_permissions)
        self.tree.add_command(team, guild=self.guild)
        stats = Stats()
        stats.add_command(post_stats)
        stats.add_command(stats_subscribe)
        self.tree.add_command(passwd, guild=self.guild)
        self.tree.add_command(stats, guild=self.guild)
        self.tree.add_command(join, guild=self.guild)
        self.tree.add_command(logs, guild=self.guild)
        self.load_passwords()
        load_subscribed_messages(self)

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
        supervisor_role = discord.utils.get(guild.roles, name=TEAM_LEADER_ROLE)
        welcome_category = discord.utils.get(guild.categories, name=WELCOME_CATEGORY_NAME)
        announce_channel = discord.utils.get(guild.text_channels, name=ANNOUNCE_CHANNEL_NAME)
        feed_channel = discord.utils.get(guild.text_channels, name=FEED_CHANNEL_NAME)

        if (
            verified_role is None
            or special_role is None
            or volunteer_role is None
            or supervisor_role is None
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
            self.supervisor_role = supervisor_role
            self.welcome_category = welcome_category
            self.announce_channel = announce_channel
            self.feed_channel = feed_channel

        self.teams_data.gen_team_memberships(self.guild, self.supervisor_role)
        await self.update_subscribed_messages()

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

        if self.verified_role in member.roles:
            return

        for channel in self.welcome_category.channels:
            # If the only user able to see it is the bot, then delete it.
            if channel.overwrites.keys() == {member.guild.default_role, member.guild.me}:
                await channel.delete()
                self.logger.info(f"Deleted channel '{channel.name}', because it has no users.")

    async def on_member_update(self, before: discord.Member, after: discord.Member) -> None:
        """Update subscribed messages when a member's roles change."""
        if isinstance(self.guild, discord.Guild):
            self.teams_data.gen_team_memberships(self.guild, self.supervisor_role)

            await self.update_subscribed_messages()

    async def on_raw_reaction_add(self, payload: discord.RawReactionActionEvent) -> None:
        """Remove subscribed messages by reacting with a cross mark."""
        if payload.emoji.name != '\N{CROSS MARK}':
            return
        if SubscribedMessage(payload.channel_id, payload.message_id) not in self.subscribed_messages:
            # Ignore for messages not in the subscribed list
            return
        if payload.member is None:
            # Ignore for users not in the server
            return
        if self.volunteer_role not in payload.member.roles:
            # Ignore for users without admin privileges
            return

        await self.remove_subscribed_message(
            SubscribedMessage(payload.channel_id, payload.message_id),
        )

    def _save_subscribed_messages(self) -> None:
        """Save subscribed messages to file."""
        with open(SUBSCRIBE_MSG_FILE, 'w') as f:
            json.dump(
                [x._asdict() for x in self.subscribed_messages],
                f,
            )

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

    def stats_message(self, members: bool = True, warnings: bool = True, statistics: bool = False) -> str:
        """Generate a message string for the given options."""
        return '\n\n'.join([
            *([self.teams_data.team_summary()] if members else []),
            *([self.teams_data.warnings()] if warnings else []),
            *([self.teams_data.statistics()] if statistics else []),
        ])

    def add_subscribed_message(self, msg: SubscribedMessage) -> None:
        """Add a subscribed message to the subscribed list."""
        self.subscribed_messages.append(msg)
        self._save_subscribed_messages()

    async def remove_subscribed_message(self, msg: SubscribedMessage) -> None:
        """Remove a subscribed message from the channel and subscribed list."""
        msg_channel = await self.fetch_channel(msg.channel_id)
        if not hasattr(msg_channel, 'fetch_message'):
            # ignore for channels that don't support message editing
            return

        try:
            message = await msg_channel.fetch_message(msg.message_id)
            chan_name = message.channel.name if hasattr(message.channel, 'name') else 'unknown channel'
            self.logger.info(f'Removing message in {chan_name} from {message.author.name}')
            await message.delete()  # remove message from discord
        except discord.errors.NotFound:
            self.logger.info(f"Message #{msg.message_id} doesn't exist, removing from subscribed messages")

        # remove message from subscription list and save to file
        self.subscribed_messages.remove(msg)
        self._save_subscribed_messages()

    async def update_subscribed_messages(self) -> None:
        """Update all subscribed messages."""
        self.logger.info('Updating subscribed messages')
        for sub_msg in self.subscribed_messages:  # edit all subscribed messages
            message = self.stats_message(
                sub_msg.members,
                sub_msg.warnings,
                sub_msg.stats,
            )
            message = f"```\n{message}\n```"

            try:
                msg_channel = await self.fetch_channel(sub_msg.channel_id)
                if not hasattr(msg_channel, 'fetch_message'):
                    # ignore for channels that don't support message editing
                    continue
                msg = await msg_channel.fetch_message(sub_msg.message_id)
                await msg.edit(content=message)
            except discord.errors.NotFound:  # message is no longer available
                await self.remove_subscribed_message(sub_msg)
