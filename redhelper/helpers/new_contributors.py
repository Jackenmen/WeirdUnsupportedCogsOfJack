import asyncio
import json
import logging
import re
from typing import Dict, TypedDict

import aiohttp
import discord
from discord.ext.commands.view import StringView  # DEP-WARN
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import GuildContext
from redbot.core.config import Config, Group
from redbot.core.utils.chat_formatting import inline, pagify
from redbot.core.utils.predicates import MessagePredicate

from ..abc import MixinMeta
from ..discord_utils import safe_delete_message

log = logging.getLogger("red.weirdjack.redhelper.helpers.newcontributors")

RED_MAIN_GUILD_ID = 133049272517001216
ORG_MEMBER_ROLE_ID = 739263148024004749
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
                  id
                  login
                }
              }
              associatedPullRequests(first:1) {
                nodes {
                  author {
                    id
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


class IncompleteAuthorData(TypedDict):
    name: str
    email: str
    username: str


class AuthorData(IncompleteAuthorData):
    id: str


class UserIdQuery:
    def __init__(self, incomplete_authors: Dict[str, IncompleteAuthorData]) -> None:
        self.incomplete_authors = incomplete_authors
        self.usernames = list(incomplete_authors.keys())

    @classmethod
    async def fetch_author_data(
        cls,
        incomplete_authors: Dict[str, IncompleteAuthorData],
        *,
        session: aiohttp.ClientSession,
        gh_token: str,
    ) -> Dict[str, AuthorData]:
        query = cls(incomplete_authors)
        query_string = query._get_query()
        async with session.post(
            "https://api.github.com/graphql",
            json={"query": query_string},
            headers={"Authorization": f"Bearer {gh_token}"}
        ) as resp:
            data = await resp.json()

        return query._get_authors_from_resp_data(data["data"])

    def _get_query(self) -> str:
        query_parts = ["query{"]
        for idx, username in enumerate(self.usernames):
            query_parts.append(
                f"u{idx}:"
                f'user(login:"{username}")'
                "{id}"
            )
        query_parts.append("}")
        return "".join(query_parts)

    def _get_authors_from_resp_data(
        self, data: Dict[str, Dict[str, str]]
    ) -> Dict[str, AuthorData]:
        authors: Dict[str, AuthorData] = {}
        for idx, username in enumerate(self.usernames):
            user_data = data.get(f"u{idx}")
            if user_data is None:
                log.error("Couldn't find user ID for user with username: %s", username)
                continue
            authors[user_data["id"]] = {
                **self.incomplete_authors[username],
                "id": user_data["id"],
            }

        return authors


def is_org_member():
    async def predicate(ctx: commands.Context) -> bool:
        guild = ctx.bot.get_guild(RED_MAIN_GUILD_ID)
        if guild is None:
            return False
        author = guild.get_member(ctx.author.id)
        if author is None:
            return False
        role = guild.get_role(ORG_MEMBER_ROLE_ID)
        if role is None:
            return False
        return role in author.roles

    return commands.check(predicate)


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
            login_id_map={},
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
        writer.close()

        # do something with the data here
        added_contributors = await self.__config.added_contributors()
        login_id_map = await self.__config.login_id_map()
        new_pending_contributors_incomplete = {}
        for username, author_data in payload.items():
            if username.endswith("[bot]"):
                continue
            user_id = login_id_map.get(username)
            if user_id is not None and user_id in added_contributors:
                continue
            new_pending_contributors_incomplete[username] = author_data

        if not new_pending_contributors_incomplete:
            return

        new_pending_contributors = await UserIdQuery.fetch_author_data(
            new_pending_contributors_incomplete,
            session=self.session,
            gh_token=(await self.bot.get_shared_api_tokens("github")).get("token", ""),
        )

        async with self.__config.pending_contributors() as pending_contributors:
            async with self.__config.login_id_map() as login_id_map:
                for user_id, author_data in dict(new_pending_contributors).items():
                    login_id_map[author_data["username"]] = user_id
                    if user_id in pending_contributors:
                        new_pending_contributors.pop(user_id, None)
                    pending_contributors[user_id] = author_data

        await self.new_pending_contributors_notify(new_pending_contributors)

    async def new_pending_contributors_notify(
        self, new_pending_contributors: Dict[str, AuthorData]
    ) -> None:
        for author_data in new_pending_contributors.values():
            username = author_data["username"]
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
                prefixes = await self.bot.get_valid_prefixes(channel.guild)
                command = inline(
                    f"{prefixes[0]}newcontributors add {username} <member>"
                )
                embed.set_footer(
                    text=f"Use {command} to map the contributor to server member."
                )
                await channel.send(embed=embed)

    @is_org_member()
    @commands.guild_only()
    @commands.group()
    async def newcontributors(self, ctx: GuildContext) -> None:
        """New contributors utility commands."""

    @commands.is_owner()
    @commands.max_concurrency(1)
    @newcontributors.command(name="fetch")
    async def newcontributors_fetch(self, ctx: GuildContext) -> None:
        """Fetches all contributors and puts them in pending list.

        This command should only be ran on first setup.
        """
        async with ctx.typing():
            await self._newcontributors_fetch(ctx)

    async def _newcontributors_fetch(self, ctx: GuildContext) -> None:
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
                            user_data = associated_pr["author"]
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
                        user_data = author_data["user"]
                    user_id = user_data["id"]
                    if (
                        user_id not in new_pending_contributors
                        and user_id not in added_contributors
                    ):
                        new_pending_contributors[user_id] = {
                            "id": user_id,
                            "username": user_data["login"],
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
        self, ctx: GuildContext, show_emails: bool = False
    ) -> None:
        """List pending contributors."""
        pending_contributors = await self.__config.pending_contributors()
        if await ctx.embed_requested():
            if show_emails:
                description = "\n".join(
                    f"[@{c['username']}](https://github.com/{c['username']})"
                    f" (Git name: {c['name']} <{c['email']}>)"
                    for c in pending_contributors.values()
                )
            else:
                description = "\n".join(
                    f"[@{c['username']}](https://github.com/{c['username']})"
                    f" (Git name: {c['name']})"
                    for c in pending_contributors.values()
                )
            for _ in pagify(description):
                await ctx.send(embed=discord.Embed(description=description))
        else:
            if show_emails:
                text = "\n".join(
                    f"@{c['username']} (Git name: {c['name']} <{c['email']}>)"
                    for c in pending_contributors.values()
                )
            else:
                text = "\n".join(
                    f"@{c['username']} (Git name: {c['name']})"
                    for c in pending_contributors.values()
                )
            for _ in pagify(text):
                await ctx.send(text)

    @newcontributors.command(name="add")
    async def newcontributors_add(
        self, ctx: GuildContext, username: str, member: discord.Member
    ):
        """Add single contributor by username."""
        login_id_map = await self.__config.login_id_map()
        try:
            user_id = login_id_map.get(username)
        except KeyError:
            await ctx.send("Contributor with this username isn't in any list.")
            return

        async with self.__config.pending_contributors() as pending_contributors:
            if (author_data := pending_contributors.pop(user_id, None)) is None:
                await ctx.send("Contributor with this username isn't in pending list.")
                return

            author_data["discord_user_id"] = member.id
            async with self.__config.added_contributors() as added_contributors:
                added_contributors[user_id] = author_data

        await ctx.send(
            "Contributor added.\n"
            "You can use this command to add role to that member:\n"
            f"`?assign {member.id} contributor`"
        )

    @newcontributors.command(name="hackadd")
    async def newcontributors_hackadd(
        self, ctx: GuildContext, username: str, user_id: int
    ):
        """Hack-add a single contributor by username."""
        if self.bot.get_guild(RED_MAIN_GUILD_ID).get_member(user_id) is not None:
            command = inline(f"{ctx.clean_prefix}newcontributors add")
            await ctx.send(
                f"This user is in the server, please use {command} instead."
            )
            return

        # yes, this has low ratelimit, but I don't care!
        try:
            user = await self.bot.fetch_user(user_id)
        except discord.NotFound:
            await ctx.send("User doesn't exist!")
            return

        login_id_map = await self.__config.login_id_map()
        try:
            user_id = login_id_map.get(username)
        except KeyError:
            await ctx.send("Contributor with this username isn't in any list.")
            return

        async with self.__config.pending_contributors() as pending_contributors:
            if (author_data := pending_contributors.pop(user_id, None)) is None:
                await ctx.send("Contributor with this username isn't in pending list.")
                return

            author_data["discord_user_id"] = user.id
            async with self.__config.leftguild_contributors() as leftguild_contributors:
                leftguild_contributors[user.id] = author_data

        await ctx.send("Contributor hack-added.")

    @commands.is_owner()
    @newcontributors.command(name="ignore")
    async def newcontributors_ignore(
        self, ctx: GuildContext, username: str
    ) -> None:
        """Ignore contributor by username. This should only be used for bot accounts."""
        login_id_map = await self.__config.login_id_map()
        try:
            user_id = login_id_map.get(username)
        except KeyError:
            await ctx.send("Contributor with this username isn't in any list.")
            return

        async with self.__config.pending_contributors() as pending_contributors:
            if (author_data := pending_contributors.pop(user_id, None)) is None:
                await ctx.send("Contributor with this username isn't in pending list.")
                return

            author_data["discord_user_id"] = None
            async with self.__config.added_contributors() as added_contributors:
                added_contributors[user_id] = author_data

        await ctx.send("Contributor ignored.")

    @commands.is_owner()
    @newcontributors.command(name="unignore")
    async def newcontributor_unignore(
        self, ctx: GuildContext, username: str
    ):
        """Unignore contributor by username. Just in case you make a mistake ;)"""
        login_id_map = await self.__config.login_id_map()
        try:
            user_id = login_id_map.get(username)
        except KeyError:
            await ctx.send("Contributor with this username isn't in any list.")
            return

        async with self.__config.added_contributors() as added_contributors:
            if (author_data := added_contributors.pop(user_id, None)) is None:
                await ctx.send("Contributor with this username isn't in the list.")
                return

            if author_data["discord_user_id"] is not None:
                await ctx.send("Contributor with this username isn't ignored.")
                return

            async with self.__config.pending_contributors() as pending_contributors:
                pending_contributors[user_id] = author_data

        await ctx.send("Contributor unignored.")

    @commands.is_owner()
    @newcontributors.command(name="addoutput")
    async def newcontributors_addoutput(
        self, ctx: GuildContext, channel: discord.TextChannel
    ) -> None:
        """Add output channel for new contributors notifications."""
        async with self.__config.output_channels() as output_channels:
            if channel.id in output_channels:
                await ctx.send("This channel is already output channel.")
                return
            output_channels.append(channel.id)
        await ctx.send("Channel added to output channels.")

    @commands.is_owner()
    @newcontributors.command(name="deleteoutput")
    async def newcontributors_deleteoutput(
        self, ctx: GuildContext, channel: discord.TextChannel
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
    async def newcontributors_interactive(self, ctx: GuildContext) -> None:
        """Interactively add contributors.

        Integrates with Red.
        """
        member_converter = commands.MemberConverter()
        pending_contributors = await self.__config.pending_contributors()
        new_added_contributors = {}

        early_exit = False
        for user_id, author_data in pending_contributors.items():
            discord_user_id_line = (
                f"**Discord user ID:** {discord_user_id}\n"
                if (discord_user_id := author_data.get('discord_user_id')) is not None
                else ""
            )
            bot_msg = await ctx.send(
                f"**GitHub Username:** {author_data['username']}\n"
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
                new_added_contributors[user_id] = author_data
                break
            else:
                # early-exit by breaking out of for loop
                await safe_delete_message(bot_msg)
                break

            await safe_delete_message(bot_msg)

        async with self.__config.pending_contributors() as pending_contributors:
            for user_id in new_added_contributors:
                pending_contributors.pop(user_id, None)

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

            new_pending_contributors = {contributor_data["id"]: contributor_data}

            async with self.__config.pending_contributors() as pending_contributors:
                for user_id, author_data in dict(new_pending_contributors).items():
                    if user_id in pending_contributors:
                        new_pending_contributors.pop(user_id, None)
                    pending_contributors[user_id] = author_data

        await self.new_pending_contributors_notify(new_pending_contributors)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        if member.guild.id != RED_MAIN_GUILD_ID:  # Red - Discord Bot server
            # Ignore other servers the bot is in
            return

        if await self._mark_contributor_as_left(self.__config.added_contributors, member):
            return
        await self._mark_contributor_as_left(self.__config.pending_contributors, member)

    async def _mark_contributor_as_left(self, group: Group, member: discord.Member) -> bool:
        async with group() as contributors:
            if not contributors:
                return False

            for contributor_data in contributors.values():
                discord_user_id = contributor_data.get("discord_user_id")
                if discord_user_id is not None and discord_user_id == member.id:
                    break
            else:
                return False

            contributors.pop(contributor_data["id"])
            async with self.__config.leftguild_contributors() as leftguild_contributors:
                leftguild_contributors[discord_user_id] = contributor_data

        return True
