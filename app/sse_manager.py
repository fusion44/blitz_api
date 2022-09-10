import asyncio
from asyncio.log import logger
from typing import Tuple
import async_timeout

from fastapi import Request

from app.external.sse_starlette import EventSourceResponse, ServerSentEvent


class SSEManager:
    _setup_finished = False
    _num_connections = 0
    _connections = {}
    _sse_queue = asyncio.Queue()

    def setup(self) -> None:
        if self._setup_finished:
            raise RuntimeError("SSEManager setup must not be called twice")

        loop = asyncio.get_event_loop()
        loop.create_task(self._broadcast_data_sse())
        self._setup_finished = True

    def add_connection(self, request: Request) -> Tuple[EventSourceResponse, int]:
        q = asyncio.Queue()
        id = self._num_connections
        self._num_connections += 1
        self._connections[id] = q
        event_source = EventSourceResponse(self._subscribe(request, id, q))
        return (event_source, id)

    async def send_to_single(self, id: int, data: ServerSentEvent):
        await self._connections[id].put(data)

    async def broadcast_to_all(self, data: ServerSentEvent):
        await self._sse_queue.put(data)

    async def _subscribe(self, request: Request, id: int, q: asyncio.Queue):
        try:
            while True:
                if await request.is_disconnected():
                    logger.info(f"Client with ID {id} has disconnected")
                    self._connections.pop(id)
                    await request.close()
                    break
                else:
                    data = await q.get()
                    yield data
        except asyncio.CancelledError as e:
            logger.info(f"CancelledError on client with ID {id}: {e}")
            self._connections.pop(id)
            await request.close()

    async def _broadcast_data_sse(self):
        while True:
            try:
                async with async_timeout.timeout(1):
                    msg = await self._sse_queue.get()
                    if msg is not None:
                        for k in self._connections.keys():
                            if self._connections.get(k):
                                await self._connections.get(k).put(msg)
                    await asyncio.sleep(0.01)
            except asyncio.TimeoutError:
                pass
