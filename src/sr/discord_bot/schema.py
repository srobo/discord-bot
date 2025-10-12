import dataclasses
import sys

if sys.version_info >= (3, 11):
    from enum import StrEnum
else:
    from backports.strenum import StrEnum
from typing import Any

from discord import ForumTag, ChannelType, PartialEmoji


class RoleType(StrEnum):
    EVERYONE = "everyone"
    VERIFIED = "verified"
    BLUESHIRT = "blueshirt"
    SUPERVISOR = "supervisor"
    UNVERIFIED_BLUESHIRT = "unverified_blueshirt"


Overwrites = dict[RoleType, dict[str, bool]]


class ChannelUseCase(StrEnum):
    """Special use cases for Discord channels."""
    RULES = "rules"
    """Initial channel users will see when they join the server. Contains the 'Join Team' button."""
    FEED = "feed"
    """Channel for blog posts from the Student Robotics blog."""
    AUDIT = "audit"
    """Audit Log for moderation"""
    STATS = "stats"
    """Channel for team stats"""
    ANNOUNCE = "announce"
    """Channel in which new members are announced."""
    DISCORD = "discord"
    """Discord system messages. (Raid alerts, community updates, etc.)"""


@dataclasses.dataclass
class ForumTagDefinition:
    name: str
    emoji: str

    @classmethod
    def from_discord(cls, tag: ForumTag) -> "ForumTagDefinition":
        return cls(name=tag.name, emoji=str(tag.emoji) if tag.emoji else "")

    def to_discord(self) -> ForumTag:
        return ForumTag(name=self.name, emoji=PartialEmoji.from_str(self.emoji))


@dataclasses.dataclass
class ChannelDefinition:
    name: str
    old_names: list[str] = dataclasses.field(default_factory=list)
    overwrites: Overwrites | None = None
    topic: str = ""
    category: "ChannelDefinition | None" = None
    channel_type: ChannelType = ChannelType.text
    use_case: ChannelUseCase | None = None
    channels: list["ChannelDefinition"] = dataclasses.field(default_factory=list)
    # Forum-specific:
    tags: list[ForumTagDefinition] = dataclasses.field(default_factory=list)
    default_reaction_emoji: str | None = None

    @classmethod
    def load(  # type: ignore[misc] # This gets validated when the YAML is validated against the schema.
        cls,
        data: dict[str, Any],
        category: "ChannelDefinition|None" = None,
    ) -> "ChannelDefinition":
        has_children = "channels" in data
        default_type = "category" if has_children else "text"

        channel = cls(
            name=data["name"],
            old_names=data.get("old_names", []),
            overwrites=data.get("permissions", {}),
            topic=data.get("topic", ""),
            category=category,
            channel_type=ChannelType[data.get("channel_type", default_type)],
            use_case=ChannelUseCase(data["use_case"]) if data.get("use_case") else None,
            channels=[],
        )

        if channel.channel_type == ChannelType.forum:
            channel.tags = [ForumTagDefinition(**tag) for tag in data.get("tags", [])]
            channel.default_reaction_emoji = data.get("default_reaction_emoji")

        if has_children:
            for child_channel in data["channels"]:
                channel.channels.append(cls.load(child_channel, category))

        return channel
