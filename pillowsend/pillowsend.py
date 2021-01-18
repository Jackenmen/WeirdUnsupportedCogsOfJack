import asyncio
import functools
import re
import textwrap
from io import BytesIO
from typing import List, Optional, Tuple

import discord
from discord.abc import Messageable
from PIL import Image, ImageDraw, ImageFont
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.data_manager import bundled_data_path

real_send = Messageable.send
FONT: Optional[ImageFont.ImageFont] = None


def _generate_image(text: str) -> discord.File:
    fp = BytesIO()
    assert FONT is not None
    w, h = FONT.getsize_multiline(text)
    im = Image.new("RGB", size=(w + 100, h + 75))
    draw = ImageDraw.Draw(im)
    draw.multiline_text((25, 25), text, font=FONT, fill="white")
    im.save(fp, format="png")

    fp.seek(0)
    return discord.File(fp, filename="message.png")


async def get_text_image(text: str) -> discord.File:
    processed_text = "\n".join(
        textwrap.fill(paragraph.strip()) for paragraph in text.split("\n")
    )
    return await asyncio.get_running_loop().run_in_executor(
        None, _generate_image, processed_text
    )


async def process_args(
    messageable, content, file, files
) -> Tuple[Optional[str], List[discord.File]]:
    if file is not None and files is not None:
        raise discord.InvalidArgument(
            "cannot pass both file and files parameter to send()"
        )
    if file is not None:
        files = [file]
    elif files is None:
        files = []
    if content is None:
        return None, files

    mentions = [
        match.group(0) for match in re.finditer(r"<@(?:!|&)?(\d+)>", content)
    ]
    ret_content = None
    if mentions:
        ret_content = ", ".join(mentions)

    if len(files) > 10:
        raise discord.InvalidArgument(
            "files parameter must be a list of up to 10 elements"
        )
    if len(files) == 10:
        await real_send(messageable, file=await get_text_image(content))
    else:
        files.insert(0, await get_text_image(content))
    return ret_content, files


if discord.version_info[:2] >= (1, 6):

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
        content, files = await process_args(self, content, file, files)
        return await real_send(
            self,
            content,
            tts=tts,
            embed=embed,
            files=files,
            delete_after=delete_after,
            nonce=nonce,
            allowed_mentions=allowed_mentions,
            reference=reference,
            mention_author=mention_author,
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
        content, files = await process_args(self, content, file, files)
        return await real_send(
            self,
            content,
            tts=tts,
            embed=embed,
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
        content, files = await process_args(self, content, file, files)
        return await real_send(
            self,
            content,
            tts=tts,
            embed=embed,
            files=files,
            delete_after=delete_after,
            nonce=nonce,
        )


class PillowSend(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.bundled_data_path = bundled_data_path(self)

    async def initialize(self) -> None:
        setattr(Messageable, "send", send)
        global FONT
        FONT = ImageFont.truetype(
            str(self.bundled_data_path / "fonts/NotoSans-Regular.ttf"), 14
        )

    def cog_unload(self) -> None:
        setattr(Messageable, "send", real_send)
