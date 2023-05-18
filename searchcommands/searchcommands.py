from __future__ import annotations

from typing import Union

import discord
import fuzzywuzzy.process
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.menus import menu


class SearchCommands(commands.Cog):
    """
    Did you ever wonder, where the fuck is that little slut command hiding?
    Now it's made easy with SearchCommands cog! Just run `[p]commandsearch`!
    """

    def __init__(self, bot: Red) -> None:
        self.bot = bot

    @commands.command(aliases=["searchcommands"])
    async def commandsearch(self, ctx: commands.Context, *, query: str) -> None:
        """Slutty commands will never be able to hide from you again!"""
        async with ctx.typing():
            # who cares for blocking if this is unsupported
            cmd_list = [
                {
                    "name": cmd.qualified_name,
                    "help": cmd.format_help_for_context(ctx),
                }
                for cmd in set(self.bot.walk_commands())
            ]
            name_matches = fuzzywuzzy.process.extract(
                {"name": query},
                cmd_list,
                processor=lambda c: fuzzywuzzy.utils.full_process(c["name"]),
            )
            help_matches = fuzzywuzzy.process.extract(
                {"help": query},
                cmd_list,
                processor=lambda c: fuzzywuzzy.utils.full_process(c["help"]),
            )
            best_matches = sorted(
                name_matches + help_matches, key=lambda m: m[1], reverse=True
            )

            pages = []
            # copy paste from cogboard
            use_embeds = ctx.channel.permissions_for(ctx.me).embed_links
            if use_embeds:
                embed_color = await ctx.embed_color()
            page: Union[discord.Embed, str]
            for match in best_matches:
                cmd = match[0]
                if use_embeds:
                    page = discord.Embed(title=cmd["name"], color=embed_color)
                    page.add_field(
                        name="Command's help",
                        value=cmd["help"][:1000] if cmd["help"] else "Unspecified",
                        inline=False,
                    )
                else:
                    page = (
                        f"```asciidoc\n"
                        f"= {cmd['name']} =\n"
                        f"* Command's help:\n"
                        f"  {cmd['help'][:1000] if cmd['help'] else 'Unspecified'}\n"
                        f"```"
                    )
                pages.append(page)
        await menu(ctx, pages)
