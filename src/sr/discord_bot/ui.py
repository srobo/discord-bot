from typing import TYPE_CHECKING

import discord

if TYPE_CHECKING:
    from sr.discord_bot.bot import BotClient

class BlueshirtConfirmView(discord.ui.View):
    @discord.ui.button(emoji="✅", label='I have read and completed the above', style=discord.ButtonStyle.primary)
    async def confirm(
        self, interaction: discord.interactions.Interaction["BotClient"], item: discord.ui.Item[discord.ui.View],
    ) -> None:
        await interaction.user.add_roles(interaction.client.volunteer_role)
        self.stop()
