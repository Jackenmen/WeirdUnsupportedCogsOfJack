import functools
import random

from discord.abc import Messageable
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config


real_send = Messageable.send
OMEGA = (
    ["\N{SMILING FACE WITH OPEN MOUTH}"] * 7
    + ["\N{SMILING CAT FACE WITH OPEN MOUTH}"]
)


@functools.wraps(real_send)
async def send(self, content=None, *, tts=False, embed=None, file=None, files=None, delete_after=None, nonce=None):
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


class SmileySend(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, 176070082584248320, force_registration=True)
        self.config.register_global(toggle=False)

    async def initialize(self) -> None:
        if await self.config.toggle():
            setattr(Messageable, "send", send)

    def cog_unload(self) -> None:
        setattr(Messageable, "send", real_send)

    @commands.command()
    async def smileysend(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Messageable, "send", send)
        else:
            setattr(Messageable, "send", real_send)
        await self.config.toggle.set(toggle)
        await ctx.tick()
