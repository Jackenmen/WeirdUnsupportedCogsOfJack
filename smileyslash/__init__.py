from typing import Any, Dict

import discord
from redbot.core import commands
from redbot.core.bot import Red

API_URL = "https://discord.com/api/v8"


class SmileySlash(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.channels: Dict[int, int] = {}

    async def initialize(self) -> None:
        setattr(
            self.bot._connection,
            "parse_interaction_create",
            self.parse_interaction_create,
        )
        self.bot._connection.parsers[
            "INTERACTION_CREATE"
        ] = self.parse_interaction_create

    def cog_unload(self) -> None:
        delattr(self.bot._connection, "parse_interaction_create")
        self.bot._connection.parsers.pop("INTERACTION_CREATE", None)

    def parse_interaction_create(self, data: Dict[str, Any]) -> None:
        self.bot.dispatch("interaction_create", data)

    @commands.Cog.listener()
    async def on_interaction_create(self, data: Dict[str, Any]) -> None:
        channel_id = data["channel_id"]
        combo = self.channels.setdefault(channel_id, 1)
        async with self.bot.http._HTTPClient__session.post(
            f"{API_URL}/interactions/{data['id']}/{data['token']}/callback",
            json={
                "type": 4,
                "data": {
                    "content": "😃" * combo,
                },
            },
        ):
            pass
        self.channels[channel_id] = combo + 1

    @commands.Cog.listener()
    async def on_message(self, message: discord.Message) -> None:
        self.channels.pop(message.channel.id, None)


async def setup(bot: Red) -> None:
    cog = SmileySlash()
    bot.add_cog(cog)
    await cog.initialize()
