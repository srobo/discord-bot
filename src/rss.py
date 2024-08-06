import os
from typing import List

import discord
import feedparser
from bs4 import BeautifulSoup
from feedparser import FeedParserDict

from src.constants import FEED_URL, FEED_CHANNEL_NAME


def get_seen_posts() -> List[str]:
    if os.path.exists('seen_posts.txt'):
        with open('seen_posts.txt', 'r') as f:
            return f.readlines()

    return []


def add_seen_post(post_id: str) -> None:
    with open('seen_posts.txt', 'a') as f:
        f.write(post_id + '\n')


async def check_posts(guild: discord.Guild) -> None:
    feed = feedparser.parse(FEED_URL)
    channel = discord.utils.get(guild.channels, name=FEED_CHANNEL_NAME)
    post = feed.entries[0]

    if post.id + "\n" not in get_seen_posts():
        await channel.send(embed=create_embed(post))
        add_seen_post(post.id)


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