import os
import sys
import logging

from discord import Intents
from dotenv import load_dotenv

from src.bot import BotClient

logger = logging.getLogger('srbot')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

intents = Intents.default()
intents.members = True  # Listen to member joins

load_dotenv()
bot = BotClient(logger=logger, intents=intents)
bot.run(os.getenv('DISCORD_TOKEN'))
