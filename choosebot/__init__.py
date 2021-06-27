from redbot.core.bot import Red

from .choosebot import ChooseBot


async def setup(bot: Red) -> None:
    bot.add_cog(ChooseBot(bot))
