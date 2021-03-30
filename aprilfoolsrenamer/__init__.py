from redbot.core.bot import Red

from .core import AprilFoolsRenamer


async def setup(bot: Red) -> None:
    bot.add_cog(AprilFoolsRenamer(bot))
