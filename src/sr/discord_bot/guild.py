import asyncio
import json
import logging
import os
import pathlib
from datetime import datetime
from typing import TYPE_CHECKING

import discord.enums
from discord import Guild, TextChannel, PartialEmoji

from sr.discord_bot.channel import ChannelSet
from sr.discord_bot.constants import PERMISSIONS, BLUESHIRT_ONBOARDING_CHANNEL_NAME, \
    SPECIAL_ROLE, ADMIN_ROLE, VOLUNTEER_ROLE, VERIFIED_ROLE
from sr.discord_bot.messages import template, post_message
from sr.discord_bot.ui import BlueshirtConfirmView

if TYPE_CHECKING:
    from sr.discord_bot.bot import BotClient


FORUM_TAGS = {
    "Rules": PartialEmoji.from_str("📜"),
    "Kit": PartialEmoji.from_str("🧰"),
    "Programming": PartialEmoji.from_str("👩‍💻"),
    "Simulator": PartialEmoji.from_str("🐞"),
    "Competition": PartialEmoji.from_str("🏆"),
    "Challenges": PartialEmoji.from_str("🏅"),
    "Microgames": PartialEmoji.from_str("🔬"),
    "Other": PartialEmoji.from_str("❓"),
    "Resolved": PartialEmoji.from_str("✅"),
}


async def setup_guild(client: "BotClient") -> None:
    year = datetime.today().year + 1
    icon = pathlib.Path(os.getenv('SR_GUILD_ICON') or 'images/icon.png').read_bytes()
    suffix = os.getenv('SR_GUILD_SUFFIX') if 'SR_GUILD_SUFFIX' in os.environ else year
    name=f"Student Robotics {suffix}"

    await client.guild.edit(
        name=name,
        icon=icon,
    )
    await upload_emoji(client.guild)
    await create_roles(client, client.guild)
    await create_channels(client, client.guild)
    await send_template_messages(client, client.guild)


async def create_roles(client: "BotClient", guild: Guild) -> None:
    """Create the roles used in the server."""
    logging.info("Creating roles")
    blueshirt_blue = discord.Colour.from_str("#3270ed")

    await guild.default_role.edit(mentionable=False, permissions=PERMISSIONS['everyone'])
    if discord.utils.get(guild.roles, name=ADMIN_ROLE) is None:
        client.admin_role = await guild.create_role(name=ADMIN_ROLE, mentionable=True, reason="Role for admins", colour=blueshirt_blue, permissions=PERMISSIONS['admin'])
    if discord.utils.get(guild.roles, name=VOLUNTEER_ROLE) is None:
        client.volunteer_role = await guild.create_role(name=VOLUNTEER_ROLE, mentionable=True, reason="Role for blueshirts",
                                                        hoist=True, colour=blueshirt_blue, permissions=PERMISSIONS['blueshirt'])
    if discord.utils.get(guild.roles, name="Robots") is None:
        robots = await guild.create_role(name="Robots", mentionable=True, hoist=True, colour=discord.Colour.from_str("#607d8b"))
        me = await guild.fetch_member(client.user.id)
        await me.add_roles(client.admin_role, robots)
    if discord.utils.get(guild.roles, name="Team Supervisor") is None:
        client.supervisor_role = await guild.create_role(name="Team Supervisor", mentionable=False, reason="Role for team supervisors", hoist=True, colour=discord.Colour.from_str("#e74c3c"))
    if discord.utils.get(guild.roles, name="Team Support") is None:
        await guild.create_role(name="Team Support", mentionable=False, reason="Role for team supervisors", hoist=True, colour=discord.Colour.from_str("#992d22"))
    if discord.utils.get(guild.roles, name=SPECIAL_ROLE) is None:
        client.special_role = await guild.create_role(name=SPECIAL_ROLE, mentionable=False, reason="Role for volunteers")
    if discord.utils.get(guild.roles, name=VERIFIED_ROLE) is None:
        client.verified_role = await guild.create_role(name=VERIFIED_ROLE, mentionable=False, reason="Initial role for verified members", permissions=PERMISSIONS['verified'])
    logging.info("Roles created")


async def upload_emoji(guild: Guild) -> None:
    """Upload the emojis used in the server."""
    logging.info("Uploading emoji")
    emoji_path = pathlib.Path('images/emoji')
    existing = await guild.fetch_emojis()
    for emoji_file in emoji_path.glob('*'):
        with open(emoji_file, 'rb') as f:
            if any(e.name == emoji_file.stem for e in existing):
                continue
            await guild.create_custom_emoji(
                name=emoji_file.stem,
                image=f.read(),
            )
    logging.info("Emoji uploaded")


async def create_channels(client: "BotClient", guild: Guild) -> None:
    """Create the channels used in the server."""
    logging.info("Creating channels")
    diff = ChannelSet.diff(ChannelSet.from_guild(guild), ChannelSet.from_definitions(client.channel_defs))
    for change in diff:
        if change.requires_community and "COMMUNITY" not in guild.features:
            logging.info("Enabling community features...")
            rules_channel = discord.utils.get(guild.channels, name=client.rules_channel_name)
            public_updates_channel = discord.utils.get(guild.channels, name=client.discord_announcements_channel_name)
            await guild.edit(
                preferred_locale=discord.enums.Locale.british_english,
                explicit_content_filter=discord.enums.ContentFilter.all_members,
                verification_level=discord.enums.VerificationLevel.low,
                community=True,
                rules_channel=rules_channel,
                public_updates_channel=public_updates_channel
            )
        logging.info(f"Applying change: {change}")
        await change.apply(guild)
        await asyncio.sleep(.5)  # avoid hitting rate limits

    logging.info("Channels created")


async def send_template_messages(client: "BotClient", guild: Guild):
    """Send template messages to the server."""
    logging.info("Sending template messages")
    messages_path = pathlib.Path('messages')
    for message_file in messages_path.glob('*'):
        channel_name = message_file.stem
        channel = discord.utils.get(guild.channels, name=channel_name)
        if channel is None:
            continue
        if isinstance(channel, TextChannel):
            messages = await template(client, guild, channel_name)

            for index, message in enumerate(messages):
                if channel == client.blueshirt_onboarding_channel and "Step 3" in message:
                    result = await post_message(channel, message, view=BlueshirtConfirmView())
                else:
                    result = await post_message(channel, message)

                if result is not None:
                    if channel.id not in client.bot_messages:
                        client.bot_messages[channel.id] = []
                    client.bot_messages[channel.id].append(result.id)
    with open("bot_messages.json", "w", encoding="utf-8") as f:
        json.dump(client.bot_messages, f)
    logging.info("Template messages sent")

