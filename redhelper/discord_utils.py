import contextlib

import discord


async def safe_delete_message(message: discord.Message) -> None:
    with contextlib.suppress(discord.NotFound):
        await message.delete()
