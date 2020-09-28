from redbot.core import commands
from redbot.core.bot import Red


class ReloadCom(commands.Cog):
    """
    Some dumb shit that Slime came up with.
    As a time reference, Slime's nickname at the time was Mimikyu.
    """
    def __init__(self, bot: Red) -> None:
        self.bot = bot

    @commands.is_owner()
    @commands.command()
    async def reloadcom(self, ctx: commands.Context, *, command: str) -> None:
        """
        Some dumb shit that Slime came up with.
        As a time reference, Slime's nickname at the time was Mimikyu.
        """
        com = self.bot.get_command(command)
        if com is None:
            await ctx.send("That command ain't here, you twat!")
            return

        cog = com.cog
        if cog is None:
            await ctx.send("That command ain't from a cog, you dumbass!")
            return

        full_module_name = cog.__module__
        if full_module_name.startswith("redbot.core"):
            await ctx.send("I ain't a magician, can't reload core without restart!")
            return

        if full_module_name.startswith("redbot.cogs"):
            pkg_name = full_module_name.split(".", maxsplit=3)[2]
        else:
            pkg_name = full_module_name.split(".", maxsplit=1)[0]

        reload_com = self.bot.get_command("reload")
        await reload_com(ctx, pkg_name)
