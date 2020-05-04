from redbot.core.bot import Red

from .shutup import ShutUp


async def setup(bot: Red) -> None:
    cog = ShutUp(bot)
    bot.add_cog(cog)
    await cog.initialize()
