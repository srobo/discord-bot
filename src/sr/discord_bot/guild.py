import json
import logging
import pathlib
import webbrowser
from datetime import datetime
from typing import TYPE_CHECKING

import discord.enums
from discord import Guild, TextChannel, PartialEmoji, ForumTag

from sr.discord_bot.constants import WELCOME_CATEGORY_NAME, PERMISSIONS, BLUESHIRT_ONBOARDING_CHANNEL_NAME, \
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


async def create_guild(client: "BotClient") -> None:
    year = datetime.today().year + 1
    icon = pathlib.Path('images/icon.png').read_bytes()
    logging.info(f"Creating guild for {year}")
    client.guild = await client.create_guild(name=f"Student Robotics {year}", icon=icon)
    logging.info("Guild created with ID " + str(client.guild.id))
    for channel in client.guild.channels:
        await channel.delete()
    await client.guild.edit(
        preferred_locale=discord.enums.Locale.british_english,
        verification_level=discord.enums.VerificationLevel.medium,
    )
    await upload_emoji(client.guild)
    await create_roles(client, client.guild)
    rules = await create_channels(client, client.guild)
    await send_template_messages(client, client.guild)
    invite = await rules.create_invite()
    with open(".env", "a", encoding="utf-8") as f:
        f.write("\nDISCORD_GUILD_ID=" + str(client.guild.id) + "\n")
    print(f"Invite link: {invite.url}")
    webbrowser.open(invite.url)


async def create_roles(client: "BotClient", guild: Guild) -> None:
    """Create the roles used in the server."""
    logging.info("Creating roles")
    blueshirt_blue = discord.Colour.from_str("#3270ed")
    client.admin_role = await guild.create_role(name=ADMIN_ROLE, mentionable=True, reason="Role for admins", colour=blueshirt_blue, permissions=PERMISSIONS['admin'])
    client.volunteer_role = await guild.create_role(name=VOLUNTEER_ROLE, mentionable=True, reason="Role for blueshirts",
                                                    hoist=True, colour=blueshirt_blue, permissions=PERMISSIONS['blueshirt'])
    robots = await guild.create_role(name="Robots", mentionable=True, hoist=True, colour=discord.Colour.from_str("#607d8b"))
    await guild.default_role.edit(mentionable= False, permissions=PERMISSIONS['everyone'])
    client.supervisor_role = await guild.create_role(name="Team Supervisor", mentionable=False, reason="Role for team supervisors", hoist=True, colour=discord.Colour.from_str("#e74c3c"))
    await guild.create_role(name="Team Support", mentionable=False, reason="Role for team supervisors", hoist=True, colour=discord.Colour.from_str("#992d22"))
    client.special_role = await guild.create_role(name=SPECIAL_ROLE, mentionable=False, reason="Role for volunteers")
    client.verified_role = await guild.create_role(name=VERIFIED_ROLE, mentionable=False, reason="Initial role for verified members", permissions=PERMISSIONS['verified'])
    me = await guild.fetch_member(client.user.id)
    await me.add_roles(client.admin_role, robots)
    logging.info("Roles created")


async def upload_emoji(guild: Guild) -> None:
    """Upload the emojis used in the server."""
    logging.info("Uploading emoji")
    emoji_path = pathlib.Path('images/emoji')
    for emoji_file in emoji_path.glob('*'):
        with open(emoji_file, 'rb') as f:
            await guild.create_custom_emoji(
                name=emoji_file.stem,
                image=f.read(),
            )
    logging.info("Emoji uploaded")


async def create_channels(client: "BotClient", guild: Guild) -> TextChannel:
    """Create the channels used in the server."""
    logging.info("Creating channels")
    for channel in await guild.fetch_channels():
        await channel.delete()

    cat_info = await guild.create_category("Information")
    rules = await guild.create_text_channel("welcome-and-rules", category=cat_info, overwrites={
        guild.default_role: discord.PermissionOverwrite(read_messages=True, send_messages=False),
    })
    announcements = await guild.create_text_channel("announcements", category=cat_info, overwrites={
        guild.default_role: discord.PermissionOverwrite(send_messages=False),
        client.volunteer_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    })
    client.feed_channel = await guild.create_text_channel("blog", category=cat_info, topic="Posts from the Student Robotics blog.")

    cat_support = await guild.create_category("Support")

    cat_blueshirt = await guild.create_category("Blueshirt Zone 🐝", overwrites={
        guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
        client.volunteer_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    })
    await guild.create_text_channel("audit-log", category=cat_blueshirt)
    client.blueshirt_onboarding_channel = await guild.create_text_channel("blueshirt-onboarding", category=cat_blueshirt, overwrites={
        client.special_role: discord.PermissionOverwrite(read_messages=True, read_message_history=True),
    })
    await guild.create_text_channel("blueshirt-banter", category=cat_blueshirt)
    await guild.create_text_channel("blueshirt-serious-business", category=cat_blueshirt, topic="A place to discuss what to do with cases on Discord")
    await guild.create_text_channel("team-stats", category=cat_blueshirt)
    await guild.create_voice_channel("blueshirt-banter", category=cat_blueshirt)

    cat_social = await guild.create_category("Social")
    await guild.create_text_channel("general", category=cat_social, topic="General discussion about Student Robotics. Use #support for support queries and #off-topic for other things.")
    client.announce_channel = await guild.create_text_channel("say-hello", category=cat_social, topic="Hello there!")
    await guild.create_text_channel("off-topic", category=cat_social, topic="Off-topic tech chat")
    await guild.create_text_channel("teams-on-the-web", category=cat_social, topic="A place to show off your team blogs and videos")

    cat_team_supervisors = await guild.create_category("Team Supervisors Only", overwrites={
        guild.default_role: discord.PermissionOverwrite(read_messages=False, send_messages=False),
        client.volunteer_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
        client.supervisor_role: discord.PermissionOverwrite(read_messages=True, send_messages=True),
    })
    await guild.create_text_channel("team-supervisors", category=cat_team_supervisors, topic="Channel for just team supervisors. Competitor-free.")

    await guild.create_category("Team Channels")
    await guild.create_category("Team Voice Channels")

    cat_admin = await guild.create_category("Admin Zone")
    await guild.create_text_channel("bot-spam", category=cat_admin)
    updates = await guild.create_text_channel("community-updates", category=cat_admin, topic="Discord community updates")

    client.welcome_category = await guild.create_category(WELCOME_CATEGORY_NAME)

    await guild.edit(
        community=True,
        rules_channel=rules,
        public_updates_channel=updates,
        explicit_content_filter=discord.enums.ContentFilter.all_members,
        system_channel=updates,
        system_channel_flags=discord.flags.SystemChannelFlags(),
    )
    await announcements.edit(type=discord.enums.ChannelType.news)
    emojis = await guild.fetch_emojis()
    await cat_support.create_forum(
        name="support",
        default_reaction_emoji=discord.utils.get(emojis, name="me2"),
        available_tags=[ForumTag(name=name, emoji=emoji) for name, emoji in FORUM_TAGS.items()]
    )

    logging.info("Channels created")
    return rules


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
                if channel.name == BLUESHIRT_ONBOARDING_CHANNEL_NAME and "Step 3" in message:
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

