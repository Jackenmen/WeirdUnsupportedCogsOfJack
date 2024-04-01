import asyncio
import datetime
import logging
import math
import random
import time
from typing import TYPE_CHECKING, Dict, List, Optional, TypedDict, Union

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config


MessageableGuildChannelOrThread = Union[
    discord.TextChannel,
    discord.VoiceChannel,
    discord.StageChannel,
    discord.Thread,
]

log = logging.getLogger("red.weirdjack.constantrandompings")


class GuildConfig(TypedDict):
    enabled: bool
    interval: float
    channel: Optional[int]


if TYPE_CHECKING:
    ValidInterval = datetime.timedelta
else:
    ValidInterval = commands.TimedeltaConverter(
        minimum=datetime.timedelta(seconds=300),
        maximum=datetime.timedelta(seconds=3600),
        default_unit="minutes",
    )


class ConstantRandomPings(commands.Cog):
    """
    Some dumb shit that Slime came up with.
    As a time reference, Slime's nickname at the time was Mimikyu.
    """
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, 176070082584248320, force_registration=True)
        self.config.register_guild(enabled=False, interval=300.0, channel=None)
        self.guilds: Dict[int, GuildConfig] = {}
        self.last_ping: Dict[int, float] = {}
        self.loop = asyncio.get_running_loop()
        self.handle = None

    async def initialize(self) -> None:
        self.guilds = await self.config.all_guilds()

        async def first_ping_people() -> None:
            await self.bot.wait_until_ready()
            await self.ping_people()

        asyncio.create_task(first_ping_people())

    async def cog_unload(self) -> None:
        if self.handle is not None:
            self.handle.cancel()

    async def set_guild_enabled(self, guild: discord.Guild, value: bool) -> None:
        self.guilds[guild.id]["enabled"] = value
        await self.config.guild(guild).enabled.set(value)

    async def set_guild_interval(self, guild: discord.Guild, value: float) -> None:
        self.guilds[guild.id]["interval"] = value
        await self.config.guild(guild).interval.set(value)

    async def set_guild_channel(
        self,
        guild: discord.Guild,
        channel_or_thread: Optional[MessageableGuildChannelOrThread],
    ) -> None:
        value = channel_or_thread and channel_or_thread.id
        self.guilds[guild.id]["channel"] = value
        await self.config.guild(guild).channel.set(value)

    def schedule_ping_people_task(self) -> None:
        asyncio.create_task(self.ping_people())

    async def ping_people(self) -> None:
        guilds_to_remove: List[int] = []

        current_time = time.time()
        new_task_start = math.inf
        for guild_id, guild_config in self.guilds.items():
            if not guild_config["enabled"]:
                continue
            channel_id = guild_config["channel"]
            if channel_id is None:
                continue

            last_ping = self.last_ping.get(guild_id, current_time)
            next_ping = last_ping + guild_config["interval"]
            if next_ping > current_time:
                # interval didn't pass
                new_task_start = min(next_ping, new_task_start)
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                # assume guild is unavailable but don't permanently remove its config
                guilds_to_remove.append(guild_id)
                continue

            if guild.unavailable:
                continue

            channel_or_thread = guild.get_channel_or_thread(channel_id)
            if channel_or_thread is None:
                # the channel no longer exists, unset in config
                await self.set_guild_channel(guild, None)
                continue

            member_to_ping = random.choice(guild.members)
            try:
                if not channel_or_thread.permissions_for(guild.me).send_messages:
                    raise RuntimeError
                await channel_or_thread.send(member_to_ping.mention)
            except (discord.Forbidden, RuntimeError):
                # missing send permissions, disable without unsetting the channel
                await self.set_guild_enabled(guild, False)
                continue
            except discord.HTTPException:
                # unexpected HTTP exception, ignore...
                pass

            self.last_ping[guild_id] = last_ping
            next_ping = last_ping + guild_config["interval"]
            new_task_start = min(next_ping, new_task_start)

        for guild_id in guilds_to_remove:
            del self.guilds[guild_id]

        delta = max(new_task_start - time.time(), 0.0)
        self.loop.call_later(delta, self.schedule_ping_people_task)

    @commands.guildowner()
    @commands.guild_only()
    @commands.group()
    async def constantrandompings(self, ctx: commands.Context) -> None:
        """Setup constant random pings."""

    @constantrandompings.command(name="channel")
    async def constantrandompings_enabled(
        self, ctx: commands.GuildContext, *, value: bool
    ):
        """Enable/disable constant random pings for the server."""
        await self.set_guild_enabled(ctx.guild, value)
        await ctx.send("Value updated.")

    @constantrandompings.command(name="channel")
    async def constantrandompings_interval(
        self, ctx: commands.GuildContext, *, interval: ValidInterval
    ):
        """Set ping interval (in minutes) for the server."""
        await self.set_guild_interval(ctx.guild, interval.total_seconds())
        await ctx.send("Value updated.")

    @constantrandompings.command(name="channel")
    async def constantrandompings_channel(
        self,
        ctx: commands.GuildContext,
        *,
        channel_or_thread: MessageableGuildChannelOrThread,
    ):
        """
        Set channel or thread where random pings should be sent.

        NOTE: You will still need to enable the feature by running
        the `[p]constantrandompings on` command.
        """
        if not channel_or_thread.permissions_for(ctx.me).send_messages:
            await ctx.send(f"I cannot send messages in {channel_or_thread.mention}!")
            return
        await self.set_guild_channel(ctx.guild, channel_or_thread)
        await ctx.send("Value updated.")
