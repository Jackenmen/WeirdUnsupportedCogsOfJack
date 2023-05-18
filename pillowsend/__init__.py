import inspect

from redbot.core.bot import Red

from .pillowsend import PillowSend


async def setup(bot: Red) -> None:
    cog = PillowSend(bot)
    maybe_coro = bot.add_cog(cog)
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
    await cog.initialize()
