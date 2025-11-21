import os
import json
import asyncio
import logging
from pathlib import Path
from typing import List, Literal

import yaml
import discord
import jsonschema
from discord import Guild, app_commands, CategoryChannel
from discord.ext import tasks

from sr.discord_bot.rss import check_posts
from sr.discord_bot.guild import setup_guild
from sr.discord_bot.teams import TeamsData
from sr.discord_bot.utils import find_role_by_name, find_channel_by_name
from sr.discord_bot.schema import ChannelUseCase, ChannelDefinition
from sr.discord_bot.channel import ChannelSet
from sr.discord_bot.messages import check_bot_messages
from sr.discord_bot.constants import (
    ADMIN_ROLE,
    SPECIAL_ROLE,
    VERIFIED_ROLE,
    CHANNEL_PREFIX,
    VOLUNTEER_ROLE,
    TEAM_LEADER_ROLE,
    FEED_CHECK_INTERVAL,
    WELCOME_CATEGORY_NAME,
    BLUESHIRT_ONBOARDING_CHANNEL_NAME,
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
    mode: Literal['run', 'plan', 'apply']
    guild: discord.Guild | discord.Object
    bot_messages: dict[int, list[int]] = {}
    admin_role: discord.Role
    verified_role: discord.Role
    special_role: discord.Role
    volunteer_role: discord.Role
    supervisor_role: discord.Role
    welcome_category: discord.CategoryChannel
    announce_channel: discord.TextChannel
    blueshirt_onboarding_channel: discord.TextChannel
    passwords: dict[str, str]
    feed_channel: discord.TextChannel
    teams_data: TeamsData = TeamsData([])
    subscribed_messages: List[SubscribedMessage]
    channel_defs: List[ChannelDefinition]

    rules_channel_name: str
    announce_channel_name: str
    feed_channel_name: str
    discord_announcements_channel_name: str
    stats_channel_name: str

    def __init__(
        self,
        logger: logging.Logger,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        intents: discord.Intents = discord.Intents.none(),
    ):
        super().__init__(loop=loop, intents=intents)
        self._load_channel_config()
        self.logger = logger
        self.tree = app_commands.CommandTree(self)
        self._init_commands()
        self._load_passwords()
        load_subscribed_messages(self)

    def _init_commands(self) -> None:
        team = Team()
        team.add_command(new_team)
        team.add_command(delete_team)
        team.add_command(create_voice)
        team.add_command(create_team_channel)
        team.add_command(export_team)
        team.add_command(repair_permissions)
        self.tree.add_command(team)
        stats = Stats()
        stats.add_command(post_stats)
        stats.add_command(stats_subscribe)
        self.tree.add_command(passwd)
        self.tree.add_command(stats)
        self.tree.add_command(join)
        self.tree.add_command(logs)

    async def setup_hook(self) -> None:
        if self.mode == 'run':
            await self.tree.sync()
            self.check_for_new_blog_posts.start()

    async def on_ready(self) -> None:
        self.logger.info(f"{self.user} has connected to Discord!")

        if self.mode == 'run':
            await self.setup_bot()
        if self.mode == 'plan':
            await self.list_guilds()
            await self.close()
        if self.mode == 'apply':
            await self.apply_changes()
            await self.close()

    async def set_roles_and_channels(self, guild: Guild) -> None:
        roles = await guild.fetch_roles()
        self.admin_role = find_role_by_name(roles, ADMIN_ROLE)
        self.verified_role = find_role_by_name(roles, VERIFIED_ROLE)
        self.special_role = find_role_by_name(roles, SPECIAL_ROLE)
        self.volunteer_role = find_role_by_name(roles, VOLUNTEER_ROLE)
        self.supervisor_role = find_role_by_name(roles, TEAM_LEADER_ROLE)
        self.welcome_category = find_channel_by_name(guild.categories, WELCOME_CATEGORY_NAME)
        self.announce_channel = find_channel_by_name(guild.text_channels, self.announce_channel_name)
        self.feed_channel = find_channel_by_name(guild.text_channels, self.feed_channel_name)
        self.blueshirt_onboarding_channel = find_channel_by_name(guild.text_channels,
                                                                 BLUESHIRT_ONBOARDING_CHANNEL_NAME)

    async def setup_bot(self) -> None:
        guild_id = os.getenv('DISCORD_GUILD_ID')
        if guild_id and guild_id.isnumeric() and (guild := self.get_guild(int(guild_id))):
            self.guild = guild
        else:
            self.logger.error("Please create a guild, and set the DISCORD_GUILD_ID environment variable to its ID.")
            if self.user is not None:
                self.logger.error("Then add the bot to the guild using the following link:")
                self.logger.error("https://discord.com/oauth2/authorize?client_id=" + str(self.user.id))
                self.logger.error("Once added, restart the bot.")
            await self.close()
            return

        try:
            await self.set_roles_and_channels(guild)
        except ValueError:
            self.logger.info("Setting up guild...")
            await setup_guild(self)
            await self.set_roles_and_channels(guild)

        await check_bot_messages(self, self.guild)
        self.teams_data.gen_team_memberships(self.guild, self.supervisor_role)
        await self.update_subscribed_messages()
        await self._create_missing_welcome_channels()

    async def on_member_join(self, member: discord.Member) -> None:
        if self.mode != 'run':
            return

        name = member.display_name
        self.logger.info(f"Member {name} ({member.id}) joined")
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

*Don't have the password? it should have been sent with this join link to your team supervisor*""",
        )
        self.logger.info(f"Created welcome channel for '{name}'")

    async def on_member_remove(self, member: discord.Member) -> None:
        if self.mode != 'run':
            return

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
        if self.mode != 'run':
            return

        if hasattr(self, 'guild') and isinstance(self.guild, Guild) and hasattr(self, 'supervisor_role'):
            self.teams_data.gen_team_memberships(self.guild, self.supervisor_role)

            await self.update_subscribed_messages()
        else:
            self.logger.debug('Not initialized yet, ignoring on_member_update...')

    async def on_raw_reaction_add(self, event: discord.RawReactionActionEvent) -> None:
        """Handle message reactions."""
        if event.member is None or self.user is not None and event.member.id == self.user.id:
            # Ignore reactions from the bot itself and users not in the server
            return

        # Remove subscribed messages by reacting with a cross mark.
        if event.emoji.name == '\N{CROSS MARK}':
            if SubscribedMessage(event.channel_id, event.message_id) not in self.subscribed_messages:
                # Ignore for messages not in the subscribed list
                return
            if self.volunteer_role not in event.member.roles:
                # Ignore for users without admin privileges
                return

            await self.remove_subscribed_message(
                SubscribedMessage(event.channel_id, event.message_id),
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
        if not hasattr(self, 'feed_channel'):
            return

        self.logger.info("Checking for new blog posts")
        await check_posts(self.feed_channel)

    @check_for_new_blog_posts.before_loop
    async def before_check_for_new_blog_posts(self) -> None:
        await self.wait_until_ready()

    def _load_channel_config(self) -> None:
        with open('channels.yml', 'r+') as f:
            contents = yaml.load(f, Loader=yaml.Loader)
        with open('channels.schema.yml', 'r+') as f:
            schema = yaml.load(f, Loader=yaml.Loader)
        jsonschema.validate(contents, schema)
        self.channel_defs = [ChannelDefinition.load(ch) for ch in contents]
        for top_level in self.channel_defs:
            if top_level.channel_type == discord.ChannelType.category:
                for channel in top_level.channels:
                    if channel.use_case == ChannelUseCase.RULES:
                        self.rules_channel_name = channel.name
                    if channel.use_case == ChannelUseCase.ANNOUNCE:
                        self.announce_channel_name = channel.name
                    if channel.use_case == ChannelUseCase.FEED:
                        self.feed_channel_name = channel.name
                    if channel.use_case == ChannelUseCase.DISCORD:
                        self.discord_announcements_channel_name = channel.name
                    if channel.use_case == ChannelUseCase.STATS:
                        self.stats_channel_name = channel.name

    def _load_passwords(self) -> None:
        """
        Returns a mapping from role name to the password for that role.

        The format should be as follows:
        ```
        teamname:password
        ```
        """
        path = Path('passwords.json')
        try:
            self.passwords = json.loads(path.read_text())
        except (json.JSONDecodeError, FileNotFoundError):
            path.write_text('{}')
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
        if self.mode != 'run' or not self.is_ready():
            return

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

    async def list_guilds(self) -> None:
        self.logger.info("This bot is currently part of the following guilds:")
        for guild in self.guilds:
            self.logger.info(f"- {guild.name} (ID: {guild.id})")
            if os.getenv('DISCORD_GUILD_ID') and str(guild.id) == os.getenv('DISCORD_GUILD_ID'):
                self.logger.info("  This is the configured guild.")
                # Output diff
                stored_set = ChannelSet.from_definitions(self.channel_defs)
                current_set = ChannelSet.from_guild(guild)
                diff = ChannelSet.diff(current_set, stored_set)
                if len(diff) > 0:
                    self.logger.warning(f"  It has {len(diff)} changes pending:")
                    for change in diff:
                        self.logger.warning(f"    {change}")
                else:
                    self.logger.info("  No pending channel changes.")
            self.logger.info(f"  Owner: {guild.owner} (ID: {guild.owner_id})")
            self.logger.info(f"  {guild.member_count} members")

    async def apply_changes(self) -> None:
        if (guild_id := os.getenv('DISCORD_GUILD_ID')) is None:
            self.logger.error("No DISCORD_GUILD_ID environment variable set.")
            return
        guild = discord.utils.get(self.guilds, id=int(guild_id))
        if guild is None:
            self.logger.error("No guild found with the configured DISCORD_GUILD_ID.")
            return
        stored_set = ChannelSet.from_definitions(self.channel_defs)
        current_set = ChannelSet.from_guild(guild)
        diff = ChannelSet.diff(current_set, stored_set)
        for change in diff:
            if change.requires_community and "COMMUNITY" not in guild.features:
                self.logger.info("Enabling community features...")
                await guild.edit(community=True)
            self.logger.info(f"Applying change: {change}")
            await change.apply(guild)
            await asyncio.sleep(.5)  # avoid hitting rate limits
        self.logger.info("Ensuring channels are in order... (This might take a minute)")
        await stored_set.sort_channels(guild)
        self.logger.info("Done!")

    async def _create_missing_welcome_channels(self) -> None:
        if not isinstance(self.guild, Guild):
            return

        async for guild_member in self.guild.fetch_members():
            if len(guild_member.roles) == 0:
                welcome_channel_found = False

                for welcome_channel in self.welcome_category.channels:
                    if isinstance(welcome_channel, CategoryChannel):
                        # Categories can't contain categories so this shouldn't happen
                        # However channels is a list of GuildChannel so we need to handle it
                        continue

                    if guild_member in welcome_channel.members:
                        welcome_channel_found = True

                if not welcome_channel_found:
                    await self.on_member_join(guild_member)
