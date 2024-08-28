import os
import sys
import logging

from dotenv import load_dotenv
from discord import Intents

from src.bot import BotClient

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
    bot.run(token)
