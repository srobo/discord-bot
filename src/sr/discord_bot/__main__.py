import os
import sys
import logging
import argparse

import sentry_sdk
from dotenv import load_dotenv
from discord import Intents

from sr.discord_bot.bot import BotClient

load_dotenv()
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

token = os.getenv("DISCORD_TOKEN")
if token is None:
    print("No token provided.", file=sys.stderr)
    exit(1)

parser = argparse.ArgumentParser(description="Student Robotics Discord Bot")
subcommands = parser.add_subparsers(dest="command")
parser_run = subcommands.add_parser("run", help="Run the Discord bot")
parser_plan = subcommands.add_parser("plan", help="List pending guild changes")
parser_apply = subcommands.add_parser("apply", help="Apply pending guild changes")
args = parser.parse_args()

if args.command is None:
    parser.print_help()
    exit(1)

bot = BotClient(logger=logger, intents=intents)
bot.mode = args.command
bot.run(token)
