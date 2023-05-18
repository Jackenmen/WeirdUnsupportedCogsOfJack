import inspect

from redbot.core.bot import Red

from .choosebot import ChooseBot


async def setup(bot: Red) -> None:
    maybe_coro = bot.add_cog(ChooseBot(bot))
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
