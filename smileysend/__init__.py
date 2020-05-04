from redbot.core.bot import Red

from .smileysend import SmileySend


async def setup(bot: Red) -> None:
    cog = SmileySend(bot)
    bot.add_cog(cog)
    await cog.initialize()
