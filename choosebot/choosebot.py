from typing import Optional

from redbot.core import commands, data_manager
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import inline


class ChooseBot(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.chosen_bot: Optional[str] = None

    async def bot_check_once(self, ctx: commands.Context) -> bool:
        if ctx.command is self.choosebot:
            return True

        instance_name = data_manager.instance_name
        assert isinstance(instance_name, str)
        if self.chosen_bot == instance_name:
            return True

        if not await self.bot.is_owner(ctx.author):
            return True

        if self.chosen_bot is None:
            raise commands.UserFeedbackCheckFailure(
                f"No instance name is set to be enforced, assuming that this instance"
                f" ({inline(instance_name)}) isn't the one you wanted to use.\n\n"
                f"Use `choosebot` command to choose the bot."
            )

        raise commands.UserFeedbackCheckFailure(
            f"The name of enforced instance is {inline(self.chosen_bot)}"
            f" but you tried to use {instance_name}. Aborting..."
        )

    @commands.is_owner()
    @commands.command()
    async def choosebot(self, ctx: commands.Context, instance_name: str) -> None:
        self.chosen_bot = instance_name
        await ctx.send(
            f"[{data_manager.instance_name}] Usage of the instance with name"
            f" {inline(instance_name)} will now be enforced."
        )
