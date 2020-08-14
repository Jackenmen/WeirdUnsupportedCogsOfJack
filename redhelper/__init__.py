from redbot.core.bot import Red

from .redhelper import RedHelper


async def setup(bot: Red) -> None:
    cog = RedHelper(bot)
    bot.add_cog(cog)
    cog.post_cog_add()
