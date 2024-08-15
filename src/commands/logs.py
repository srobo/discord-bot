import logging
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, IO, Tuple, List, cast
from zipfile import BadZipFile, ZipFile, is_zipfile, ZIP_DEFLATED

import aiohttp
import discord
from discord import app_commands

from src.constants import TEAM_CHANNEL_PREFIX

if TYPE_CHECKING:
    from src.bot import BotClient


class AnimationHandling(Enum):
    none = 0
    team = 1
    separate = 2


logger = logging.getLogger("logs")
logger.setLevel(logging.INFO)
handler = logging.StreamHandler(sys.stdout)
handler.setLevel(logging.INFO)
logger.addHandler(handler)

# Don't post to team channels and force the guild used so testing can you DMs
DISCORD_TESTING = bool(os.getenv('DISCORD_TESTING'))
# Just post all messages to calling channel, allow DMs
DISCORD_DEBUG = bool(os.getenv('DISCORD_DEBUG'))
if DISCORD_TESTING or DISCORD_DEBUG:
    # print all debug messages
    logger.setLevel(logging.DEBUG)
    handler.setLevel(logging.DEBUG)


async def log_and_reply(ctx: discord.interactions.Interaction["BotClient"], error_str: str) -> None:
    logger.error(error_str)
    await ctx.followup.send(content=error_str, ephemeral=True)


async def get_channel(
    ctx: discord.interactions.Interaction["BotClient"],
    channel_name: str,
) -> discord.TextChannel | None:
    channel_name = channel_name.lower()  # all text/voice channels are lowercase
    guild = ctx.guild
    if DISCORD_DEBUG:
        # Always return calling channel
        return cast(discord.TextChannel, ctx.channel)
    if DISCORD_TESTING:
        guild_id = os.getenv('DISCORD_GUILD')
        if guild_id is None:
            guild = None
        else:
            guild = ctx.client.get_guild(int(guild_id))

    # get team's channel by name
    if guild is None:
        raise app_commands.NoPrivateMessage
    channel = discord.utils.get(
        guild.channels,
        name=channel_name,
    )

    if not channel:
        await log_and_reply(
            ctx,
            f"# Channel {channel_name} not found, unable to send message",
        )
        return None
    elif not isinstance(channel, discord.TextChannel):
        await log_and_reply(
            ctx,
            f"# {channel.name} is not a text channel, unable to send message",
        )
        return None

    return channel


async def get_team_channel(
    ctx: discord.interactions.Interaction["BotClient"],
    archive_name: str,
    zip_name: str,
) -> Tuple[str, discord.TextChannel | None]:
    # extract team name from filename
    tla_search = re.match(TEAM_CHANNEL_PREFIX + r'(.*?)[-.]', archive_name)
    if not isinstance(tla_search, re.Match):
        await log_and_reply(
            ctx,
            f"# Failed to extract a TLA from {archive_name} in {zip_name}",
        )
        return '', None

    tla = tla_search.group(1)
    channel = await get_channel(ctx, f"{TEAM_CHANNEL_PREFIX}{tla}")

    return tla, channel


def pre_test_zipfile(archive_name: str, zip_name: str) -> bool:
    if not archive_name.lower().endswith('.zip'):  # skip non-zips
        logger.debug(f"{archive_name} from {zip_name} is not a ZIP, skipping")
        return False

    # skip files not starting with TEAM_CHANNEL_PREFIX
    if not archive_name.lower().startswith(TEAM_CHANNEL_PREFIX):
        logger.debug(
            f"{archive_name} from {zip_name} "
            f"doesn't start with {TEAM_CHANNEL_PREFIX}, skipping",
        )
        return False
    return True


def match_animation_files(log_name: str, animation_dir: Path) -> List[Path]:
    match_num_search = re.search(r'match-([0-9]+)', log_name)
    if not isinstance(match_num_search, re.Match):
        logger.warning(f'Invalid match name: {log_name}')
        return []
    match_num = match_num_search[1]
    logger.debug(f"Fetching animation files for match {match_num}")
    match_files = animation_dir.glob(f'match-{match_num}.*')
    return [data_file for data_file in match_files if data_file.suffix != '.mp4']


def insert_match_files(archive: Path, animation_dir: Path) -> None:
    # append animations to archive
    with ZipFile(archive, 'a', compression=ZIP_DEFLATED) as zipfile:
        for log_name in zipfile.namelist():
            if not log_name.endswith('.txt'):
                continue

            for animation_file in match_animation_files(log_name, animation_dir):
                zipfile.write(animation_file.resolve(), animation_file.name)

        # add textures subtree
        for texture in (animation_dir / 'textures').glob('**/*'):
            zipfile.write(
                texture.resolve(),
                texture.relative_to(animation_dir),
            )


async def send_file(
    ctx: discord.interactions.Interaction["BotClient"],
    channel: discord.TextChannel,
    archive: Path,
    event_name: str,
    msg_str: str = "Here are your logs",
    logging_str: str = "Uploaded logs",
) -> bool:
    try:
        if DISCORD_TESTING:  # don't actually send message in testing
            if (archive.stat().st_size / 1000 ** 2) > 8:
                # discord.HTTPException requires aiohttp.ClientResponse
                await log_and_reply(
                    ctx,
                    f"# {archive.name} was too large to upload at "
                    f"{archive.stat().st_size / 1000 ** 2 :.3f} MiB",
                )
                return False
        else:
            await channel.send(
                content=f"{msg_str} from {event_name if event_name else 'today'}",
                file=discord.File(str(archive)),
            )
        logger.debug(
            f"{logging_str} from {event_name if event_name else 'today'}",
        )
    except discord.HTTPException as e:  # handle file size issues
        if e.status == 413:
            await log_and_reply(
                ctx,
                f"# {archive.name} was too large to upload at "
                f"{archive.stat().st_size / 1000 ** 2 :.3f} MiB",
            )
            return False
        else:
            raise e
    return True


