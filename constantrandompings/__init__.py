from redbot.core.bot import Red

from .core import ConstantRandomPings


async def setup(bot: Red) -> None:
    cog = ConstantRandomPings(bot)
    await bot.add_cog(cog)
    await cog.initialize()
