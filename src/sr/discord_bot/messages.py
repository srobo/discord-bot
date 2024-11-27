from pathlib import Path
from string import Template
from typing import TYPE_CHECKING

from discord import File, TextChannel, Guild, Emoji, Message
from discord.utils import get

if TYPE_CHECKING:
    from sr.discord_bot.bot import BotClient

import re

templates: dict[str, Template] = {}
emojis: dict[str, Emoji] = {}

IMAGE_REGEX = re.compile(r"!\[(?P<alt>.*)]\((?P<path>.*)\)")
EMOJI_REGEX = re.compile(r":(?P<name>[A-Za-z0-9_]+):")
CHANNEL_REGEX = re.compile(r"#(?P<name>[\w-]+)")


def get_channel(guild: Guild, match: re.Match) -> str:
    """Get a channel by its name in the given guild."""
    groups = match.groupdict()
    if "name" in groups:
        if channel := get(guild.channels, name=groups["name"]):
            return channel.mention
    return match[0]  # Return the original match if no channel is found


async def template(
    client: "BotClient",
    guild: Guild,
    template_name: str,
    **kwargs,
) -> list[str]:
    kwargs = get_default_args(client, guild) | kwargs
    if template_name not in templates:
        with open(f"messages/{template_name}.md", "r", encoding="utf-8") as file:
            templates[template_name] = Template(file.read())

    full_text = templates[template_name].substitute(**kwargs)

    if len(emojis) == 0:
        for emoji in await guild.fetch_emojis():
            emojis[emoji.name] = emoji

    full_text = re.sub(
        EMOJI_REGEX,
        lambda m: str(emojis[m.group('name')]),
        full_text,
    )

    full_text = re.sub(
        CHANNEL_REGEX,
        lambda m: get_channel(guild, m),
        full_text,
    )

    return full_text.split("---\n")


def get_default_args(client: "BotClient", guild: Guild) -> dict[str, str]:
    """Get the default arguments for the templates."""
    return {
        "bot": client.user.mention,
        "y": guild.name[-4:],
        "blueshirt": client.volunteer_role.mention,
    }


async def post_message(channel: TextChannel, message: str, **kwargs) -> Message | None:
    """Post a message to a channel."""
    # Check if the message contains an image
    message = message.strip()
    image = re.match(IMAGE_REGEX, message)

    if image:
        path = Path(image.group("path"))
        return await channel.send(
            file=File(
                path,
                filename=path.name,
                description=image.group("alt")
            ),
        )
    elif message != "":
        return await channel.send(message, suppress_embeds=True, **kwargs)
    return None
