import os
import sys
import logging

import sentry_sdk
from dotenv import load_dotenv
from discord import Intents

from sr.discord_bot.bot import BotClient

logger = logging.getLogger("srbot")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)
sentry_sdk.init(
    dsn=os.getenv("SENTRY_DSN"),
    traces_sample_rate=1.0,
)

intents = Intents.default()
intents.members = True  # Listen to member joins

if __name__ == "__main__":
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")
    if token is None:
        print("No token provided.", file=sys.stderr)
        exit(1)

    bot = BotClient(logger=logger, intents=intents)
    bot.run(token)
