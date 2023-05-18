import inspect

from redbot.core.bot import Red

from .redhelper import RedHelper


async def setup(bot: Red) -> None:
    cog = RedHelper(bot)
    maybe_coro = bot.add_cog(cog)
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
    cog.post_cog_add()
