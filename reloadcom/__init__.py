from redbot.core.bot import Red

from .reloadcom import ReloadCom


async def setup(bot: Red) -> None:
    cog = ReloadCom(bot)
    bot.add_cog(cog)
