from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from sr.discord_bot.bot import BotClient


class BlueshirtConfirmView(discord.ui.View):
    def __init__(self) -> None:
        super().__init__(timeout=None)

    @discord.ui.button(
        emoji="✅",
        label='I have read and completed the above',
        style=discord.ButtonStyle.primary,
        custom_id="blueshirt-confirm",
    )
    async def confirm(
        self, interaction: discord.interactions.Interaction["BotClient"], item: discord.ui.Item[discord.ui.View],
    ) -> None:
        await interaction.response.defer()
        if isinstance(interaction.user, discord.Member):
            await interaction.user.add_roles(interaction.client.volunteer_role)
