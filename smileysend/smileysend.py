import asyncio
import contextlib
import functools
import random
from typing import List, Iterable

import discord
from discord.abc import Messageable
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import Context
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import box
from redbot.core.utils.predicates import MessagePredicate


real_send = Messageable.send
real_send_interactive = Context.send_interactive
OMEGA = (
    ["\N{SMILING FACE WITH OPEN MOUTH}"] * 7
    + ["\N{SMILING CAT FACE WITH OPEN MOUTH}"]
)
MORE_LIST = [
    "\N{SMILING FACE WITH OPEN MOUTH}",
    "\N{SMILING CAT FACE WITH OPEN MOUTH}",
    "more",
    "moar",
]


if discord.version_info[:2] >= (1, 4):
    @functools.wraps(real_send)
    async def send(
        self,
        content=None,
        *,
        tts=False,
        embed=None,
        file=None,
        files=None,
        delete_after=None,
        nonce=None,
        allowed_mentions=None,
    ):
        emoji = random.choice(OMEGA)
        if content:
            if len(content) > 1995:
                await real_send(self, emoji)
            else:
                content = f"{emoji} {content} {emoji}"
        else:
            content = emoji
        return await real_send(
            self,
            content,
            tts=tts,
            embed=embed,
            file=file,
            files=files,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
        )
else:
    @functools.wraps(real_send)
    async def send(
        self,
        content=None,
        *,
        tts=False,
        embed=None,
        file=None,
        files=None,
        delete_after=None,
        nonce=None,
    ):
        emoji = random.choice(OMEGA)
        if content:
            if len(content) > 1995:
                await real_send(self, emoji)
            else:
                content = f"{emoji} {content} {emoji}"
        else:
            content = emoji
        return await real_send(
            self,
            content,
            tts=tts,
            embed=embed,
            file=file,
            files=files,
            delete_after=delete_after,
            nonce=nonce,
        )


@functools.wraps(real_send_interactive)
async def send_interactive(
    self, messages: Iterable[str], box_lang: str = None, timeout: int = 15
) -> List[discord.Message]:
    """Send multiple messages interactively.
    The user will be prompted for whether or not they would like to view
    the next message, one at a time. They will also be notified of how
    many messages are remaining on each prompt.
    Parameters
    ----------
    messages : `iterable` of `str`
        The messages to send.
    box_lang : str
        If specified, each message will be contained within a codeblock of
        this language.
    timeout : int
        How long the user has to respond to the prompt before it times out.
        After timing out, the bot deletes its prompt message.
    """
    messages = tuple(messages)
    ret = []

    for idx, page in enumerate(messages, 1):
        if box_lang is None:
            msg = await self.send(page)
        else:
            msg = await self.send(box(page, lang=box_lang))
        ret.append(msg)
        n_remaining = len(messages) - idx
        if n_remaining > 0:
            if n_remaining == 1:
                plural = ""
                is_are = "is"
            else:
                plural = "s"
                is_are = "are"
            query = await self.send(
                "There {} still {} message{} remaining. "
                f"Type {random.choice(OMEGA)} to continue."
                "".format(is_are, n_remaining, plural)
            )
            try:
                resp = await self.bot.wait_for(
                    "message",
                    check=MessagePredicate.lower_contained_in(MORE_LIST, self),
                    timeout=timeout,
                )
            except asyncio.TimeoutError:
                with contextlib.suppress(discord.HTTPException):
                    await query.delete()
                break
            else:
                try:
                    await self.channel.delete_messages((query, resp))
                except (discord.HTTPException, AttributeError):
                    # In case the bot can't delete other users' messages,
                    # or is not a bot account
                    # or channel is a DM
                    with contextlib.suppress(discord.HTTPException):
                        await query.delete()
    return ret


class SmileySend(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, 176070082584248320, force_registration=True)
        self.config.register_global(toggle=False, toggle_interactive=False)

    async def initialize(self) -> None:
        settings = await self.config.all()
        if await settings["toggle"]:
            setattr(Messageable, "send", send)
        if await settings["toggle_interactive"]:
            setattr(Messageable, "send", send)

    def cog_unload(self) -> None:
        setattr(Messageable, "send", real_send)
        setattr(Context, "send_interactive", real_send_interactive)

    @commands.group()
    async def smileysend(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Messageable, "send", send)
        else:
            setattr(Messageable, "send", real_send)
        await self.config.toggle.set(toggle)
        await ctx.tick()

    @commands.command(name="interactive")
    async def smileysend_interactive(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Context, "send_interactive", send_interactive)
        else:
            setattr(Context, "send_interactive", real_send_interactive)
        await self.config.toggle_interactive.set(toggle)
        await ctx.tick()
