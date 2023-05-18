import inspect

from redbot.core.bot import Red

from .searchcommands import SearchCommands


async def setup(bot: Red) -> None:
    cog = SearchCommands(bot)
    maybe_coro = bot.add_cog(cog)
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
