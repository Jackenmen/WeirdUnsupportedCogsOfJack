from typing import Any, Dict

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import NoParseOptional as Optional
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import inline, pagify

FEED = "FEED"


class RSSNotifier(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, 176070082584248320, force_registration=True)
        # {CHANNEL_ID: {FEED_NAME: {...}}}
        self.config.init_custom(FEED, 2)
        self.config.register_custom(FEED, user_mentions=[])

    @commands.guild_only()
    @commands.group()
    async def rssnotifier(self, ctx: commands.Context) -> None:
        """RSSNotifier settings."""

    @rssnotifier.command(name="optin")
    async def rssnotifier_optin(
        self,
        ctx: commands.GuildContext,
        feed_name: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Opt-in receiving notifications for the given feed name."""
        user_id = ctx.author.id
        if channel is None:
            channel = ctx.channel
        scope = self.config.custom(FEED, channel.id, feed_name).user_mentions
        async with scope.get_lock():
            user_mentions = await scope()
            if user_id in user_mentions:
                await ctx.send(
                    "You already opted in receiving notifications for this feed."
                )
                return
            user_mentions.append(user_id)
            await scope.set(user_mentions)
            await ctx.send(
                "You will now receive notifications"
                f" for feed {inline(feed_name)} in {channel.mention}"
            )

    @rssnotifier.command(name="optout")
    async def rssnotifier_optout(
        self,
        ctx: commands.GuildContext,
        feed_name: str,
        channel: Optional[discord.TextChannel] = None,
    ) -> None:
        """Opt-out of receiving notifications for the given feed name."""
        user_id = ctx.author.id
        if channel is None:
            channel = ctx.channel
        scope = self.config.custom(FEED, channel.id, feed_name).user_mentions
        async with scope.get_lock():
            user_mentions = await scope()
            if user_id not in user_mentions:
                await ctx.send(
                    "You weren't registered to notifications for this feed."
                )
                return
            user_mentions.remove(user_id)
            await scope.set(user_mentions)
            await ctx.send(
                "You will no longer receive notifications"
                f" for feed {inline(feed_name)} in {channel.mention}"
            )

    @commands.Cog.listener()
    async def on_aikaternacogs_rss_message(
        self,
        *,
        channel: discord.TextChannel,
        feed_data: Dict[str, Any],
        force: bool,
        **_kwargs: Any,
    ) -> None:
        feed_name = feed_data["name"]
        scope = self.config.custom(FEED, channel.id, feed_name).user_mentions
        user_mentions = await scope()
        if not user_mentions:
            return
        if force:
            await channel.send(
                "THIS IS A FORCED UPDATE. RSSNotifier will not notify users about it."
            )
            return
        for page in pagify(" ".join(map("<@{}>".format, user_mentions)), delims=[" "]):
            await channel.send(page)
