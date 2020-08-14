import asyncio
import json
from redbot.core.bot import Red

from ..abc import MixinMeta


class NewContributorsMixin(MixinMeta):
    def __init__(self, bot: Red) -> None:
        super().__init__(bot)
        self.ipc_task: asyncio.Task

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
        print(payload)

        writer.close()
