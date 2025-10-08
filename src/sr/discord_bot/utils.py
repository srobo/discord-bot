from typing import TypeVar, Sequence

import discord
from discord import Role
from discord.abc import GuildChannel


def find_role_by_name(roles: Sequence[Role], name: str) -> Role:
    value = discord.utils.get(roles, name=name)
    if value is None:
        raise ValueError(f"Role '{name}' not found in guild")
    return value


ChannelT = TypeVar("ChannelT", bound=GuildChannel)


def find_channel_by_name(channels: Sequence[ChannelT], name: str) -> ChannelT:
    value = discord.utils.get(channels, name=name)
    if value is None:
        raise ValueError(f"Channel '{name}' not found in guild")
    return value
