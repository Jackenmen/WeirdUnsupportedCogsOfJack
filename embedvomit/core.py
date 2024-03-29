import functools
import re
from typing import Any, Optional, Sequence

import discord
from discord.abc import Messageable
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config


MENTION_RE = re.compile(r"<@[!&]?[0-9]{15,20}>|@everyone|@here")
real_send = Messageable.send


if discord.version_info[0] >= 2:

    @functools.wraps(real_send)
    async def send(
        self,
        content: Optional[str] = None,
        *,
        embed: Optional[discord.Embed] = None,
        embeds: Optional[Sequence[discord.Embed]] = None,
        **kwargs: Any,
    ) -> discord.Message:
        content = str(content) if content is not None else None
        new_content: Optional[str] = " ".join(
            map(re.Match.group, MENTION_RE.finditer(content or ""))
        )
        if new_content and len(new_content) <= 1996:
            new_content = f"||{new_content}||"
        new_content = new_content or None

        if embed is not None and embeds is not None:
            raise TypeError("Cannot mix embed and embeds keyword arguments.")
        new_embeds = []
        if embed is not None:
            new_embeds.append(embed)
        elif embeds is not None:
            if len(embeds) > 10:
                raise ValueError("embeds has a maximum of 10 elements.")
            new_embeds.extend(embeds)

        if content:
            new_embeds.insert(0, discord.Embed(description=content))
        if not new_embeds:
            new_embeds.append(discord.Embed(description="\u200b"))

        if len(new_embeds) > 10:
            await real_send(
                self,
                new_content,
                embed=new_embeds.pop(0),
                tts=kwargs.get("tts", False),
                delete_after=kwargs.get("delete_after", None),
                allowed_mentions=kwargs.get("allowed_mentions", None),
                reference=kwargs.pop("reference", None),
                mention_author=kwargs.get("mention_author", None),
                suppress_embeds=kwargs.get("suppress_embeds", False),
                silent=kwargs.get("silent", False),
            )
            new_content = None

        return await real_send(self, new_content, embeds=new_embeds, **kwargs)

else:

    @functools.wraps(real_send)
    async def send(
        self,
        content: Optional[str] = None,
        *,
        embed: Optional[discord.Embed] = None,
        **kwargs: Any,
    ) -> discord.Message:
        content = str(content) if content is not None else None
        new_content: Optional[str] = " ".join(
            map(re.Match.group, MENTION_RE.finditer(content or ""))
        )
        if new_content and len(new_content) <= 1996:
            new_content = f"||{new_content}||"
        new_content = new_content or None

        if embed is None:
            embed = discord.Embed(description=content or "\u200b")
        elif content:
            await real_send(
                self,
                new_content,
                embed=discord.Embed(description=content),
                tts=kwargs.get("tts", False),
                delete_after=kwargs.get("delete_after", None),
                reference=kwargs.pop("reference", None),
                allowed_mentions=kwargs.get("allowed_mentions", None),
                mention_author=kwargs.get("mention_author", None),
            )
            new_content = None

        return await real_send(self, new_content, embed=embed, **kwargs)


class EmbedVomit(commands.Cog):
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
    async def embedvomit(self, ctx: commands.Context, toggle: bool) -> None:
        if toggle:
            setattr(Messageable, "send", send)
        else:
            setattr(Messageable, "send", real_send)
        await self.config.toggle.set(toggle)
        await ctx.tick()
