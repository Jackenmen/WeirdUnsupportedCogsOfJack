import asyncio
import json

import aiohttp
import discord
from redbot.core import commands
from redbot.core.bot import Red


getContributorsQuery = """
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


class RedHelper(commands.Cog):
    def __init__(self, bot: Red) -> None:
        self.bot = bot
        self.session: aiohttp.ClientSession
        self.ipc_task: asyncio.Task

    def post_cog_add(self) -> None:
        self.session = aiohttp.ClientSession()
        self.ipc_task = asyncio.create_task(self.ipc_server())

    def cog_unload(self) -> None:
        asyncio.create_task(self.session.close())
        self.ipc_task.cancel()

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
                    "query": getContributorsQuery,
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
        await ctx.send(
            embed=discord.Embed(
                title=f"Contributors to milestone {milestone}",
                description=", ".join(
                    map(
                        "[{0}](https://github.com/{0})".format,
                        sorted(authors, key=str.lower)
                    )
                ),
            )
        )

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
        print(payload)

        writer.close()
