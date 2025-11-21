from __future__ import annotations

import abc
import dataclasses
from typing import Mapping, TYPE_CHECKING

import discord
from discord import (
    Role,
    Guild,
    Member,
    Object,
    ChannelType,
    TextChannel,
    PermissionOverwrite,
)
from discord.abc import GuildChannel
from discord.utils import MISSING

from sr.discord_bot.utils import find_role_by_name, find_channel_by_name

if TYPE_CHECKING:
    from discord.types.guild import ChannelPositionUpdate

from sr.discord_bot.schema import (
    RoleType,
    Overwrites,
    ChannelUseCase,
    ChannelDefinition,
    ForumTagDefinition,
)
from sr.discord_bot.constants import (
    SPECIAL_ROLE,
    VERIFIED_ROLE,
    VOLUNTEER_ROLE,
    TEAM_LEADER_ROLE,
    TEAM_CATEGORY_NAME,
    WELCOME_CATEGORY_NAME,
    TEAM_VOICE_CATEGORY_NAME,
)

RoleOverwrites = dict[Role, PermissionOverwrite]

IGNORED_CATEGORIES = [
    TEAM_CATEGORY_NAME,
    TEAM_VOICE_CATEGORY_NAME,
    WELCOME_CATEGORY_NAME,
]


def match_overwrites(overwrites: Overwrites, guild: Guild) -> Mapping[Role | Member | Object, PermissionOverwrite]:
    return {
        guild.default_role: overwrites.get(RoleType.EVERYONE, PermissionOverwrite()),
        find_role_by_name(guild.roles, VERIFIED_ROLE): overwrites.get(RoleType.VERIFIED, PermissionOverwrite()),
        find_role_by_name(guild.roles, VOLUNTEER_ROLE): overwrites.get(RoleType.BLUESHIRT, PermissionOverwrite()),
        find_role_by_name(guild.roles, TEAM_LEADER_ROLE): overwrites.get(RoleType.SUPERVISOR, PermissionOverwrite()),
        find_role_by_name(guild.roles, SPECIAL_ROLE): overwrites.get(RoleType.UNVERIFIED_BLUESHIRT, PermissionOverwrite()),
    }


