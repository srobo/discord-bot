from __future__ import annotations

import abc
import dataclasses
from typing import Mapping, Any, TYPE_CHECKING

import discord
from discord import ChannelType, PermissionOverwrite, Role, Guild, PartialEmoji
from discord.abc import GuildChannel
if TYPE_CHECKING:
    from discord.types.guild import ChannelPositionUpdate

from sr.discord_bot.constants import TEAM_CATEGORY_NAME, TEAM_VOICE_CATEGORY_NAME, WELCOME_CATEGORY_NAME, VERIFIED_ROLE, \
    VOLUNTEER_ROLE, TEAM_LEADER_ROLE, SPECIAL_ROLE
from sr.discord_bot.schema import ChannelDefinition, Overwrites, RoleType, ChannelUseCase

RoleOverwrites = dict[Role, PermissionOverwrite]

IGNORED_CATEGORIES = [
    TEAM_CATEGORY_NAME,
    TEAM_VOICE_CATEGORY_NAME,
    WELCOME_CATEGORY_NAME,
]

class ChannelSet:
    def __init__(self):
        self._channels: list[Channel] = []
        self._role_map: Mapping[Role, RoleType] | None = None

    def _get_role_type(self, role: Role, guild: Guild) -> RoleType:
        if self._role_map is None:
            self._role_map = {
                guild.default_role: RoleType.EVERYONE,
                discord.utils.get(guild.roles, name=VERIFIED_ROLE): RoleType.VERIFIED,
                discord.utils.get(guild.roles, name=VOLUNTEER_ROLE): RoleType.BLUESHIRT,
                discord.utils.get(guild.roles, name=TEAM_LEADER_ROLE): RoleType.SUPERVISOR,
                discord.utils.get(guild.roles, name=SPECIAL_ROLE): RoleType.UNVERIFIED_BLUESHIRT,
            }

        if role not in self._role_map:
            raise ValueError(f"Role type for '{role.name}' not found")

        return self._role_map[role]

    def _get_overwrites(self, channel: GuildChannel) -> Overwrites:
        overwrites = {}
        for subject, permissions in channel.overwrites.items():
            if isinstance(subject, Role):
                overwrites[self._get_role_type(subject, channel.guild).value] = {}
                for permission, value in permissions:
                    if value is not None:
                        overwrites[self._get_role_type(subject, channel.guild).value][permission] = value
        return overwrites

    def count(self, category: Channel|None) -> int:
        """Count the number of channels in a category, or top-level channels if category is None."""
        if category is None:
            return len([c for c in self._channels if c.category is None])
        return len([c for c in self._channels if c.category == category])

    def create_category(
        self,
        name: str,
        *,
        overwrites: Overwrites | None = None,
        old_names: list[str] | None = None,
    ) -> Channel:
        category = Channel(
            name=name,
            position=self.count(None),
            overwrites=overwrites,
            topic="",
            category=None,
            type=ChannelType.category,
            old_names=old_names or [],
        )
        self._channels.append(category)
        return category

    def create_text_channel(
        self,
        name: str,
        *,
        category: Channel | None = None,
        overwrites: Overwrites | None = None,
        topic: str = "",
        old_names: list[str] | None = None,
        position: int | None = None,
        type: int = ChannelType.text,
        use_case: ChannelUseCase | None = None,
    ) -> None:
        if category and category.type != ChannelType.category:
            raise ValueError("The category must be a channel of type 'category'.")
        text_channel = Channel(
            name=name,
            position=position if position is not None else self.count(category),
            overwrites=overwrites,
            topic=topic,
            category=category,
            type=type,
            old_names=old_names or [],
        )

        self._channels.append(text_channel)

    def create_voice_channel(
        self,
        name: str,
        *,
        category: Channel | None = None,
        overwrites: Overwrites | None = None,
        old_names: list[str] | None = None,
        position: int | None = None,
    ) -> None:
        if category.type != ChannelType.category:
            raise ValueError("The category must be of type 'category'.")
        voice_channel = Channel(
            name=name,
            position=position if position is not None else self.count(category),
            overwrites=overwrites,
            topic="",
            category=category,
            type=ChannelType.voice,
            old_names=old_names or [],
        )
        self._channels.append(voice_channel)

    def create_forum_channel(
        self,
        name: str,
        *,
        category: Channel | None = None,
        overwrites: Overwrites | None = None,
        old_names: list[str] | None = None,
        position: int | None = None,
        default_reaction_emoji: str | None = None,
        available_tags: list[str] | None = None,
    ) -> None:
        if category and category.type != ChannelType.forum:
            raise ValueError("The category must be a channel of type 'forum'.")
        forum_channel = Channel(
            name=name,
            position=position if position is not None else self.count(category),
            overwrites=overwrites,
            topic="",
            category=category,
            type=ChannelType.forum,
            old_names=old_names or [],
            default_reaction_emoji=default_reaction_emoji,
            available_tags=available_tags or [],
        )
        self._channels.append(forum_channel)

    @classmethod
    def diff(cls, old: ChannelSet, new: ChannelSet) -> list[ChannelCommand]:
        """Calculate the difference between two ChannelSets."""
        commands = []
        # TODO: Diff categories first (in case one gets renamed)
        cls._diff_channels(old._channels, new._channels, commands)
        return commands

    async def sort_channels(self, guild: Guild) -> None:
        for category in [c for c in self._channels if c.is_category]:
            channels = [c for c in self._channels if c.category == category]
            await self.sort_category(channels, guild)
        channels = [c for c in self._channels if c.category is None]
        await self.sort_category(channels, guild)

    async def sort_category(self, channels: list[Channel], guild: Guild) -> None:
        payload: list[ChannelPositionUpdate] = [{'id': await ChannelSet.get_channel_id(c, guild), 'position': c.position } for c in channels]
        await guild._state.http.bulk_channel_update(guild.id, payload)

    @classmethod
    def _diff_channels(cls, old: list[Channel], new: list[Channel], commands: list[ChannelCommand]) -> None:
        """Calculate the difference in channels between two ChannelSets."""

        seen_old_channel_names = set()

        for new_index, new_channel in enumerate(new):
            old_channel = next((x for x in old if x.name == new_channel.name or x.name in new_channel.old_names), None)
            if old_channel is None:
                if new_channel.is_category:
                    commands.append(CreateCategoryCommand(name=new_channel.name, overwrites=new_channel.overwrites))
                elif new_channel.type == ChannelType.forum:
                    commands.append(CreateForumCommand(
                        name=new_channel.name,
                        category=new_channel.category,
                        overwrites=new_channel.overwrites,
                        topic=new_channel.topic,
                        default_reaction_emoji=PartialEmoji(name=new_channel.default_reaction_emoji) if new_channel.default_reaction_emoji else None,
                        available_tags=[{"name": tag_name} for tag_name in new_channel.available_tags],
                    ))
                else:
                    commands.append(CreateChannelCommand(
                        name=new_channel.name,
                        type=new_channel.type,
                        category=new_channel.category,
                        overwrites=new_channel.overwrites,
                        topic=new_channel.topic,
                    ))

                    # figure out when we have the bare minimum based on use_case ;-;
            else:
                seen_old_channel_names.add(old_channel.name)
                command = AlterChannelCommand.diff(old_channel, new_channel, new_index, old_channel.type)
                if command.has_changes():
                    commands.append(command)

        for old_channel in old:
            if old_channel.name not in seen_old_channel_names:
                commands.insert(0, DeleteChannelCommand(name=old_channel.name, is_category=old_channel.is_category))

    @classmethod
    def from_guild(cls, guild: Guild) -> ChannelSet:
        """Create a ChannelSet from a Discord Guild."""
        channel_set = cls()

        categories: dict[int, Channel] = {}
        for category in guild.categories:
            categories[category.id] = channel_set.create_category(
                name=category.name,
                overwrites=channel_set._get_overwrites(category),
                old_names=[category.name],
            )
        for channel in guild.channels:
            if channel.type == ChannelType.category or channel.category.name in IGNORED_CATEGORIES:
                continue
            if channel.type == ChannelType.voice:
                channel_set.create_voice_channel(
                    name=channel.name,
                    category=categories[channel.category.id],
                    overwrites=channel_set._get_overwrites(channel),
                    old_names=[channel.name],
                    position=channel.position,
                )
            elif channel.type == ChannelType.forum:
                forum_channel = channel  # type: discord.ForumChannel
                channel_set.create_forum_channel(
                    name=forum_channel.name,
                    category=categories[forum_channel.category.id] if forum_channel.category else None,
                    overwrites=channel_set._get_overwrites(forum_channel),
                    old_names=[forum_channel.name],
                    position=forum_channel.position,
                    default_reaction_emoji=forum_channel.default_reaction_emoji.name if forum_channel.default_reaction_emoji else None,
                    available_tags=[tag.name for tag in forum_channel.available_tags],
                )
            else:
                channel_set.create_text_channel(
                    name=channel.name,
                    category=categories[channel.category.id],
                    overwrites=channel_set._get_overwrites(channel),
                    topic=channel.topic or "",
                    old_names=[channel.name],
                    position=channel.position,
                    type=channel.type,
                )
        return channel_set

    @classmethod
    def from_definitions(cls, cat_definitions: list[ChannelDefinition]) -> ChannelSet:
        """Create a ChannelSet from a parsed YAML file."""
        channel_set = cls()
        categories: dict[str, Channel] = {}
        for cat_definition in cat_definitions:
            category = channel_set.create_category(
                name=cat_definition.name,
                overwrites=cat_definition.overwrites,
                old_names=cat_definition.old_names,
            )
            categories[cat_definition.name] = category

        for cat_definition in cat_definitions:
            category = categories[cat_definition.name]
            for channel_definition in cat_definition.channels:
                if channel_definition.channel_type == ChannelType.voice:
                    channel_set.create_voice_channel(
                        name=channel_definition.name,
                        category=category,
                        overwrites=channel_definition.overwrites,
                        old_names=channel_definition.old_names,
                    )
                else:
                    channel_set.create_text_channel(
                        name=channel_definition.name,
                        category=category,
                        overwrites=channel_definition.overwrites,
                        topic=channel_definition.topic,
                        old_names=channel_definition.old_names,
                        type=channel_definition.channel_type,
                    )
        return channel_set

    @staticmethod
    async def get_channel_id(ch: Channel, guild: Guild) -> int:
        await guild.fetch_channels()
        if ch.type == ChannelType.category:
            channel = discord.utils.get(guild.categories, name=ch.name)
        elif ch.type == ChannelType.text:
            channel = discord.utils.get(guild.text_channels, name=ch.name)
        elif ch.type == ChannelType.voice:
            channel = discord.utils.get(guild.voice_channels, name=ch.name)
        elif ch.type == ChannelType.forum:
            channel = discord.utils.get(guild.forums, name=ch.name)
        else:
            channel = discord.utils.get(guild.channels, name=ch.name)
        if channel is None:
            raise ValueError("Failed to find channel")
        return channel.id

