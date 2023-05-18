import inspect

from redbot.core.bot import Red

from .smileysend import SmileySend


async def setup(bot: Red) -> None:
    cog = SmileySend(bot)
    maybe_coro = bot.add_cog(cog)
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
    await cog.initialize()
