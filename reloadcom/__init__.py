import inspect

from redbot.core.bot import Red

from .reloadcom import ReloadCom


async def setup(bot: Red) -> None:
    cog = ReloadCom(bot)
    maybe_coro = bot.add_cog(cog)
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
