import asyncio

import aiohttp
import discord
from redbot.core import commands
from redbot.core.bot import Red
from redbot.core.utils.chat_formatting import box

from ..abc import MixinMeta


GET_CONTRIBUTORS_QUERY = """
query getContributors($milestone: Int!, $after: String) {
  repository(owner: "Cog-Creators", name: "Red-DiscordBot") {
    milestone(number: $milestone) {
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
"""


class ChangelogMixin(MixinMeta):
    def __init__(self, bot: Red) -> None:
        super().__init__(bot)
        self.session: aiohttp.ClientSession

    def post_cog_add(self) -> None:
        super().post_cog_add()
        self.session = aiohttp.ClientSession()

    def cog_unload(self) -> None:
        super().cog_unload()
        asyncio.create_task(self.session.close())

    @commands.is_owner()
    @commands.command()
    async def getcontributors(self, ctx: commands.Context, milestone: int) -> None:
        """Get contributors for the given milestone in Red's repo."""
        after = None
        has_next_page = True
        authors = set()
        token = (await self.bot.get_shared_api_tokens("github")).get("token", "")
        while has_next_page:
            async with self.session.post(
                "https://api.github.com/graphql",
                json={
                    "query": GET_CONTRIBUTORS_QUERY,
                    "variables": {
                        "milestone": milestone,
                        "after": after,
                    }
                },
                headers={"Authorization": f"Bearer {token}"}
            ) as resp:
                json = await resp.json()
                pull_requests = json["data"]["repository"]["milestone"]["pullRequests"]
                nodes = pull_requests["nodes"]
                authors |= {node["author"]["login"] for node in nodes}
                page_info = pull_requests["pageInfo"]
                after = page_info["endCursor"]
                has_next_page = page_info["hasNextPage"]

        sorted_authors = sorted(authors, key=str.lower)

        embed = discord.Embed(
            title=f"Contributors to milestone {milestone}",
            description=", ".join(
                map("[{0}](https://github.com/{0})".format, sorted_authors)
            ),
        )
        embed.add_field(
            name="RST formatted list",
            value=box(", ".join(map(":ghuser:`{}`".format, sorted_authors))),
        )

        await ctx.send(embed=embed)