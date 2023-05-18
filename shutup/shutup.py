import functools
from typing import Callable, Optional

import discord
from discord import InvalidArgument, Message
from discord.abc import Messageable
from redbot.core import commands
from redbot.core.bot import Red


@functools.wraps(Messageable.send)
async def send(
    self,
    content=None,
    *,
    tts=False,
    embed=None,
    embeds=None,
    file=None,
    files=None,
    stickers=None,
    delete_after=None,
    nonce=None,
    allowed_mentions=None,
    reference=None,
    mention_author=None,
    view=None,
    suppress_embeds=False,
    silent=False,
):
    channel = await self._get_channel()
    state = self._state
    content = str(content) if content is not None else None
    if file is not None and files is not None:
        raise InvalidArgument("cannot pass both file and files parameter to send()")
    if embed is not None and embeds is not None:
        raise InvalidArgument("cannot pass both embed and embeds parameter to send()")
    if file is not None:
        files = [file]
    if files is None:
        files = []
    if embed is not None:
        embeds = [embed]
    if embeds:
        embeds = [embed.to_dict() for embed in embeds]
    sticker_items = [
        {"id": sticker.id, "name": sticker.name, "format_type": sticker.format.value}
        for sticker in (stickers or [])
    ]
    attachments = []
    some_random_id = 679460791094607952
    for file in files:
        attachment = {
            "id": str(some_random_id),
            "filename": file.filename,
            "description": file.description or None,
            "size": 3,
            "url": f"https://cdn.discordapp.com/attachments/133251234164375552/679460791094607952/{file.filename}",
            "proxy_url": f"https://media.discordapp.net/attachments/133251234164375552/679460791094607952/{file.filename}",
        }
        attachments.append(attachment)
        some_random_id += 1
        file.close()
    data = {
        "id": "679460791291871240",
        "type": 0,
        "content": content,
        "channel_id": str(channel.id),
        "author": {
            "id": str(state.user.id),
            "username": state.user.name,
            "avatar": None,
            "discriminator": state.user.discriminator,
            "bot": state.user.bot,
        },
        "attachments": attachments,
        "embeds": embeds if embeds else [],
        "sticker_items": sticker_items,
        "mentions": [],
        "mention_roles": [],
        "pinned": False,
        "mention_everyone": False,
        "tts": tts,
        "timestamp": "2020-02-18T22:54:36.415000+00:00",
        "edited_timestamp": None,
        "flags": 0,
        "nonce": str(nonce),
    }
    if reference is not None:
        try:
            data["message_reference"] = reference.to_message_reference_dict()
        except AttributeError:
            raise TypeError(
                "reference parameter must be Message, MessageReference, or PartialMessage"
            ) from None
    if view is not None:
        data["components"] = view.to_components()
    if suppress_embeds or silent:
        flags = discord.MessageFlags()
        flags.suppress_embeds = suppress_embeds
        flags.suppress_notifications = silent
        data["flags"] = flags.value
    return Message(state=state, channel=channel, data=data)


class ShutUp(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self._old_send: Optional[Callable] = None

    @commands.command()
    async def shutup(self, ctx: commands.Context) -> None:
        if ctx.channel.permissions_for(ctx.me).add_reactions:
            try:
                await ctx.message.add_reaction("\N{ZIPPER-MOUTH FACE}")
            except discord.HTTPException:
                await ctx.send("K, I'll shut up forever. Sorry.")
        else:
            await ctx.send("K, I'll shut up forever. Sorry.")
        self._old_send = Messageable.send
        setattr(Messageable, "send", send)

    @commands.command()
    async def unshutup(self, ctx: commands.Context) -> None:
        if self._old_send is None:
            await ctx.send("I didn't shut up, but sure, I can talk...")
            return
        setattr(Messageable, "send", self._old_send)
        self._old_send = None
        await ctx.send("K, I'm back babe. Don't you ever shut me up again plz")
