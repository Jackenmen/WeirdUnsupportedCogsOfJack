import asyncio

import aiohttp
from redbot.core import commands
from redbot.core.bot import Red

from .abc import CogAndABCMeta
from .helpers import ChangelogMixin, NewContributorsMixin


class RedHelper(
    ChangelogMixin, NewContributorsMixin, commands.Cog, metaclass=CogAndABCMeta
):
    def __init__(self, bot: Red) -> None:
        super().__init__(bot)
        self.bot = bot

    def post_cog_add(self) -> None:
        super().post_cog_add()
        self.session = aiohttp.ClientSession()

    def cog_unload(self) -> None:
        super().cog_unload()
        asyncio.create_task(self.session.close())
