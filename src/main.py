import asyncio
import os
import sys
import logging

from dotenv import load_dotenv
from discord import Intents

from src.bot import BotClient
from rss import post_check_timer

logger = logging.getLogger("srbot")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

intents = Intents.default()
intents.members = True  # Listen to member joins

if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if token is None:
        print("No token provided.", file=sys.stderr)
        exit(1)

    bot = BotClient(logger=logger, intents=intents)
    loop = asyncio.get_event_loop()

try:
    loop.create_task(post_check_timer(bot))
    loop.run_until_complete(bot.start(token))
except KeyboardInterrupt:
    loop.run_until_complete(bot.close())
    # cancel all tasks lingering
finally:
    loop.close()
