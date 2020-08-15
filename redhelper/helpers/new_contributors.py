import asyncio
import json
import logging
from typing import Dict

import discord
from discord.ext.commands.view import StringView  # DEP-WARN
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.config import Config
from redbot.core.utils.chat_formatting import pagify
from redbot.core.utils.predicates import MessagePredicate

from ..abc import MixinMeta
from ..discord_utils import safe_delete_message


GET_CONTRIBUTORS_QUERY = """
query getContributors($after: String) {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    defaultBranchRef {
      target {
        ... on Commit {
          history(first: 100, after: $after) {
            nodes {
              commitUrl
              author {
                email
                name
                user {
                  login
                }
              }
              associatedPullRequests(first:1) {
                nodes {
                  author {
                    login
                  }
                }
              }
            }
            pageInfo {
              endCursor
              hasNextPage
            }
          }
        }
      }
    }
  }
}
"""

log = logging.getLogger("red.weirdjack.redhelper.helpers.newcontributors")


class NewContributorsMixin(MixinMeta):
    def __init__(self, bot: Red) -> None:
        super().__init__(bot)
        self.ipc_task: asyncio.Task
        self.__config = Config.get_conf(
            None,
            176070082584248320,
            cog_name="RedHelper_NewContributors",
            force_registration=True,
        )
        self.__config.register_global(
            added_contributors={},
            pending_contributors={},
            leftguild_contributors={},
            output_channels=[],
        )

    def post_cog_add(self) -> None:
        super().post_cog_add()
        self.ipc_task = asyncio.create_task(self.ipc_server())

    def cog_unload(self) -> None:
        super().cog_unload()
        self.ipc_task.cancel()

    async def ipc_server(self) -> None:
        # could use UNIX socket instead here
        server = await asyncio.start_server(self.ipc_handler, "127.0.0.1", 8888)

        async with server:
            await server.serve_forever()

    async def ipc_handler(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        raw_data = await reader.read()
        payload = json.loads(raw_data.decode())

        # do something with the data here
        added_contributors = await self.__config.added_contributors()
        new_pending_contributors = {}
        for username, author_data in payload.items():
            if username not in added_contributors:
                new_pending_contributors[username] = author_data

        async with self.__config.pending_contributors() as pending_contributors:
            for username, author_data in dict(new_pending_contributors).items():
                if username in pending_contributors:
                    new_pending_contributors.pop(username, None)
                pending_contributors[username] = author_data

        writer.close()

        await self.new_pending_contributors_notify(new_pending_contributors)

    async def new_pending_contributors_notify(
        self, new_pending_contributors: Dict[str, Dict[str, str]]
    ) -> None:
        for username, author_data in new_pending_contributors.items():
            commit_author_name = author_data["name"]
            discord_user_id_line = (
                f"\n**Discord user ID:** {discord_user_id}"
                if (discord_user_id := author_data.get('discord_user_id')) is not None
                else ""
            )
            embed = discord.Embed(
                title="New pending contributor!",
                description=(
                    f"**GitHub:** [@{username}](https://github.com/{username})\n"
                    f"**Commit author name:** {commit_author_name}"
                    f"{discord_user_id_line}"
                ),
            )
            output_channels = [
                channel
                for channel_id in await self.__config.output_channels()
                if (channel := self.bot.get_channel(channel_id)) is not None
            ]
            for channel in output_channels:
                await channel.send(embed=embed)

    @commands.is_owner()
    @commands.group()
    async def newcontributors(self, ctx: commands.Context) -> None:
        """New contributors utility commands."""

    @commands.max_concurrency(1)
    @newcontributors.command(name="fetch")
    async def newcontributors_fetch(self, ctx: commands.Context) -> None:
        """Fetches all contributors and puts them in pending list.

        This command should only be ran on first setup.
        """
        async with ctx.typing():
            await self._newcontributors_fetch(ctx)

    async def _newcontributors_fetch(self, ctx: commands.Context) -> None:
        prompt_to_check_logs = False
        after = None
        has_next_page = True
        token = (await self.bot.get_shared_api_tokens("github")).get("token", "")
        new_pending_contributors = {}
        added_contributors = await self.__config.added_contributors()
        while has_next_page:
            async with self.session.post(
                "https://api.github.com/graphql",
                json={"query": GET_CONTRIBUTORS_QUERY, "variables": {"after": after}},
                headers={"Authorization": f"Bearer {token}"}
            ) as resp:
                json = await resp.json()
                commits = (
                    json["data"]["repository"]["defaultBranchRef"]["target"]["history"]
                )
                nodes = commits["nodes"]
                for node in nodes:
                    author_data = node["author"]
                    if author_data["user"] is None:
                        # the commit author doesn't have associated GH account
                        # let's try to check associated PR
                        try:
                            associated_pr = node["associatedPullRequests"]["nodes"][0]
                        except IndexError:
                            # no associated PRs - either:
                            # - commit wasn't made through PR
                            # - or something weird is going on
                            # let's just put it into logs
                            log.error(
                                "Failed to find GitHub username of commit author.\n"
                                "Commit author: %s <%s>\n"
                                "Commit URL: %s",
                                author_data["name"],
                                author_data["email"],
                                node["commitUrl"],
                            )
                            prompt_to_check_logs = True
                            continue
                        try:
                            username = associated_pr["author"]["login"]
                        except KeyError:
                            # author of PR has deleted his GH account
                            log.error(
                                "Failed to find GitHub username of commit author"
                                " through associated PR.\n"
                                "Commit author: %s <%s>\n"
                                "Commit URL: %s",
                                author_data["name"],
                                author_data["email"],
                                node["commitUrl"],
                            )
                            prompt_to_check_logs = True
                            continue
                    else:
                        username = author_data["user"]["login"]
                    if (
                        username not in new_pending_contributors
                        and username not in added_contributors
                    ):
                        new_pending_contributors[username] = {
                            "username": username,
                            "name": author_data["name"],
                            "email": author_data["email"],
                        }
                page_info = commits["pageInfo"]
                after = page_info["endCursor"]
                has_next_page = page_info["hasNextPage"]

        async with self.__config.pending_contributors() as pending_contributors:
            pending_contributors.update(new_pending_contributors)

        msg = "Finished"
        if prompt_to_check_logs:
            msg += (
                " There have been some issues, please check logs for more information."
            )
        await ctx.send(msg)

    @newcontributors.command(name="listpending")
    async def listpending(
        self, ctx: commands.Context, show_emails: bool = False
    ) -> None:
        """List pending contributors."""
        pending_contributors = await self.__config.pending_contributors()
        if await ctx.embed_requested():
            if show_emails:
                description = "\n".join(
                    f"[@{username}](https://github.com/{username})"
                    f" (Git name: {c['name']} <{c['email']}>)"
                    for username, c in pending_contributors.items()
                )
            else:
                description = "\n".join(
                    f"[@{username}](https://github.com/{username})"
                    f" (Git name: {c['name']})"
                    for username, c in pending_contributors.items()
                )
            for page in pagify(description):
                await ctx.send(embed=discord.Embed(description=description))
        else:
            if show_emails:
                text = "\n".join(
                    f"@{username} (Git name: {c['name']} <{c['email']}>)"
                    for username, c in pending_contributors.items()
                )
            else:
                text = "\n".join(
                    f"@{username} (Git name: {c['name']})"
                    for username, c in pending_contributors.items()
                )
            for page in pagify(text):
                await ctx.send(text)

    @newcontributors.command(name="addcontributor")
    async def newcontributors_addcontributor(
        self, ctx: commands.Context, username: str, member: discord.Member
    ):
        """Add single contributor by username."""
        async with self.__config.pending_contributors() as pending_contributors:
            if (author_data := pending_contributors.pop(username, None)) is None:
                await ctx.send("Contributor with this username isn't in pending list.")
                return

            author_data["discord_user_id"] = member.id
            async with self.__config.added_contributors() as added_contributors:
                added_contributors[username] = author_data

        await ctx.send(
            "Contributor added.\n"
            "You can use this command to add role to that member:\n"
            f"`?assign {member.id} contributor`"
        )

    @newcontributors.command(name="addoutput")
    async def newcontributors_addoutput(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Add output channel for new contributors notifications."""
        async with self.__config.output_channels() as output_channels:
            if channel.id in output_channels:
                await ctx.send("This channel is already output channel.")
                return
            output_channels.append(channel.id)
        await ctx.send("Channel added to output channels.")

    @newcontributors.command(name="deleteoutput")
    async def newcontributors_deleteoutput(
        self, ctx: commands.Context, channel: discord.TextChannel
    ) -> None:
        """Delete output channel for new contributors notifications."""
        async with self.__config.output_channels() as output_channels:
            try:
                output_channels.remove(channel.id)
            except ValueError:
                await ctx.send("This channel wasn't output channel.")
                return
        await ctx.send("Channel removed from output channels.")

    @commands.max_concurrency(1)
    @newcontributors.command(name="interactive")
    async def newcontributors_interactive(self, ctx: commands.Context) -> None:
        """Interactively add contributors.

        Integrates with Red.
        """
        member_converter = commands.MemberConverter()
        pending_contributors = await self.__config.pending_contributors()
        new_added_contributors = {}

        early_exit = False
        for username, author_data in pending_contributors.items():
            discord_user_id_line = (
                f"**Discord user ID:** {discord_user_id}\n"
                if (discord_user_id := author_data.get('discord_user_id')) is not None
                else ""
            )
            bot_msg = await ctx.send(
                f"**GitHub Username:** {username}\n"
                f"**Commit author name:** {author_data['name']}\n"
                f"**Commit author email:** {author_data['email']}\n"
                f"{discord_user_id_line}"
                "Use Red's `?assign` command or send user ID to add contributor."
                " Type `exit` to finish, use `skip` to skip the contributor."
            )

            while not early_exit:
                user_msg = await self.bot.wait_for(
                    "message_without_command", check=MessagePredicate.same_context(ctx)
                )
                content = user_msg.content

                if content == "exit":
                    early_exit = True
                    continue
                if content == "skip":
                    break

                if user_msg.content.startswith("?assign "):
                    view = StringView(user_msg.content)
                    view.skip_string("?assign ")
                    content = view.get_quoted_word()

                try:
                    member = await member_converter.convert(ctx, content)
                except commands.BadArgument as e:
                    await ctx.send(
                        f"{e}. Please try passing user ID"
                        " or using `?assign` command again."
                    )
                    continue

                author_data["discord_user_id"] = member.id
                new_added_contributors[username] = author_data
                break
            else:
                # early-exit by breaking out of for loop
                await safe_delete_message(bot_msg)
                break

            await safe_delete_message(bot_msg)

        async with self.__config.pending_contributors() as pending_contributors:
            for username in new_added_contributors:
                pending_contributors.pop(username, None)

        async with self.__config.added_contributors() as added_contributors:
            added_contributors.update(new_added_contributors)

        await ctx.send("Finished early." if early_exit else "Finished")

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        if member.guild.id != 133049272517001216:  # Red - Discord Bot server
            # Ignore other servers the bot is in
            return

        async with self.__config.leftguild_contributors() as leftguild_contributors:
            if (
                contributor_data := leftguild_contributors.pop(str(member.id), None)
            ) is None:
                return

            new_pending_contributors = {contributor_data["username"]: contributor_data}

            async with self.__config.pending_contributors() as pending_contributors:
                for username, author_data in dict(new_pending_contributors).items():
                    if username in pending_contributors:
                        new_pending_contributors.pop(username, None)
                    pending_contributors[username] = author_data

        await self.new_pending_contributors_notify(new_pending_contributors)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.guild.id != 133049272517001216:  # Red - Discord Bot server
            # Ignore other servers the bot is in
            return

        async with self.__config.added_contributors() as added_contributors:
            if not added_contributors:
                return

            for contributor_data in added_contributors.values():
                if contributor_data["discord_user_id"] == member.id:
                    break
            else:
                return

            added_contributors.pop(contributor_data["username"])
            async with self.__config.leftguild_contributors() as leftguild_contributors:
                leftguild_contributors[
                    contributor_data["discord_user_id"]
                ] = contributor_data
