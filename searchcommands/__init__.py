from redbot.core.bot import Red

from .searchcommands import SearchCommands


def setup(bot: Red) -> None:
    cog = SearchCommands(bot)
    bot.add_cog(cog)