@dataclasses.dataclass(frozen=True)
class Channel:
    name: str
    position: int
    overwrites: RoleOverwrites
    topic: str
    category: Channel | None
    type: ChannelType
    old_names: list[str] = dataclasses.field(default_factory=list)
    # Forum-specific:
    default_reaction_emoji: str | None = None  # Name of the emoji
    available_tags: list[str] = dataclasses.field(default_factory=list)
    # Bot use only:
    use_case: ChannelUseCase | None = None

    @property
    def is_category(self) -> bool:
        return self.type == ChannelType.category

class Command(abc.ABC):
    @abc.abstractmethod
    async def apply(self, guild: Guild) -> None:
        ...

@dataclasses.dataclass
class AlterChannelCommand(Command):
    old_name: str
    new_name: str
    overwrites: RoleOverwrites | None = None
    topic: str | None = None
    category: Channel | None = None
    position: int | None = None
    is_category: bool = False  # Whether this command is for a category, only for display purposes
    channel_type: ChannelType = ChannelType.text  # Used for sorting
    # Forum-specific:
    default_reaction_emoji: str | None = None  # Name of the emoji
    available_tags: list[str] = dataclasses.field(default_factory=list)

    @classmethod
    def diff(cls, old_channel: Channel, new_channel: Channel, new_position: int, channel_type: ChannelType) -> AlterChannelCommand:
        command = cls(old_name=old_channel.name, new_name=new_channel.name,
                      is_category=new_channel.is_category, channel_type=channel_type)
        if old_channel.overwrites != new_channel.overwrites:
            command.overwrites = new_channel.overwrites
        if old_channel.topic != new_channel.topic:
            command.topic = new_channel.topic
        if not old_channel.category or (old_channel.category.name != new_channel.category.name):
            command.category = new_channel.category
        command.position = new_position
        return command

    def is_rename(self) -> bool:
        """Check if the command is a rename."""
        return self.old_name != self.new_name

    def has_attribute_changes(self) -> bool:
        """Check if the command has any changes."""
        return (self.overwrites is not None or
                self.topic is not None or
                self.category is not None)

    def has_changes(self) -> bool:
        """Check if the command has any changes."""
        return self.is_rename() or self.has_attribute_changes()

    def __str__(self) -> str:
        if self.is_rename() and not self.has_attribute_changes():
            if self.is_category:
                return f"RENAME Category \"{self.old_name}\" to \"{self.new_name}\""
            return f"RENAME Channel #{self.old_name} to #{self.new_name}"
        changes = []
        if self.old_name != self.new_name:
            if self.is_category:
                changes.append(f"name: {self.old_name} -> {self.new_name}")
            changes.append(f"name: #{self.old_name} -> #{self.new_name}")
        if self.overwrites is not None:
            changes.append("permissions changed")
        if self.topic is not None:
            changes.append(f"topic: {self.topic}")
        if self.category is not None:
            changes.append(f"category: \"{self.category.name}\"")

        if self.is_category:
            return f"ALTER  Category \"{self.old_name}\" ({', '.join(changes)})"
        return f"ALTER  Channel #{self.old_name} ({', '.join(changes)})"

    async def get_channel(self, guild: Guild) -> GuildChannel:
        await guild.fetch_channels()
        if self.channel_type == ChannelType.category:
            channel = discord.utils.get(guild.categories, name=self.old_name)
        elif self.channel_type == ChannelType.text:
            channel = discord.utils.get(guild.text_channels, name=self.old_name)
        elif self.channel_type == ChannelType.voice:
            channel = discord.utils.get(guild.voice_channels, name=self.old_name)
        elif self.channel_type == ChannelType.forum:
            channel = discord.utils.get(guild.forums, name=self.old_name)
        else:
            channel = discord.utils.get(guild.channels, name=self.old_name)
        if channel is None:
            raise ValueError("Failed to find channel")
        return channel

    async def apply(self, guild: Guild) -> None:
        channel = discord.utils.get(guild.channels, name=self.old_name)
        if channel is None:
            raise "Failed to find channel"

        kwargs = {}
        if self.is_rename():
            kwargs["name"] = self.new_name

        if self.topic is not None:
            kwargs["topic"] = self.topic

        if self.category is not None:
            kwargs["category"] = discord.utils.get(guild.channels, name=self.category.name)

        if self.overwrites is not None:
            kwargs["overwrites"] = self.overwrites

        if channel.type == ChannelType.forum:
            await guild.fetch_emojis()
            channel.default_reaction_emoji = discord.utils.get(guild.emojis, name=self.default_reaction_emoji)
            # Sync tags
            if self.available_tags and channel is discord.ForumChannel:
                existing_tags = {tag.name: tag for tag in channel.available_tags}
                new_tags = []
                for tag_name in self.available_tags:
                    if tag_name in existing_tags:
                        new_tags.append(existing_tags[tag_name])
                    else:
                        new_tags.append(await channel.create_tag(name=tag_name))
                kwargs["available_tags"] = new_tags


        if kwargs:
            await channel.edit(**kwargs)