def extract_animations(zipfile: ZipFile, tmpdir: Path, fully_extract: bool) -> bool:
    animation_files = [
        name for name in zipfile.namelist()
        if name.split('/')[-1].startswith('animations')
           and name.endswith('.zip')
    ]

    if not animation_files:
        return False

    try:
        zipfile.extract(animation_files[0], path=tmpdir)
    except BadZipFile:
        logger.warning("The animations zip was corrupt")
        return False

    # give the animations archive + folder if fixed name
    shutil.move(str(tmpdir / animation_files[0]), str(tmpdir / 'animations.zip'))

    if fully_extract:
        with ZipFile(tmpdir / 'animations.zip') as animation_zip:
            (tmpdir / 'animations').mkdir()
            animation_zip.extractall(tmpdir / 'animations')
            logger.debug("Extracting animations.zip")
    return True


async def logs_upload(
    ctx: discord.interactions.Interaction["BotClient"],
    file: IO[bytes],
    zip_name: str,
    event_name: str,
    team_animation: AnimationHandling,  # None = don't upload animations
) -> None:
    animations_found = False
    try:
        with tempfile.TemporaryDirectory() as tmpdir_name:
            tmpdir = Path(tmpdir_name)
            completed_tlas = []

            with ZipFile(file) as zipfile:
                if team_animation != AnimationHandling.none:
                    animations_found = extract_animations(zipfile, tmpdir, team_animation == AnimationHandling.team)

                    if not animations_found:
                        await log_and_reply(ctx, "animations Zip file is missing")

                for archive_name in zipfile.namelist():
                    if not pre_test_zipfile(archive_name, zip_name):
                        continue

                    zipfile.extract(archive_name, path=tmpdir)

                    if not is_zipfile(tmpdir / archive_name):  # test file is a valid zip
                        await log_and_reply(
                            ctx,
                            f"# {archive_name} from {zip_name} is not a valid ZIP file",
                        )
                        # The file will be removed with the temporary directory
                        continue

                    if team_animation and animations_found:
                        insert_match_files(tmpdir / archive_name, tmpdir / 'animations')

                    # get team's channel
                    tla, channel = await get_team_channel(ctx, archive_name, zip_name)
                    if not channel:
                        continue

                    # upload to team channel with message
                    if not await send_file(
                        ctx,
                        channel,
                        tmpdir / archive_name,
                        event_name,
                        logging_str=f"Uploaded logs for {tla}",
                    ):
                        # try again without animations
                        # TODO test this clause in unit testing
                        if team_animation:
                            # extract original archive, modified version is overwritten
                            zipfile.extract(archive_name, path=tmpdir)

                            if await send_file(  # retry with original archive
                                ctx,
                                channel,
                                tmpdir / archive_name,
                                event_name,
                                logging_str=f"Uploaded only logs for {tla}",
                            ):
                                await log_and_reply(
                                    ctx,
                                    f"Only able to upload logs for {tla}, "
                                    "no animations were served",
                                )

                        continue

                    completed_tlas.append(tla)

            if team_animation is False and animations_found:
                common_channel = await get_channel(ctx, "general")
                # upload animations.zip to common channel
                if common_channel:
                    await send_file(
                        ctx,
                        common_channel,
                        tmpdir / 'animations.zip',
                        event_name,
                        msg_str="Here are the animation files",
                        logging_str="Uploaded animations",
                    )

            await ctx.followup.send(content=
                                    f"Successfully uploaded logs to {len(completed_tlas)} teams: "
                                    f"{', '.join(completed_tlas)}",
                                    )
    except BadZipFile:
        await log_and_reply(ctx, f"# {zip_name} is not a valid ZIP file")


@app_commands.command(
    name="logs",
    description="Get combined logs archive from URL for distribution to teams, avoids Discord's size limit",
)
@app_commands.describe(
    url="URL to a zip of logs",
    animations="How the animation files will be handled",
    event_name="Optionally set the event name used in the bot's message to teams",
)
async def logs(
    interaction: discord.interactions.Interaction['BotClient'],
    url: str,
    animations: AnimationHandling = AnimationHandling.none,
    event_name: str | None = None,
) -> None:
    logger.info(f"{interaction.user.name} started downloading logs from {url}")

    with tempfile.TemporaryFile(suffix='.zip') as zipfile:
        if url.endswith('.zip'):
            filename = url.split("/")[-1]
        else:
            filename = f"logs_upload-{datetime.date.today()}.zip"

        await interaction.response.defer(thinking=True)  # provides feedback that the bot is processing
        # download zip, using aiohttp
        async with aiohttp.ClientSession() as session:
            resp = await session.get(url)

            if resp.status >= 400:
                logger.error(
                    f"Download from {url} failed with error "
                    f"{resp.status}, {resp.reason}",
                )
                await interaction.followup.send(content="Zip file failed to download")
                return

            zipfile_data = await resp.read()

            zipfile.write(zipfile_data)

        # start processing from beginning of the file
        zipfile.seek(0)

        await logs_upload(
            interaction,
            zipfile,
            filename,
            event_name,
            animations,
        )
