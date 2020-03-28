from redbot.core.bot import Red

from .redhelper import RedHelper


async def setup(bot: Red) -> None:
    bot.add_cog(RedHelper(bot))
