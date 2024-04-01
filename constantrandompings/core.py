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
from redbot.core.utils.chat_formatting import humanize_timedelta


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
        self.task: Optional[asyncio.Task] = None
        self.handle: Optional[asyncio.TimerHandle] = None
        self._schedule_next = True

    async def initialize(self) -> None:
        self.guilds = await self.config.all_guilds()

        async def schedule_after_ready() -> None:
            await self.bot.wait_until_ready()
            self.schedule_ping_people_task()

        asyncio.create_task(schedule_after_ready())

    async def cog_unload(self) -> None:
        if self.task is not None:
            self.task.cancel()
            self.task = None
        if self.handle is not None:
            self.handle.cancel()
            self.handle = None

    async def _ensure_config_for_guild(self, guild: discord.Guild) -> None:
        if guild.id in self.guilds:
            return
        self.guilds[guild.id] = await self.config.guild(guild).all()

    async def get_guild_config(self, guild: discord.Guild) -> GuildConfig:
        guild_config = self.guilds.get(guild.id)
        if guild_config is not None:
            return guild_config
        return await self.config.guild(guild).all()

    async def set_guild_enabled(self, guild: discord.Guild, value: bool) -> None:
        await self._ensure_config_for_guild(guild)
        self.guilds[guild.id]["enabled"] = value
        await self.config.guild(guild).enabled.set(value)

    async def set_guild_interval(self, guild: discord.Guild, value: float) -> None:
        await self._ensure_config_for_guild(guild)
        self.guilds[guild.id]["interval"] = value
        await self.config.guild(guild).interval.set(value)

    async def set_guild_channel(
        self,
        guild: discord.Guild,
        channel_or_thread: Optional[MessageableGuildChannelOrThread],
    ) -> None:
        await self._ensure_config_for_guild(guild)
        value = channel_or_thread and channel_or_thread.id
        self.guilds[guild.id]["channel"] = value
        await self.config.guild(guild).channel.set(value)

    async def reschedule_ping_people_task(self) -> None:
        log.info("Settings changed, rescheduling task...")
        if self.task is not None:
            # task is currently running, disable scheduling and wait
            log.info(
                "Task is already running, waiting for reschedule until it finishes."
            )
            self._schedule_next = False
            await self.task
            self._schedule_next = True

        if self.handle is not None:
            self.handle.cancel()
        self.schedule_ping_people_task()

    def schedule_ping_people_task(self) -> None:
        def _done_callback(task: asyncio.Task) -> None:
            try:
                exc = task.exception()
            except asyncio.CancelledError:
                pass
            else:
                if exc is None:
                    return
                log.error(
                    "An unexpected error occurred in ping people task.",
                    exc_info=exc,
                )

        self.task = asyncio.create_task(self.ping_people())
        self.task.add_done_callback(_done_callback)

    async def ping_people(self) -> None:
        log.debug("Starting ping people task...")
        self.handle = None
        guilds_to_remove: List[int] = []

        current_time = time.time()
        new_task_start = math.inf
        for guild_id, guild_config in self.guilds.items():
            if not guild_config["enabled"]:
                continue
            channel_id = guild_config["channel"]
            if channel_id is None:
                continue

            last_ping = self.last_ping.setdefault(guild_id, current_time)
            next_ping = last_ping + guild_config["interval"]
            if next_ping > current_time:
                # interval didn't pass
                new_task_start = min(next_ping, new_task_start)
                log.debug(
                    "Interval for guild with ID %s did not pass yet, skipping...",
                    guild_id,
                )
                continue

            guild = self.bot.get_guild(guild_id)
            if guild is None:
                # assume guild is unavailable but don't permanently remove its config
                guilds_to_remove.append(guild_id)
                log.warning(
                    "Could not find guild with ID %s, ignoring until cog reload...",
                    guild_id,
                )
                continue

            if guild.unavailable:
                log.warning("Guild with ID %s is unavailable, skipping...", guild_id)
                continue

            channel_or_thread = guild.get_channel_or_thread(channel_id)
            if channel_or_thread is None:
                # the channel no longer exists, unset in config
                await self.set_guild_channel(guild, None)
                log.warning(
                    "Channel or thread with ID %s no longer exists,"
                    " unsetting the value in configuration of guild with ID %s.",
                    channel_id,
                    guild_id,
                )
                continue

            # we can ping new users into the thread
            channel = (
                channel_or_thread.parent
                if isinstance(channel_or_thread, discord.Thread)
                else channel_or_thread
            )
            members = [m for m in guild.members if channel.permissions_for(channel)]
            member_to_ping = random.choice(members)
            try:
                if not channel_or_thread.permissions_for(guild.me).send_messages:
                    raise RuntimeError
                await channel_or_thread.send(member_to_ping.mention)
            except (discord.Forbidden, RuntimeError):
                # missing send permissions, disable without unsetting the channel
                await self.set_guild_enabled(guild, False)
                log.warning(
                    "Missing send permissions in channel or thread with ID %s,"
                    " disabled constant random pings for guild with ID %s.",
                    channel_id,
                    guild_id,
                )
                continue
            except discord.HTTPException as exc:
                # unexpected HTTP exception, ignore...
                log.warning(
                    "Could not send message in channel or thread with ID %s"
                    " (from guild with ID %s) due to HTTP exception.",
                    channel_id,
                    guild_id,
                    exc_info=exc,
                )

            last_ping = self.last_ping[guild_id] = time.time()
            next_ping = last_ping + guild_config["interval"]
            new_task_start = min(next_ping, new_task_start)

        for guild_id in guilds_to_remove:
            del self.guilds[guild_id]

        log.debug("Ping people task finished.")
        if not self._schedule_next or new_task_start is math.inf:
            log.info("No guild requires scheduling a new task, returning...")
            # nothing needs to happen in the future
            return
        delta = max(new_task_start - time.time(), 0.0) + 5.0
        log.info("Next task will be started in %s seconds.", delta)
        self.loop.call_later(delta, self.schedule_ping_people_task)

    @commands.guildowner()
    @commands.guild_only()
    @commands.group()
    async def constantrandompings(self, ctx: commands.Context) -> None:
        """Setup constant random pings."""

    @constantrandompings.command(name="settings", aliases=["showsettings"])
    async def constantrandompings_settings(self, ctx: commands.GuildContext) -> None:
        """Show settings for the server."""
        guild_config = await self.get_guild_config(ctx.guild)
        status = "Enabled" if guild_config["enabled"] else "Disabled"
        channel_or_thread = ctx.guild.get_channel_or_thread(guild_config["channel"])
        channel_mention = (
            channel_or_thread and channel_or_thread.mention
            or f"Unknown {guild_config['channel']}"
        )
        interval = humanize_timedelta(seconds=guild_config["interval"])
        await ctx.send(
            f"**Settings**\n\n"
            f"Status: {status}\n"
            f"Channel: {channel_mention}\n"
            f"Interval: {interval}"
        )

    @constantrandompings.command(name="enable")
    async def constantrandompings_enable(self, ctx: commands.GuildContext) -> None:
        """Enable constant random pings for the server."""
        await self.set_guild_enabled(ctx.guild, True)
        await ctx.send("Constant random pings enabled.")
        await self.reschedule_ping_people_task()

    @constantrandompings.command(name="disable")
    async def constantrandompings_disable(self, ctx: commands.GuildContext) -> None:
        """Disable constant random pings for the server."""
        await self.set_guild_enabled(ctx.guild, False)
        await ctx.send("Constant random pings disabled.")
        await self.reschedule_ping_people_task()

    @constantrandompings.command(name="interval")
    async def constantrandompings_interval(
        self, ctx: commands.GuildContext, *, interval: ValidInterval
    ) -> None:
        """Set ping interval (in minutes) for the server."""
        await self.set_guild_interval(ctx.guild, interval.total_seconds())
        await ctx.send("Value updated.")
        await self.reschedule_ping_people_task()

    @constantrandompings.command(name="channel")
    async def constantrandompings_channel(
        self,
        ctx: commands.GuildContext,
        *,
        channel_or_thread: MessageableGuildChannelOrThread,
    ) -> None:
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
        await self.reschedule_ping_people_task()
