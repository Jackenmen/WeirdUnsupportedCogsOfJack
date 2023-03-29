import inspect

from redbot.core.bot import Red

from .core import EmbedVomit


async def setup(bot: Red) -> None:
    cog = EmbedVomit(bot)
    maybe_coro = bot.add_cog(cog)
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
    else:
        await cog.cog_load()
