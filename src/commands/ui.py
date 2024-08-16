from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from src.bot import BotClient


class TeamDeleteConfirm(discord.ui.View):
    def __init__(self, guild: discord.Guild, tla: str):
        super().__init__()
        self.guild: discord.Guild = guild
        self.tla: str = tla
        self.value: bool = False

    @discord.ui.button(label='Delete', style=discord.ButtonStyle.red)
    async def confirm(self, interaction: discord.interactions.Interaction["BotClient"], item: discord.ui.Item[discord.ui.View]) -> None:
        self.value = True
        self.stop()

    @discord.ui.button(label='Cancel', style=discord.ButtonStyle.grey)
    async def cancel(self, interaction: discord.interactions.Interaction["BotClient"], item: discord.ui.Item[discord.ui.View]) -> None:
        await interaction.response.defer(ephemeral=True)
        self.stop()
