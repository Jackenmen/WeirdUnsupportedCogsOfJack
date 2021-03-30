import logging
from datetime import datetime
from string import Template

import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import inline, pagify


log = logging.getLogger("red.weirdjack.aprilfoolsrenamer")


class AprilFoolsRenamer(commands.Cog):
    """A fun little April Fools cog that sets nicknames of all users using a given template."""
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.config = Config.get_conf(self, 176070082584248320, force_registration=True)
        # this is `False` rather than `None`
        # because `None` is a valid value for nickname
        self.config.register_guild(nick_template=None)
        self.config.register_member(original_nick=False)

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def setnicktemplate(
        self, ctx: commands.GuildContext, *, nick_template: str = None
    ) -> None:
        """
        Set nickname template for auto-renaming.

        Leave empty to disable (to reverse `[p]renameall`, you still need to use `[p]revertnicks`)
        """
        if nick_template is None:
            command = inline(f"{ctx.clean_prefix}revertnicks")
            await ctx.send(
                "Auto-renaming disabled."
                f" Use {command} to revert the changes to the nicknames."
            )
            return
        tmpl = Template(nick_template)
        if len(tmpl.safe_substitute(index=len(ctx.guild.members))) > 32:
            await ctx.send("Nickname is too long!")
            return
        await self.config.guild(ctx.guild).nick_template.set(nick_template)
        nick = tmpl.safe_substitute(index=len(ctx.guild.members))
        await ctx.send(f"Nickname template set! Here's an example nickname: {nick}")

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def renameall(self, ctx: commands.GuildContext) -> None:
        """
        Rename everyone in the server.

        These values will be substituted:
        $index - Member's number/index on the members list. First server member (with the earliest join date) has $index=1, second member $index=2 and so on.
        """
        nick_template = await self.config.guild(ctx.guild).nick_template()
        if nick_template is None:
            command = inline(f"{ctx.clean_prefix}setnicktemplate")
            await ctx.send(
                "Nickname template needs to be set"
                f" with {command} before you can use this command."
            )
            return
        tmpl = Template(nick_template)
        if len(tmpl.safe_substitute(index=len(ctx.guild.members))) > 32:
            await ctx.send("The set nickname is too long!")
            return

        members = sorted(ctx.guild.members, key=lambda m: m.joined_at)

        not_changed = []
        async with ctx.typing():
            for idx, member in enumerate(members, start=1):
                nick = tmpl.safe_substitute(index=idx)
                if member.top_role >= ctx.guild.me.top_role:
                    not_changed.append(
                        f"{member} (would be: {nick})"
                        " - Member's top role is not lower than mine."
                    )
                    continue
                original_nick = member.nick
                try:
                    await member.edit(nick=nick, reason="April Fools joke")
                except discord.HTTPException as exc:
                    not_changed.append(
                        f"{member} (would be: {nick}) - An unexpected error occurred"
                        f" when trying to edit member's nickname: {exc}"
                    )
                else:
                    await self.config.member(member).original_nick.set(original_nick)

        msg = "Nicknames updated!"
        if not_changed:
            msg += "Nicknames of these users have not been updated:"
            msg += "\n".join(not_changed)
        await ctx.send(msg)

    @commands.guild_only()
    @commands.admin()
    @commands.command()
    async def resetnicks(self, ctx: commands.GuildContext) -> None:
        """
        Reset everyone's nicknames to what they were before `[p]renameall` command was used.
        """
        not_changed = []
        async with ctx.typing():
            for member in ctx.guild.members:
                original_nick = await self.config.member(member).original_nick()
                if original_nick is False:
                    continue
                if member.top_role >= ctx.guild.me.top_role:
                    not_changed.append(
                        f"{member} - Member's top role is not lower than mine."
                    )
                    continue
                try:
                    await member.edit(
                        nick=original_nick, reason="Revert April Fools joke"
                    )
                except discord.HTTPException as exc:
                    not_changed.append(
                        f"{member} - An unexpected error occurred"
                        f" when trying to edit member's nickname: {exc}"
                    )
                else:
                    await self.config.member(member).original_nick.clear()

        msg = "Nicknames updated!"
        if not_changed:
            msg += "Nicknames of these users have not been updated:"
            msg += "\n".join(not_changed)
        for page in pagify(msg):
            await ctx.send(page)

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        nick_template = await self.config.guild(member.guild).nick_template()
        if nick_template is None:
            return
        tmpl = Template(nick_template)
        idx = (
            sorted(
                member.guild.members, key=lambda m: m.joined_at or datetime.utcnow()
            ).index(member)
            + 1
        )
        original_nick = member.nick  # most likely just None
        nick = tmpl.safe_substitute(index=idx)
        try:
            await member.edit(nick=nick, reason="April Fools joke")
        except discord.HTTPException as exc:
            log.error(
                "%s - An unexpected error occurred"
                " when trying to edit member's nickname",
                member,
                exc_info=exc,
            )
        else:
            await self.config.member(member).original_nick.set(original_nick)
