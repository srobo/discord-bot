from __future__ import annotations

import abc
import dataclasses
from typing import Mapping

import discord
from discord import ChannelType, PermissionOverwrite, Role, Guild
from discord.abc import GuildChannel

from sr.discord_bot.constants import TEAM_CATEGORY_NAME, TEAM_VOICE_CATEGORY_NAME, WELCOME_CATEGORY_NAME, VERIFIED_ROLE, \
    VOLUNTEER_ROLE, TEAM_LEADER_ROLE, SPECIAL_ROLE
from sr.discord_bot.schema import CategoryChannelDefinition, Overwrites, RoleType

RoleOverwrites = dict[Role, PermissionOverwrite]

IGNORED_CATEGORIES = [
    TEAM_CATEGORY_NAME,
    TEAM_VOICE_CATEGORY_NAME,
    WELCOME_CATEGORY_NAME,
]

class ChannelSet:
    def __init__(self):
        self._channels: list[Channel] = []
        self._role_map: Mapping[RoleType, Role] | None = None

    def get_role(self, role_type: RoleType, guild: Guild) -> Role:
        if self._role_map is None:
            self._role_map = {
                RoleType.EVERYONE: guild.default_role,
                RoleType.VERIFIED: discord.utils.get(guild.roles, name=VERIFIED_ROLE),
                RoleType.BLUESHIRT: discord.utils.get(guild.roles, name=VOLUNTEER_ROLE),
                RoleType.SUPERVISOR: discord.utils.get(guild.roles, name=TEAM_LEADER_ROLE),
                RoleType.UNVERIFIED_BLUESHIRT: discord.utils.get(guild.roles, name=SPECIAL_ROLE),
            }

        if role_type not in self._role_map:
            raise ValueError(f"Role for '{role_type}' not found in guild '{guild.name}'")

        return self._role_map[role_type]

    def convert_overwrites(self, overwrites: Overwrites, guild: Guild) -> RoleOverwrites:
        return { self.get_role(role_type, guild): PermissionOverwrite(**perms) for role_type, perms in overwrites.items() }

    def create_category(
        self,
        name: str,
        *,
        overwrites: RoleOverwrites | None = None,
        old_names: list[str] | None = None,
    ) -> Channel:
        category = Channel(
            name=name,
            position=self.count(None) + 1,
            overwrites=overwrites or {},
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
        category: Channel,
        overwrites: RoleOverwrites | None = None,
        topic: str = "",
        old_names: list[str] | None = None,
    ) -> None:
        if category.type != ChannelType.category:
            raise ValueError("The category must be a channel of type 'category'.")
        text_channel = Channel(
            name=name,
            position=self.count(category) + 1,
            overwrites=overwrites or {},
            topic=topic,
            category=category,
            type=ChannelType.text,
            old_names=old_names or [],
        )
        self._channels.append(text_channel)

    def create_voice_channel(
        self,
        name: str,
        *,
        category: Channel,
        overwrites: RoleOverwrites | None = None,
        old_names: list[str] | None = None,
    ) -> None:
        if category.type != ChannelType.category:
            raise ValueError("The category must be of type 'category'.")
        voice_channel = Channel(
            name=name,
            position=self.count(category) + 1,
            overwrites=overwrites or {},
            topic="",
            category=category,
            type=ChannelType.voice,
            old_names=old_names or [],
        )
        self._channels.append(voice_channel)

    @classmethod
    def diff(cls, old: ChannelSet, new: ChannelSet) -> list[ChannelCommand]:
        """Calculate the difference between two ChannelSets."""
        commands = []
        cls._diff_categories(
            [x for x in old._channels if x.type == ChannelType.category],
            [x for x in new._channels if x.type == ChannelType.category],
            commands,
        )
        cls._diff_channels(
            [x for x in old._channels if x.type != ChannelType.category],
            [x for x in new._channels if x.type != ChannelType.category],
            commands,
        )
        return commands

    @classmethod
    def _diff_categories(cls, old: list[Channel], new: list[Channel], commands: list[ChannelCommand]) -> None:
        """Calculate the difference in categories between two ChannelSets."""
        seen_old_cat_names = set()

        for new_index, new_cat in enumerate(new):
            old_cat = next((x for x in old if x.name == new_cat.name or x.name in new_cat.old_names), None)
            if old_cat is None:
                commands.append(CreateCategoryCommand(name=new_cat.name, overwrites=new_cat.overwrites))
            else:
                old_index = old.index(old_cat)
                seen_old_cat_names.add(old_cat.name)
                command = AlterChannelCommand(old_name=old_cat.name, new_name=new_cat.name, is_category=True)
                if old_cat.overwrites != new_cat.overwrites:
                    command.overwrites = new_cat.overwrites
                if old_cat.topic != new_cat.topic:
                    command.topic = new_cat.topic
                if old_cat.category != new_cat.category:
                    command.category = new_cat.category
                if old_index != new_index:
                    command.position = new_index
                if command.has_changes():
                    commands.append(command)


        for old_cat in old:
            if old_cat.name not in seen_old_cat_names and old_cat.name not in IGNORED_CATEGORIES:
                commands.insert(0, DeleteChannelCommand(name=old_cat.name, is_category=True))

    @classmethod
    def _diff_channels(cls, old: list[Channel], new: list[Channel], commands: list[ChannelCommand]) -> None:
        """Calculate the difference in channels between two ChannelSets."""

        seen_old_channel_names = set()

        for new_index, new_channel in enumerate(new):
            old_channel = next((x for x in old if x.name == new_channel.name or x.name in new_channel.old_names), None)
            if old_channel is None:
                commands.append(CreateChannelCommand(
                    name=new_channel.name,
                    type=new_channel.type,
                    category=new_channel.category,
                    overwrites=new_channel.overwrites,
                    topic=new_channel.topic,
                ))
            else:
                old_index = old.index(old_channel)
                seen_old_channel_names.add(old_channel.name)
                command = AlterChannelCommand(old_name=old_channel.name, new_name=new_channel.name)
                if old_channel.overwrites != new_channel.overwrites:
                    command.overwrites = new_channel.overwrites
                if old_channel.topic != new_channel.topic:
                    command.topic = new_channel.topic
                if old_channel.category != new_channel.category:
                    command.category = new_channel.category
                if old_index != new_index:
                    command.position = new_index
                if command.has_changes():
                    commands.append(command)

        for old_channel in old:
            if old_channel.name not in seen_old_channel_names:
                commands.insert(0, DeleteChannelCommand(name=old_channel.name))

    @classmethod
    def from_guild(cls, guild: Guild):
        """Create a ChannelSet from a Discord Guild."""
        channel_set = cls()

        def get_overwrites(c: GuildChannel) -> Overwrites:
            return {role: overwrite for role, overwrite in c.overwrites.items() if isinstance(role, Role)}

        categories: dict[int, Channel] = {}
        for category in guild.categories:
            categories[category.id] = channel_set.create_category(
                name=category.name,
                overwrites=get_overwrites(category),
                old_names=[category.name],
            )
        for channel in guild.text_channels + guild.voice_channels:
            if channel.category is None or channel.category.name in IGNORED_CATEGORIES:
                continue
            if channel.type == ChannelType.text:
                channel_set.create_text_channel(
                    name=channel.name,
                    category=categories[channel.category.id],
                    overwrites=get_overwrites(channel),
                    topic=channel.topic or "",
                    old_names=[channel.name],
                )
            elif channel.type == ChannelType.voice:
                channel_set.create_voice_channel(
                    name=channel.name,
                    category=categories[channel.category.id],
                    overwrites=get_overwrites(channel),
                    old_names=[channel.name],
                )
        return channel_set

    @classmethod
    def from_definitions(cls, cat_definitions: list[CategoryChannelDefinition]) -> ChannelSet:
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
                if channel_definition.channel_type == ChannelType.text:
                    channel_set.create_text_channel(
                        name=channel_definition.name,
                        category=category,
                        overwrites=channel_definition.overwrites,
                        topic=channel_definition.topic,
                        old_names=channel_definition.old_names,
                    )
                elif channel_definition.channel_type == ChannelType.voice:
                    channel_set.create_voice_channel(
                        name=channel_definition.name,
                        category=category,
                        overwrites=channel_definition.overwrites,
                        old_names=channel_definition.old_names,
                    )
        return channel_set

    def count(self, category: Channel|None) -> int:
        """Count the number of channels in a category."""
        return sum(1 for c in self._channels if c.category == category)

