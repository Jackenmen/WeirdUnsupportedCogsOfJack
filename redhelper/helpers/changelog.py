import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.commands import NoParseOptional as Optional
from redbot.core.config import Config, Group
from redbot.core.utils.chat_formatting import box

from ..abc import MixinMeta


GET_MILESTONE_CONTRIBUTORS_QUERY = """
query getMilestoneContributors($milestone: String!, $after: String) {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    milestones(first: 1, query: $milestone) {
      nodes {
        title
        pullRequests(first: 100, after: $after) {
          nodes {
            author {
              login
            }
            merged
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
"""
GITHUB_USERS = "GITHUB_USERS"


def get_rst_string(display_name: str, github_username: str) -> str:
    if display_name == github_username:
        return f":ghuser:`{github_username}`"
    return f":ghuser:`{display_name} <{github_username}>`"


class ChangelogMixin(MixinMeta):
    def __init__(self, bot: Red) -> None:
        super().__init__(bot)
        self.__config = Config.get_conf(
            None,
            176070082584248320,
            cog_name="RedHelper_Changelog",
            force_registration=True,
        )
        # {github_username: {...}}
        self.__config.init_custom(GITHUB_USERS, 1)
        self.__config.register_custom(GITHUB_USERS, custom_name=None)

    def gh_user_config(self, github_username: str) -> Group:
        return self.__config.custom(GITHUB_USERS, github_username.lower())

    async def get_name(self, github_username: str) -> str:
        group = self.gh_user_config(github_username)
        return await group.custom_name() or github_username

    @commands.command()
    async def getcontributors(
        self, ctx: commands.Context, milestone: str, show_not_merged: bool = False
    ) -> None:
        """
        Get contributors for the given milestone in Red's repo.

        By default, this only shows PRs that have already been merged.
        You can pass True to `<show_not_merged>` to show both merged and not merged PRs.
        """
        after = None
        has_next_page = True
        authors = set()
        token = (await self.bot.get_shared_api_tokens("github")).get("token", "")
        while has_next_page:
            async with self.session.post(
                "https://api.github.com/graphql",
                json={
                    "query": GET_MILESTONE_CONTRIBUTORS_QUERY,
                    "variables": {
                        "milestone": milestone,
                        "after": after,
                    },
                },
                headers={"Authorization": f"Bearer {token}"},
            ) as resp:
                json = await resp.json()
                try:
                    milestone_data = json["data"]["repository"]["milestones"]["nodes"][0]
                except IndexError:
                    await ctx.send("Given milestone couldn't have been found.")
                milestone_title = milestone_data["title"]
                pull_requests = milestone_data["pullRequests"]
                nodes = pull_requests["nodes"]
                authors |= {
                    node["author"]["login"]
                    for node in nodes
                    if show_not_merged or node["merged"]
                }
                page_info = pull_requests["pageInfo"]
                after = page_info["endCursor"]
                has_next_page = page_info["hasNextPage"]

        authors_with_names = [
            (await self.get_name(github_username), github_username)
            for github_username in authors
        ]
        sorted_authors = sorted(authors_with_names, key=lambda t: t[0].lower())

        embed = discord.Embed(
            title=f"Contributors to milestone {milestone_title}",
            description=", ".join(
                map("[{0[0]}](https://github.com/{0[1]})".format, sorted_authors)
            ),
        )
        embed.add_field(
            name="RST formatted list (with custom display names)",
            value=box(
                ", ".join(
                    get_rst_string(display_name, github_username)
                    for display_name, github_username in sorted_authors
                )
            ),
        )

        await ctx.send(embed=embed)

    @commands.is_owner()
    @commands.command()
    async def setcontributorname(
        self,
        ctx: commands.Context,
        github_username: str,
        display_name: Optional[str] = None,
    ):
        """
        Set custom display name for a contributor.

        Don't pass `display_name` to reset to GitHub username.
        """
        # I could do a comparison between `github_username` and `display_name`,
        # but one could only want to update the casing which would fail in that case
        group = self.gh_user_config(github_username)
        await group.display_name.set(display_name)
        if display_name is None:
            await ctx.send("Display name reset.")
        else:
            await ctx.send("Display name updated.")
