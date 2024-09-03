# file to store messages being dynamically updated between reboots
import json
from typing import Any, Dict, NamedTuple, TYPE_CHECKING

import discord
from discord import app_commands

from sr.discord_bot.constants import VOLUNTEER_ROLE

if TYPE_CHECKING:
    from sr.discord_bot.bot import BotClient

SUBSCRIBE_MSG_FILE = 'subscribed_messages.json'


class SubscribedMessage(NamedTuple):
    """A message that is updated when the server statistics change."""

    channel_id: int
    message_id: int
    members: bool = True
    warnings: bool = True
    stats: bool = False

    @classmethod
    def load(cls, dct: Dict[str, Any]) -> 'SubscribedMessage':  # type:ignore[misc]
        """Load a SubscribedMessage object from a dictionary."""
        return cls(**dct)

    def __eq__(self, comp: object) -> bool:
        if not isinstance(comp, SubscribedMessage):
            return False
        return (
            self.channel_id == comp.channel_id
            and self.message_id == comp.message_id
        )


@app_commands.guild_only()
@app_commands.default_permissions()
class Stats(app_commands.Group):
    def __init__(self) -> None:
        super().__init__(description="Posts team member statistics")


@app_commands.command(name='post')  # type:ignore[arg-type]
@app_commands.describe(
    members='Display the number of members in each team',
    warnings='Display warnings about missing supervisors and empty teams',
    stats='Display statistics about the teams',
)
@app_commands.checks.has_role(VOLUNTEER_ROLE)
async def post_stats(
    ctx: discord.interactions.Interaction["BotClient"],
    members: bool = False,
    warnings: bool = False,
    stats: bool = False,
) -> None:
    """Generate statistics for the server and send them to the channel."""
    if (members, warnings, stats) == (False, False, False):
        members = True
        warnings = True
    message = ctx.client.stats_message(members, warnings, stats)

    await send_response(ctx, message)


@discord.app_commands.command(name='subscribe')  # type:ignore[arg-type]
@app_commands.describe(
    members='Display the number of members in each team',
    warnings='Display warnings about missing supervisors and empty teams',
    stats='Display statistics about the teams',
)
@app_commands.checks.has_role(VOLUNTEER_ROLE)
async def stats_subscribe(
    ctx: discord.interactions.Interaction["BotClient"],
    members: bool = False,
    warnings: bool = False,
    stats: bool = False,
) -> None:
    """Subscribe to updates for statistics for the server and send a subscribed message."""
    if (members, warnings, stats) == (False, False, False):
        members = True
        warnings = True
    message = ctx.client.stats_message(members, warnings, stats)

    bot_message = await send_response(ctx, message)
    if bot_message is None:
        return
    ctx.client.add_subscribed_message(SubscribedMessage(
        bot_message.channel.id,
        bot_message.id,
        members,
        warnings,
        stats,
    ))


async def send_response(
    ctx: discord.interactions.Interaction['BotClient'],
    message: str,
) -> discord.Message | None:
    """Respond to an interaction and return the bot's message object."""
    try:
        await ctx.response.send_message(f"```\n{message}\n```")
        bot_message = await ctx.original_response()
    except discord.NotFound as e:
        print('Unable to find original message')
        print(e)
    except (discord.HTTPException, discord.ClientException) as e:
        print('Unable to connect to discord server')
        print(e)
    else:
        return bot_message
    return None


def load_subscribed_messages(client: 'BotClient') -> None:
    """Load subscribed message details from file."""
    try:
        with open(SUBSCRIBE_MSG_FILE) as f:
            client.subscribed_messages = json.load(f, object_hook=SubscribedMessage.load)
    except (json.JSONDecodeError, FileNotFoundError):
        with open(SUBSCRIBE_MSG_FILE, 'w') as f:
            f.write('[]')