@dataclasses.dataclass(frozen=True)
class Channel:
    name: str
    position: int
    overwrites: RoleOverwrites
    topic: str
    category: Channel | None
    type: ChannelType
    old_names: list[str] = dataclasses.field(default_factory=list)

class Command(abc.ABC):
    @abc.abstractmethod
    def apply(self, guild: Guild) -> None:
        pass

@dataclasses.dataclass
class AlterChannelCommand(Command):
    old_name: str
    new_name: str
    overwrites: RoleOverwrites | None = None
    topic: str | None = None
    category: Channel | None = None
    position: int | None = None
    is_category: bool = False  # Whether this command is for a category, only for display purposes

    def is_rename(self) -> bool:
        """Check if the command is a rename."""
        return self.old_name != self.new_name

    def has_attribute_changes(self) -> bool:
        """Check if the command has any changes."""
        return (self.overwrites is not None or
                self.topic is not None or
                self.category is not None or
                self.position is not None)

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
        if self.position is not None:
            changes.append(f"position: {self.position}")
        # Extra space for alignment
        if self.is_category:
            return f"ALTER  Category \"{self.old_name}\" ({', '.join(changes)})"
        return f"ALTER  Channel #{self.old_name} ({', '.join(changes)})"

    def apply(self, guild: Guild) -> None:
        pass # TODO implement

@dataclasses.dataclass(frozen=True)
class DeleteChannelCommand(Command):
    name: str
    is_category: bool = False  # Whether this command is for a category, only for display purposes

    def __str__(self) -> str:
        return f'DELETE Channel "#{self.name}"'

    def apply(self, guild: Guild) -> None:
        discord.utils.get(guild.channels, name=self.name).delete()

@dataclasses.dataclass(frozen=True)
class CreateCategoryCommand(Command):
    name: str
    overwrites: RoleOverwrites | None = None

    def __str__(self) -> str:
        return f'CREATE Category "{self.name}"'

    def apply(self, guild: Guild) -> None:
        guild.create_category(self.name, overwrites=self.overwrites)

@dataclasses.dataclass(frozen=True)
class CreateChannelCommand(Command):
    name: str
    type: ChannelType
    category: Channel
    overwrites: RoleOverwrites | None = None
    topic: str = ""

    def __str__(self) -> str:
        return f'CREATE Channel #{self.name} in Category "{self.category.name}"'

    def apply(self, guild: Guild) -> None:
        if self.type == ChannelType.text:
            guild.create_text_channel(self.name, category=discord.utils.get(guild.categories, name=self.category.name), overwrites=self.overwrites, topic=self.topic)
        elif self.type == ChannelType.voice:
            guild.create_voice_channel(self.name, category=discord.utils.get(guild.categories, name=self.category.name), overwrites=self.overwrites)
        else:
            raise ValueError(f"Unsupported channel type: {self.type}")

ChannelCommand = AlterChannelCommand | DeleteChannelCommand | CreateCategoryCommand | CreateChannelCommand