class ChannelSet:
    def __init__(self) -> None:
        self._channels: list[Channel] = []
        self._role_map: Mapping[Role, RoleType] | None = None

    def _get_role_type(self, role: Role, guild: Guild) -> RoleType:
        if self._role_map is None:
            self._role_map = {
                guild.default_role: RoleType.EVERYONE,
                find_role_by_name(guild.roles, VERIFIED_ROLE): RoleType.VERIFIED,
                find_role_by_name(guild.roles, VOLUNTEER_ROLE): RoleType.BLUESHIRT,
                find_role_by_name(guild.roles, TEAM_LEADER_ROLE): RoleType.SUPERVISOR,
                find_role_by_name(guild.roles, SPECIAL_ROLE): RoleType.UNVERIFIED_BLUESHIRT,
            }

        if role not in self._role_map:
            raise ValueError(f"Role type for '{role.name}' not found")

        return self._role_map[role]

    def _get_overwrites(self, channel: GuildChannel) -> Overwrites:
        return {
            self._get_role_type(subject, channel.guild): permissions
            for subject, permissions in channel.overwrites.items()
            if isinstance(subject, Role)
        }

    def count(self, category: Channel | None) -> int:
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
            overwrites=overwrites or {},
            topic="",
            category=None,
            channel_type=ChannelType.category,
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
        channel_type: int = ChannelType.text.value,
        use_case: ChannelUseCase | None = None,
    ) -> None:
        if category and category.channel_type != ChannelType.category:
            raise ValueError("The category must be a channel of type 'category'.")
        text_channel = Channel(
            name=name,
            position=position if position is not None else self.count(category),
            overwrites=overwrites or {},
            topic=topic,
            category=category,
            channel_type=ChannelType(channel_type),
            old_names=old_names or [],
            use_case=use_case,
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
        if category is not None and category.channel_type != ChannelType.category:
            raise ValueError("The category must be of type 'category'.")
        voice_channel = Channel(
            name=name,
            position=position if position is not None else self.count(category),
            overwrites=overwrites or {},
            topic="",
            category=category,
            channel_type=ChannelType.voice,
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
        available_tags: list[ForumTagDefinition] | None = None,
    ) -> None:
        if category and category.channel_type != ChannelType.category:
            raise ValueError("The category must be a channel of type 'category'.")
        forum_channel = Channel(
            name=name,
            position=position if position is not None else self.count(category),
            overwrites=overwrites or {},
            topic="",
            category=category,
            channel_type=ChannelType.forum,
            old_names=old_names or [],
            default_reaction_emoji=default_reaction_emoji,
            available_tags=available_tags or [],
        )
        self._channels.append(forum_channel)

    @classmethod
    def diff(cls, old: ChannelSet, new: ChannelSet) -> list[ChannelCommand]:
        """Calculate the difference between two ChannelSets."""
        commands: list[ChannelCommand] = []
        cls._diff_channels(old._channels, new._channels, commands)
        return commands

    async def sort_channels(self, guild: Guild) -> None:
        for category in [c for c in self._channels if c.is_category]:
            channels = [c for c in self._channels if c.category == category]
            await self.sort_category(channels, guild)
        channels = [c for c in self._channels if c.category is None]
        await self.sort_category(channels, guild)

    async def sort_category(self, channels: list[Channel], guild: Guild) -> None:
        payload: list[ChannelPositionUpdate] = [
            {'id': await ChannelSet.get_channel_id(c, guild), 'position': c.position}
            for c in channels
        ]
        await guild._state.http.bulk_channel_update(guild.id, payload)

    @classmethod
    def _diff_channels(cls, old: list[Channel], new: list[Channel], commands: list[ChannelCommand]) -> None:
        """Calculate the difference in channels between two ChannelSets."""

        seen_old_channel_names = set()

        late_commands: list[ChannelCommand] = []

        for new_index, new_channel in enumerate(new):
            old_channel = next((x for x in old if x.name == new_channel.name or x.name in new_channel.old_names), None)
            if old_channel is None:
                command: ChannelCommand
                if new_channel.is_category:
                    command = CreateCategoryCommand(name=new_channel.name, overwrites=new_channel.overwrites)
                elif new_channel.channel_type == ChannelType.forum:
                    command = CreateForumCommand(
                        name=new_channel.name,
                        category=new_channel.category,
                        overwrites=new_channel.overwrites,
                        topic=new_channel.topic,
                        default_reaction_emoji=new_channel.default_reaction_emoji,
                        available_tags=new_channel.available_tags,
                    )
                else:
                    command = CreateChannelCommand(
                        name=new_channel.name,
                        channel_type=new_channel.channel_type,
                        category=new_channel.category,
                        overwrites=new_channel.overwrites,
                        topic=new_channel.topic,
                        use_case=new_channel.use_case,
                    )
                if command.requires_community:
                    late_commands.append(command)
                else:
                    commands.append(command)
            else:
                seen_old_channel_names.add(old_channel.name)
                command = AlterChannelCommand.diff(old_channel, new_channel, old_channel.channel_type)
                if command.has_changes:
                    commands.append(command)

        commands.extend(late_commands)

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
            category_present = channel.category is not None
            category_ignored = category_present and (channel.category.name in IGNORED_CATEGORIES
                                                     if channel.category else False)
            category_channel: Channel | None = categories[channel.category.id] \
                if channel.category and channel.category.id in categories else None
            if channel.type == ChannelType.category or category_ignored:
                continue
            if channel.type == ChannelType.voice:
                channel_set.create_voice_channel(
                    name=channel.name,
                    category=category_channel,
                    overwrites=channel_set._get_overwrites(channel),
                    old_names=[channel.name],
                    position=channel.position,
                )
            elif channel.type == ChannelType.forum:
                default_reaction = channel.default_reaction_emoji.name if channel.default_reaction_emoji else None
                channel_set.create_forum_channel(
                    name=channel.name,
                    category=category_channel,
                    overwrites=channel_set._get_overwrites(channel),
                    old_names=[channel.name],
                    position=channel.position,
                    default_reaction_emoji=default_reaction,
                    available_tags=[ForumTagDefinition.from_discord(tag) for tag in channel.available_tags],
                )
            else:
                channel_set.create_text_channel(
                    name=channel.name,
                    category=category_channel,
                    overwrites=channel_set._get_overwrites(channel),
                    topic=channel.topic or "",
                    old_names=[channel.name],
                    position=channel.position,
                    channel_type=channel.type.value,
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
                elif channel_definition.channel_type == ChannelType.forum:
                    channel_set.create_forum_channel(
                        name=channel_definition.name,
                        category=category,
                        overwrites=channel_definition.overwrites,
                        old_names=channel_definition.old_names,
                        default_reaction_emoji=channel_definition.default_reaction_emoji,
                        available_tags=channel_definition.tags,
                    )
                else:
                    channel_set.create_text_channel(
                        name=channel_definition.name,
                        category=category,
                        overwrites=channel_definition.overwrites,
                        topic=channel_definition.topic,
                        old_names=channel_definition.old_names,
                        channel_type=channel_definition.channel_type.value,
                    )
        return channel_set

    @staticmethod
    async def get_channel_id(ch: Channel, guild: Guild) -> int:
        await guild.fetch_channels()
        channel: GuildChannel | None
        if ch.channel_type == ChannelType.category:
            channel = discord.utils.get(guild.categories, name=ch.name)
        elif ch.channel_type == ChannelType.text:
            channel = discord.utils.get(guild.text_channels, name=ch.name)
        elif ch.channel_type == ChannelType.voice:
            channel = discord.utils.get(guild.voice_channels, name=ch.name)
        elif ch.channel_type == ChannelType.forum:
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
    overwrites: Overwrites
    topic: str
    category: Channel | None
    channel_type: ChannelType
    old_names: list[str] = dataclasses.field(default_factory=list)
    # Forum-specific:
    default_reaction_emoji: str | None = None  # Name of the emoji
    available_tags: list[ForumTagDefinition] = dataclasses.field(default_factory=list)
    # Bot use only:
    use_case: ChannelUseCase | None = None

    def __eq__(self, other: object) -> bool:
        if other is None:
            return False
        if not isinstance(other, Channel):
            return NotImplemented
        return self.name == other.name

    @property
    def is_category(self) -> bool:
        return self.channel_type == ChannelType.category


class Command(abc.ABC):
    @abc.abstractmethod
    async def apply(self, guild: Guild) -> None:
        ...

    @property
    def has_changes(self) -> bool:
        return True

    @property
    def requires_community(self) -> bool:
        return False


@dataclasses.dataclass
class AlterChannelCommand(Command):
    old_name: str
    new_name: str
    overwrites: Overwrites | None = None
    topic: str | None = None
    category: Channel | None = None
    is_category: bool = False  # Whether this command is for a category, only for display purposes
    channel_type: ChannelType = ChannelType.text  # Used for sorting
    # Forum-specific:
    default_reaction_emoji: str | None = None  # Name of the emoji
    available_tags: list[str] = dataclasses.field(default_factory=list)
    # Bot use only:
    use_case: ChannelUseCase | None = None

    @classmethod
    def diff(cls, old_channel: Channel, new_channel: Channel, channel_type: ChannelType) -> AlterChannelCommand:
        command = cls(old_name=old_channel.name, new_name=new_channel.name,
                      is_category=new_channel.is_category, channel_type=channel_type, use_case=new_channel.use_case)
        changed_category = new_channel.category is not None and old_channel.category != new_channel.category
        if old_channel.overwrites != new_channel.overwrites:
            command.overwrites = new_channel.overwrites
        if old_channel.topic != new_channel.topic:
            command.topic = new_channel.topic
        if not old_channel.category or changed_category:
            command.category = new_channel.category
        return command

    def is_rename(self) -> bool:
        """Check if the command is a rename."""
        return self.old_name != self.new_name

    def has_attribute_changes(self) -> bool:
        """Check if the command has any changes."""
        return (self.overwrites is not None
                or self.topic is not None
                or self.category is not None)

    @property
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

    @classmethod
    def get_role_by_role_type(cls, role_type: RoleType, guild: Guild) -> Role:
        if role_type == RoleType.EVERYONE:
            return guild.default_role

        role_names = {
            RoleType.VERIFIED: VERIFIED_ROLE,
            RoleType.BLUESHIRT: VOLUNTEER_ROLE,
            RoleType.SUPERVISOR: TEAM_LEADER_ROLE,
            RoleType.UNVERIFIED_BLUESHIRT: SPECIAL_ROLE,
        }

        if role := discord.utils.get(guild.roles, name=role_names[role_type]):
            return role
        raise ValueError("Invalid role type")

    async def apply(self, guild: Guild) -> None:
        channel = discord.utils.get(guild.channels, name=self.old_name)
        if channel is None:
            raise Exception("Failed to find channel")

        kwargs = {}
        if self.is_rename():
            kwargs["name"] = self.new_name

        if self.topic is not None:
            kwargs["topic"] = self.topic

        if self.category is not None:
            kwargs["category"] = find_channel_by_name(guild.channels, self.category.name)  # type: ignore

        if self.overwrites is not None:
            overwrites = {
                AlterChannelCommand.get_role_by_role_type(role_type, guild): permissions
                for role_type, permissions in self.overwrites.items()
            }
            if overwrites != channel.overwrites:
                kwargs["overwrites"] = overwrites  # type: ignore

        if channel.type == ChannelType.forum:
            await guild.fetch_emojis()
            default_reaction_emoji = discord.utils.get(guild.emojis, name=self.default_reaction_emoji)
            if default_reaction_emoji is not None:
                channel.default_reaction_emoji = default_reaction_emoji._to_partial()
            # Sync tags
            if self.available_tags and isinstance(channel, discord.ForumChannel):
                existing_tags = {tag.name: tag for tag in channel.available_tags}
                new_tags = []
                for tag_name in self.available_tags:
                    if tag_name in existing_tags:
                        new_tags.append(existing_tags[tag_name])
                    else:
                        new_tags.append(await channel.create_tag(name=tag_name))
                kwargs["available_tags"] = new_tags  # type: ignore

        if kwargs:
            await channel.edit(**kwargs)
        if isinstance(channel, TextChannel) and self.use_case is not None:
            if self.use_case == ChannelUseCase.RULES and guild.rules_channel != channel:
                await guild.edit(rules_channel=channel)
            elif self.use_case == ChannelUseCase.DISCORD and guild.system_channel != channel:
                await guild.edit(system_channel=channel)
            elif self.use_case == ChannelUseCase.ANNOUNCE and guild.public_updates_channel != channel:
                await guild.edit(public_updates_channel=channel)


@dataclasses.dataclass(frozen=True)
class DeleteChannelCommand(Command):
    name: str
    is_category: bool = False  # Whether this command is for a category, only for display purposes

    def __str__(self) -> str:
        type_str = "Category" if self.is_category else "Channel"
        return f'DELETE {type_str} "#{self.name}"'

    async def apply(self, guild: Guild) -> None:
        channel = discord.utils.get(guild.channels, name=self.name)
        if channel is not None:
            await channel.delete()


@dataclasses.dataclass(frozen=True)
class CreateCategoryCommand(Command):
    name: str
    overwrites: Overwrites = dataclasses.field(default_factory=dict)

    def __str__(self) -> str:
        return f'CREATE Category "{self.name}"'

    async def apply(self, guild: Guild) -> None:
        if self.overwrites is None:
            return
        await guild.create_category(self.name, overwrites=match_overwrites(self.overwrites, guild))


@dataclasses.dataclass(frozen=True)
class CreateChannelCommand(Command):
    name: str
    channel_type: ChannelType
    category: Channel | None = None
    overwrites: Overwrites = dataclasses.field(default_factory=dict)
    topic: str = ""
    # Bot use only:
    use_case: ChannelUseCase | None = None

    def __str__(self) -> str:
        s = f'CREATE Channel #{self.name}'

        if self.category is not None:
            s += f' in Category "{self.category.name}"'

        return s

    @property
    def requires_community(self) -> bool:
        return self.channel_type == ChannelType.news

    async def apply(self, guild: Guild) -> None:
        if self.category is not None:
            channel_category = discord.utils.get(guild.categories, name=self.category.name)
        else:
            channel_category = None
        overwrites = match_overwrites(self.overwrites or {}, guild)
        if self.channel_type == ChannelType.text or self.channel_type == ChannelType.news:
            channel = await guild.create_text_channel(
                self.name,
                category=channel_category,
                overwrites=overwrites,
                topic=self.topic,
                news=self.channel_type == ChannelType.news and 'NEWS' in guild.features,
            )

            if self.use_case == ChannelUseCase.RULES:
                await guild.edit(rules_channel=channel)
            elif self.use_case == ChannelUseCase.DISCORD:
                await guild.edit(system_channel=channel)
            elif self.use_case == ChannelUseCase.ANNOUNCE:
                await guild.edit(public_updates_channel=channel)
        elif self.channel_type == ChannelType.voice:
            await guild.create_voice_channel(
                self.name,
                category=channel_category,
                overwrites=overwrites,
            )
        else:
            raise ValueError(f"Unsupported channel type: {self.channel_type}")


@dataclasses.dataclass(frozen=True)
class CreateForumCommand(Command):
    name: str
    category: Channel | None = None
    overwrites: Overwrites = dataclasses.field(default_factory=dict)
    topic: str = ""
    default_reaction_emoji: str | None = None
    available_tags: list[ForumTagDefinition] = dataclasses.field(default_factory=list)

    def __str__(self) -> str:
        return f'CREATE Forum #{self.name}'

    @property
    def requires_community(self) -> bool:
        return True

    async def apply(self, guild: Guild) -> None:
        emojis = await guild.fetch_emojis()
        default_reaction_emoji = discord.utils.get(emojis, name=self.default_reaction_emoji.strip(':')) \
            if self.default_reaction_emoji else MISSING
        await guild.create_forum(
            name=self.name,
            category=discord.utils.get(guild.categories, name=self.category.name) if self.category else None,
            overwrites=match_overwrites(self.overwrites or {}, guild),
            topic=self.topic,
            default_reaction_emoji=default_reaction_emoji,
            available_tags=[tag.to_discord() for tag in self.available_tags],
        )


ChannelCommand = \
    AlterChannelCommand | \
    DeleteChannelCommand | \
    CreateCategoryCommand | \
    CreateChannelCommand | \
    CreateForumCommand
