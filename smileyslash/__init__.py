from typing import Any, Dict

import discord
from redbot.core import app_commands, commands
from redbot.core.bot import Red

channels: Dict[int, int] = {}


class SmileySlash(commands.Cog):
    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        if message.webhook_id is None:
            channels.pop(message.channel.id, None)


@app_commands.command(description="😃" * 100)
async def smile(interaction: discord.Interaction, member: discord.Member) -> None:
    del member
    combo = channels.setdefault(interaction.channel_id, 1)
    channels[interaction.channel_id] = combo + 1
    await interaction.response.send_message("😃" * combo)


async def setup(bot: Red) -> None:
    cog = SmileySlash()
    bot.tree.add_command(smile)
    await bot.add_cog(cog)


async def teardown(bot: Red) -> None:
    bot.tree.remove_command("smile")
