import dataclasses
from enum import StrEnum

from discord import ChannelType


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

@dataclasses.dataclass(frozen=True)
class ChannelDefinition:
    name: str
    old_names: list[str] = dataclasses.field(default_factory=list)
    overwrites: Overwrites | None = None
    topic: str = ""
    category: "ChannelDefinition | None" = None
    channel_type: ChannelType = ChannelType.text
    use_case: ChannelUseCase | None = None

    @classmethod
    def load(cls, data: dict, category: "CategoryChannelDefinition|None") -> "ChannelDefinition":
        return cls(
            name=data["name"],
            old_names=data.get("old_names", []),
            overwrites=data.get("permissions"),
            topic=data.get("topic", ""),
            category=category if category else None,
            channel_type=ChannelType[data.get("channel_type", "text")],
            use_case=ChannelUseCase(data["use_case"]) if data.get("use_case") else None,
        )

@dataclasses.dataclass(frozen=True)
class CategoryChannelDefinition:
    name: str
    channels: list[ChannelDefinition]
    overwrites: Overwrites | None = None
    old_names: list[str] = dataclasses.field(default_factory=list)

    @classmethod
    def load(cls, data: dict):
        category = cls(
            name=data["name"],
            overwrites=data.get("permissions"),
            old_names=data.get("old_names", []),
            channels=[],
        )
        category_channels = [ChannelDefinition.load(ch_data, category) for ch_data in data.get("channels", [])]
        object.__setattr__(category, 'channels', category_channels)
        return category
