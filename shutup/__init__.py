from redbot.core.bot import Red

from .shutup import ShutUp


async def setup(bot: Red) -> None:
    bot.add_cog(ShutUp(bot))
