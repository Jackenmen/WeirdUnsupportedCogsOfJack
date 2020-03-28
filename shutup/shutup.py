import functools
from typing import Callable, Optional

import discord
from discord import InvalidArgument, Message
from discord.abc import Messageable
from redbot.core import commands
from redbot.core.bot import Red


@functools.wraps(Messageable.send)
async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None):
    channel = await self._get_channel()
    state = self._state
    content = str(content) if content is not None else None
    if embed is not None:
        embed = embed.to_dict()
    if file is not None and files is not None:
        raise InvalidArgument("cannot pass both file and files parameter to send()")
    if file is not None:
        files = [file]
    if files is None:
        files = []
    attachments = []
    some_random_id = 679460791094607952
    for file in files:
        attachment = {
            "id": str(some_random_id),
            "filename": file.filename,
            "size": 3,
            "url": f"https://cdn.discordapp.com/attachments/133251234164375552/679460791094607952/{file.filename}",
            "proxy_url": f"https://media.discordapp.net/attachments/133251234164375552/679460791094607952/{file.filename}",
        }
        attachments.append(attachment)
        some_random_id += 1
        file.close()
    return Message(
        state=state,
        channel=channel,
        data={
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
            "embeds": [embed] if embed is not None else [],
            "mentions": [],
            "mention_roles": [],
            "pinned": False,
            "mention_everyone": False,
            "tts": tts,
            "timestamp": "2020-02-18T22:54:36.415000+00:00",
            "edited_timestamp": None,
            "flags": 0,
            "nonce": str(nonce),
        },
    )


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
