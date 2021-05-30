import functools
from contextvars import ContextVar
from copy import copy

import discord
from discord.abc import Messageable
from redbot.core import commands
from redbot.core.bot import Red


_ctx_var = ContextVar("pingafter", default=None)
real_send = Messageable.send


class PingSendInfo:
    __slots__ = ("mention", "message_count")

    def __init__(self, author: discord.Member, message_count: int = 1) -> None:
        self.mention = author.mention
        self.message_count = message_count

    def dec(self) -> bool:
        if not self.message_count:
            return False
        self.message_count -= 1
        return not self.message_count


@functools.wraps(real_send)
async def send(*args, **kwargs):
    info = _ctx_var.get()
    if info is not None and info.dec():
        await real_send(info.mention)
    return await real_send(*args, **kwargs)


class PingAfter(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot

    async def initialize(self) -> None:
        setattr(Messageable, "send", send)

    def cog_unload(self) -> None:
        setattr(Messageable, "send", real_send)

    @commands.command()
    async def pingafter(self, ctx: commands.Context, *, command: str) -> None:
        msg = copy(ctx.message)
        msg.content = f"{ctx.prefix}{command}"
        _ctx_var.set(PingSendInfo(ctx.author))
        self.bot.dispatch("message", msg)
