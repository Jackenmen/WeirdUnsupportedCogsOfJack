from redbot.core.bot import Red

from .pingafter import PingAfter


async def setup(bot: Red) -> None:
    cog = PingAfter(bot)
    bot.add_cog(cog)
    await cog.initialize()
