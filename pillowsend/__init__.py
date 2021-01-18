from redbot.core.bot import Red

from .pillowsend import PillowSend


async def setup(bot: Red) -> None:
    cog = PillowSend(bot)
    bot.add_cog(cog)
    await cog.initialize()
