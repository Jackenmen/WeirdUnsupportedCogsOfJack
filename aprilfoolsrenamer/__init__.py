import inspect

from redbot.core.bot import Red

from .core import AprilFoolsRenamer


async def setup(bot: Red) -> None:
    maybe_coro = bot.add_cog(AprilFoolsRenamer(bot))
    if inspect.isawaitable(maybe_coro):
        await maybe_coro
