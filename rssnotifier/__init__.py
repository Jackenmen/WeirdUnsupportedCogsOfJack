from redbot.core.bot import Red

from .rssnotifier import RSSNotifier


def setup(bot: Red) -> None:
    bot.add_cog(RSSNotifier(bot))