@dataclasses.dataclass(frozen=True)
class DeleteChannelCommand(Command):
    name: str
    is_category: bool = False  # Whether this command is for a category, only for display purposes

    def __str__(self) -> str:
        type_str = "Category" if self.is_category else "Channel"
        return f'DELETE #{type_str} "#{self.name}"'

    async def apply(self, guild: Guild) -> None:
        await discord.utils.get(guild.channels, name=self.name).delete()

@dataclasses.dataclass(frozen=True)
class CreateCategoryCommand(Command):
    name: str
    overwrites: RoleOverwrites | None = None

    def __str__(self) -> str:
        return f'CREATE Category "{self.name}"'

    async def apply(self, guild: Guild) -> None:
        await guild.create_category(self.name, overwrites=self.overwrites)

@dataclasses.dataclass(frozen=True)
class CreateChannelCommand(Command):
    name: str
    type: ChannelType
    category: Channel | None = None
    overwrites: RoleOverwrites | None = None
    topic: str = ""

    def __str__(self) -> str:
        s =  f'CREATE Channel #{self.name}'

        if self.category is not None:
            s += f' in Category "{self.category.name}"'

        return s

    async def apply(self, guild: Guild) -> None:
        if self.type == ChannelType.text:
            await guild.create_text_channel(self.name, category=discord.utils.get(guild.categories, name=self.category.name), overwrites=self.overwrites, topic=self.topic)
        elif self.type == ChannelType.voice:
            await guild.create_voice_channel(self.name, category=discord.utils.get(guild.categories, name=self.category.name), overwrites=self.overwrites)
        else:
            raise ValueError(f"Unsupported channel type: {self.type}")

@dataclasses.dataclass(frozen=True)
class CreateForumCommand(Command):
    name: str
    category: Channel | None = None
    overwrites: RoleOverwrites | None = None
    topic: str = ""
    default_reaction_emoji: PartialEmoji | None = None
    available_tags: list[dict[str, Any]] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        s =  f'CREATE Forum #{self.name}'

        if self.category is not None:
            s += f' in Category "{self.category.name}"'

        return s

    async def apply(self, guild: Guild) -> None:
        await guild.create_forum(
            name=self.name,
            category=discord.utils.get(guild.categories, name=self.category.name) if self.category else None,
            overwrites=self.overwrites,
            topic=self.topic,
            default_reaction_emoji=self.default_reaction_emoji,
            available_tags=[discord.ForumTag(**tag) for tag in self.available_tags],
        )

ChannelCommand = AlterChannelCommand | DeleteChannelCommand | CreateCategoryCommand | CreateChannelCommand | CreateForumCommand
