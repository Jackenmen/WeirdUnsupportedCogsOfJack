import asyncio
import contextlib
import functools
import itertools
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


MSG_IDS = "MSG_IDS"
CONFIG = Config.get_conf(
    None, 176070082584248320, cog_name="SmileySend", force_registration=True
)
CONFIG.register_global(toggle=False, toggle_interactive=False, toggle_replies=False)
# {CHANNEL_ID: {EMOJI_STR: {message_id: 123}}}
CONFIG.init_custom(MSG_IDS, 2)
CONFIG.register_custom(MSG_IDS, message_id=None)
CONFIG_CACHE = {}
REPLIES_ENABLED = False

real_send = Messageable.send
real_send_interactive = Context.send_interactive
OMEGA = ["\N{SMILING FACE WITH OPEN MOUTH}"] * 7 + [
    "\N{SMILING CAT FACE WITH OPEN MOUTH}"
]
SPECIAL_AUTHOR_CASES = {
    57287406247743488: ["\N{JEANS}"],
    154497072148643840: ["\N{SMILING CAT FACE WITH OPEN MOUTH}"],
    223391425302102016: ["\N{SHARK}"],
    280730525960896513: ["\N{BREAD}"],
    145519400223506432: ["\N{FIRE}"],
    119079430642466816: ["\N{EYE}\N{VARIATION SELECTOR-16}"],
}
MORE_LIST = [
    "\N{SMILING FACE WITH OPEN MOUTH}",
    "\N{SMILING CAT FACE WITH OPEN MOUTH}",
    "more",
    "moar",
]
FULL_MORE_LIST = MORE_LIST + [
    emoji for emojis in SPECIAL_AUTHOR_CASES.values() for emoji in emojis
]


if discord.version_info[:2] >= (1, 6):

    async def get_msg_ref(
        messageable: Messageable, emoji: str, *, smileysend_force_new_ref: bool = False
    ) -> discord.MessageReference:
        channel = await messageable._get_channel()
        ref_data = CONFIG_CACHE.setdefault(str(channel.id), {}).setdefault(emoji, {})

        if (
            smileysend_force_new_ref
            or (ref_msg_id := ref_data.get("message_id")) is None
        ):
            emoji_count = (2000 + 1) // (len(emoji) + 1)
            ref_msg_content = " ".join(itertools.repeat(emoji, min(50, emoji_count)))
            ref_msg = await real_send(messageable, ref_msg_content)

            ref_data["message_id"] = ref_msg_id = ref_msg.id
            scope = CONFIG.custom(MSG_IDS, str(channel.id), emoji).message_id
            await scope.set(ref_msg_id)

        return discord.MessageReference(message_id=ref_msg_id, channel_id=channel.id)

    async def send_with_msg_ref(
        messageable: Messageable,
        content=None,
        *,
        reference=None,
        smileysend_emoji,
        smileysend_force_new_ref=False,
        **kwargs,
    ) -> discord.Message:
        if reference is None and REPLIES_ENABLED:
            reference = await get_msg_ref(
                messageable,
                smileysend_emoji,
                smileysend_force_new_ref=smileysend_force_new_ref,
            )
        else:
            smileysend_force_new_ref = True
        try:
            return await real_send(messageable, content, reference=reference, **kwargs)
        except discord.HTTPException as e:
            if (
                not smileysend_force_new_ref
                and e.code == 50035
                and "In message_reference: Unknown message" in str(e)
            ):
                return await send_with_msg_ref(
                    messageable,
                    content,
                    smileysend_emoji=smileysend_emoji,
                    smileysend_force_new_ref=True,
                    **kwargs,
                )
            raise

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
        reference=None,
        mention_author=None,
    ):
        if isinstance(self, Context):
            emojis = SPECIAL_AUTHOR_CASES.get(self.author.id, OMEGA)
        else:
            emojis = OMEGA
        emoji = random.choice(emojis)
        content = str(content) if content is not None else None
        if content:
            if len(content) >= (2000 - (len(emoji) + 1) * 2):
                await real_send(self, emoji)
            else:
                content = f"{emoji} {content} {emoji}"
        else:
            content = emoji
        return await send_with_msg_ref(
            self,
            content,
            tts=tts,
            embed=embed,
            file=file,
            files=files,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
            reference=reference,
            mention_author=mention_author,
            smileysend_emoji=emoji,
        )


elif discord.version_info[:2] >= (1, 4):

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
        if isinstance(self, Context):
            emojis = SPECIAL_AUTHOR_CASES.get(self.author.id, OMEGA)
        else:
            emojis = OMEGA
        emoji = random.choice(emojis)
        content = str(content) if content is not None else None
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
        if isinstance(self, Context):
            emojis = SPECIAL_AUTHOR_CASES.get(self.author.id, OMEGA)
        else:
            emojis = OMEGA
        emoji = random.choice(emojis)
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

            omega = SPECIAL_AUTHOR_CASES.get(self.author.id, OMEGA)
            query = await self.send(
                "There {} still {} message{} remaining. "
                f"Type {random.choice(omega)} to continue."
                "".format(is_are, n_remaining, plural)
            )
            try:
                resp = await self.bot.wait_for(
                    "message",
                    check=MessagePredicate.lower_contained_in(FULL_MORE_LIST, self),
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

    async def initialize(self) -> None:
        settings = await CONFIG.all()
        if settings["toggle"]:
            setattr(Messageable, "send", send)
        if settings["toggle_interactive"]:
            setattr(Context, "send_interactive", send_interactive)
        global CONFIG_CACHE
        CONFIG_CACHE = await CONFIG.custom(MSG_IDS).all()
        global REPLIES_ENABLED
        REPLIES_ENABLED = settings["toggle_replies"]

    def cog_unload(self) -> None:
        setattr(Messageable, "send", real_send)
        setattr(Context, "send_interactive", real_send_interactive)

    @commands.is_owner()
    @commands.group(invoke_without_command=True)
    async def smileysend(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Messageable, "send", send)
        else:
            setattr(Messageable, "send", real_send)
        await CONFIG.toggle.set(toggle)
        await ctx.tick()

    @smileysend.command(name="interactive")
    async def smileysend_interactive(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Context, "send_interactive", send_interactive)
        else:
            setattr(Context, "send_interactive", real_send_interactive)
        await CONFIG.toggle_interactive.set(toggle)
        await ctx.tick()

    @smileysend.command(name="replies")
    async def smileysend_replies(self, ctx: commands.Context, toggle: bool) -> None:
        global REPLIES_ENABLED
        REPLIES_ENABLED = toggle
        await CONFIG.toggle_replies.set(toggle)
        await ctx.tick()
