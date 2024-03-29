import functools
import random
import re
from typing import Any, List, Optional

import discord
from discord.abc import Messageable
from redbot import VersionInfo, version_info as red_version_info
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import pagify


if red_version_info >= VersionInfo.from_str("3.5.0"):
    from typing import Literal
else:
    from redbot.core.commands import Literal


CODE_BLOCK_RE = re.compile(r"```[\w.+\-]+(?!```).*?```|```\n*.+?```", re.DOTALL)
real_send = Messageable.send
SKIP_CODE_BLOCKS = True
HEADER_SIZE: Optional[int] = 1


class ContentPart:
    def __init__(self, content: str, *, can_split: bool = True) -> None:
        self.content = content
        self.can_split = can_split


@functools.wraps(real_send)
async def send(
    self,
    content: Optional[str] = None,
    **kwargs: Any,
) -> discord.Message:
    content = str(content) if content is not None else None
    if content:
        content_parts = []
        if SKIP_CODE_BLOCKS:
            start = 0
            end = 0
            for match in CODE_BLOCK_RE.finditer(content):
                end = match.start()
                if end != start:
                    content_parts.append(ContentPart(content[start:end]))
                if content_parts and not content_parts[-1].can_split:
                    content_parts[-1].content += match.group(0)
                else:
                    content_parts.append(ContentPart(match.group(0), can_split=False))
                start = match.end()
            if start != len(content):
                content_parts.append(ContentPart(content[start:]))
        else:
            content_parts.append(ContentPart(content))
        current_page_length = 0
        pages = []
        lines: List[str] = []
        for part in content_parts:
            if not part.can_split:
                new_line = part.content
                if current_page_length + len(new_line) > 2001:
                    current_page_length = 0
                    pages.append("\n".join(lines))
                    lines.clear()
                current_page_length += len(new_line) + 1
                lines.append(new_line)
                continue

            for line in part.content.splitlines():
                pagifier = pagify(line, [" "], shorten_by=0)
                header_size = (
                    random.randint(1, 3) if HEADER_SIZE is None else HEADER_SIZE
                )
                pagifier._page_length = 1999 - header_size
                for longest_line in pagifier:
                    new_line = f"{'#'*header_size} {longest_line}"
                    if current_page_length + len(new_line) > 2001:
                        current_page_length = 0
                        pages.append("\n".join(lines))
                        lines.clear()
                    current_page_length += len(new_line) + 1
                    lines.append(new_line)
                    header_size = (
                        random.randint(1, 3) if HEADER_SIZE is None else HEADER_SIZE
                    )
                    pagifier._page_length = 1999 - header_size  # DEP-WARN
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
        self.config.register_global(
            toggle=False,
            skip_code_blocks=True,
            header_size=1,
        )

    async def cog_load(self) -> None:
        settings = await self.config.all()
        if settings["toggle"]:
            setattr(Messageable, "send", send)
        global SKIP_CODE_BLOCKS
        SKIP_CODE_BLOCKS = settings["skip_code_blocks"]
        global HEADER_SIZE
        HEADER_SIZE = settings["header_size"]

    def cog_unload(self) -> None:
        setattr(Messageable, "send", real_send)

    @commands.is_owner()
    @commands.group(invoke_without_command=True)
    async def headersend(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Messageable, "send", send)
        else:
            setattr(Messageable, "send", real_send)
        await self.config.toggle.set(toggle)
        await ctx.tick()

    @commands.is_owner()
    @headersend.command("headersize")
    async def headersend_headersize(
        self, ctx: commands.Context, size: Literal["1", "2", "3", "random"]
    ) -> None:
        """
        The size of the header that should be used.

        You can choose between "1" (large - `#`), "2" (medium - `##`), "3" (small - `###`),
        and "random" (large, medium, or small chosen at random for each message line).
        """
        global HEADER_SIZE
        HEADER_SIZE = int(size) if size != "random" else None
        await self.config.header_size.set(HEADER_SIZE)
        await ctx.tick()

    @commands.is_owner()
    @headersend.command("skipcodeblocks")
    async def headersend_skipcodeblocks(
        self, ctx: commands.Context, toggle: bool
    ) -> None:
        global SKIP_CODE_BLOCKS
        SKIP_CODE_BLOCKS = toggle
        await self.config.skip_code_blocks.set(toggle)
        await ctx.tick()
