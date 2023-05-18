import functools
from typing import Any, List, Optional

import discord
from discord.abc import Messageable
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import pagify


real_send = Messageable.send


@functools.wraps(real_send)
async def send(
    self,
    content: Optional[str] = None,
    **kwargs: Any,
) -> discord.Message:
    content = str(content) if content is not None else None
    if content:
        current_page_length = 0
        pages = []
        lines: List[str] = []
        for line in content.splitlines():
            for longest_line in pagify(line, [" "], shorten_by=2):
                new_line = f"# {longest_line}"
                if current_page_length + len(new_line) > 2000:
                    pages.append("\n".join(lines))
                    lines.clear()
                lines.append(new_line)
        if lines:
            pages.append("\n".join(lines))
        try:
            content = pages.pop()
        except IndexError:
            content = None
        else:
            for page in pages:
                await real_send(self, page)

    return await real_send(self, content, **kwargs)


class HeaderSend(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, 176070082584248320, force_registration=True)
        self.config.register_global(toggle=False)

    async def cog_load(self) -> None:
        settings = await self.config.all()
        if settings["toggle"]:
            setattr(Messageable, "send", send)

    def cog_unload(self) -> None:
        setattr(Messageable, "send", real_send)

    @commands.is_owner()
    @commands.command()
    async def headersend(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Messageable, "send", send)
        else:
            setattr(Messageable, "send", real_send)
        await self.config.toggle.set(toggle)
        await ctx.tick()
