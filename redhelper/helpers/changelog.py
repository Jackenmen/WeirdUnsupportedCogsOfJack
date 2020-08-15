import discord
from redbot.core import commands
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


class ChangelogMixin(MixinMeta):
    @commands.is_owner()
    @commands.command()
    async def getcontributors(self, ctx: commands.Context, milestone: str) -> None:
        """Get contributors for the given milestone in Red's repo."""
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
                    }
                },
                headers={"Authorization": f"Bearer {token}"}
            ) as resp:
                json = await resp.json()
                try:
                    milestone_data = json["data"]["repository"]["milestones"]["nodes"][0]
                except IndexError:
                    await ctx.send("Given milestone couldn't have been found.")
                milestone_title = milestone_data["title"]
                pull_requests = milestone_data["pullRequests"]
                nodes = pull_requests["nodes"]
                authors |= {node["author"]["login"] for node in nodes}
                page_info = pull_requests["pageInfo"]
                after = page_info["endCursor"]
                has_next_page = page_info["hasNextPage"]

        sorted_authors = sorted(authors, key=str.lower)

        embed = discord.Embed(
            title=f"Contributors to milestone {milestone_title}",
            description=", ".join(
                map("[{0}](https://github.com/{0})".format, sorted_authors)
            ),
        )
        embed.add_field(
            name="RST formatted list",
            value=box(", ".join(map(":ghuser:`{}`".format, sorted_authors))),
        )

        await ctx.send(embed=embed)
