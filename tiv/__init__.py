import discord
from redbot.core.bot import Red
from redbot.core.errors import CogLoadError

from .tiv import _tiv_load, _tiv_unload


async def setup(bot: Red) -> None:
    if discord.version_info.major == 2:
        raise CogLoadError("Text in Voice Channels support is built into Red 3.5!")

    _tiv_load()


async def teardown(bot: Red) -> None:
    _tiv_unload()
