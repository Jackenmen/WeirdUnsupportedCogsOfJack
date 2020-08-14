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
