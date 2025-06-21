import argparse
import asyncio
import os

import discord
from dotenv import load_dotenv

async def delete_guilds(guild_ids: list[int]) -> None:
    load_dotenv()
    token = os.getenv("DISCORD_TOKEN")

    client = discord.Client(intents=discord.Intents.default())
    await client.login(token)
    task = asyncio.create_task(client.connect(reconnect=True))
    while not client.is_ready():
        await asyncio.sleep(.5)
    try:
        for guild_id in guild_ids:
            guild = client.get_guild(guild_id)
            if not guild:
                print(f"Guild with ID {guild_id} not found.")
                continue

            if guild.owner != client.user:
                print(f"Cannot delete guild {guild_id} as it is not owned by the bot.")
            else:
                print(f"Deleting guild: {guild.name} (ID: {guild.id})")
                await guild.delete()
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        task.cancel()
        await client.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description="Delete specified guilds from the Discord bot.")
    parser.add_argument(
        'guild_ids',
        metavar='GUILD_ID',
        type=int,
        nargs='+',
        help='IDs of the guilds to delete'
    )
    args = parser.parse_args()
    asyncio.run(delete_guilds(args.guild_ids))
