import inspect

from redbot.core.bot import Red

from .pingafter import PingAfter


async def setup(bot: Red) -> None:
    cog = PingAfter(bot)
    maybe_coro = bot.add_cog(cog)
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
    await cog.initialize()
