import asyncio
from typing import Optional

import discord
import feedparser
from bs4 import BeautifulSoup
from feedparser import FeedParserDict

from src.bot import BotClient
from src.constants import FEED_URL, FEED_CHECK_INTERVAL, FEED_CHANNEL_NAME


def get_feed_channel(bot: BotClient) -> discord.TextChannel:
    for channel in bot.get_all_channels():
        if channel.name == FEED_CHANNEL_NAME:
            return channel


async def get_last_blog_post(channel: discord.TextChannel) -> str | None:
    # TODO: This doesn't work when the bot is restarted, store the URL instead
    last_message: Optional[discord.Message] = channel.last_message
    if last_message is not None and len(last_message.embeds) > 0:
        return last_message.embeds[0].url

    return None


async def check_posts(bot: BotClient):
    feed = feedparser.parse(FEED_URL)
    channel = get_feed_channel(bot)
    post = feed.entries[0]
    newest_post_url = post.link
    last_message_url = await get_last_blog_post(channel)
    if newest_post_url != last_message_url:
        await channel.send(embed=create_embed(post))


def create_embed(post: FeedParserDict) -> discord.Embed:
    soup = BeautifulSoup(post.content[0].value, 'html.parser')

    embed = discord.Embed(
        title=post.title,
        type="article",
        url=post.link,
        description=soup.p.text,
    )

    if len(post.media_thumbnail) > 0:
        embed.set_image(url=post.media_thumbnail[0]['url'])

    return embed


async def post_check_timer(bot: BotClient):
    await bot.wait_until_ready()
    while True:
        await check_posts(bot)
        await asyncio.sleep(FEED_CHECK_INTERVAL)
