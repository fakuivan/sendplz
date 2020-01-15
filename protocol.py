import websockets
import uri as urilib
from typing import (Awaitable, Callable, AsyncContextManager, Coroutine, Optional, 
                    Any, Protocol, Type, Optional, Tuple, AsyncIterator)

from utils import register_ws_urls
register_ws_urls(urilib)

async def send_clipboard(ip: str, port: int, clipboard: str) -> None:
    uri = urilib.URI(scheme="ws", host=str(ip), port=port) / "clipboard"
    async with websockets.connect(str(uri)) as websocket:
        await websocket.send(message=clipboard)

async def send_file(ip: str, port: int,
                    reader: AsyncContextManager[Tuple[str, AsyncIterator[bytes]]]) -> None:
    uri = urilib.URI(scheme="ws", host=str(ip), port=port) / "file"
    async with websockets.connect(str(uri)) as websocket:
        async with reader as (filename, stream):
            await websocket.send(message=filename)
            async for chunk in stream:
                await websocket.send(chunk)
        await websocket.send("")


class SessionHandler(Protocol):
    async def ip_authenticate(self, address: str) -> bool: ...
    async def set_clipboard(self, clipboard: str) -> None: ...
    def open_file(self, filename: str, estimated_size: Optional[int]) -> \
        AsyncContextManager[Callable[[bytes], Awaitable[None]]]: ...


async def listen(session_handler: Callable[[], SessionHandler],
                 network: str, port: int) -> None:
    async def ahandler(
        websocket: websockets.WebSocketServer,
        path: str
    ) -> Any:
        session = session_handler()
        if not await session.ip_authenticate(websocket.remote_address):
            return
        if path == "/clipboard":
            clipboard: str = await websocket.recv()
            if not isinstance(clipboard, str):
                return
            await session.set_clipboard(clipboard)
        elif path == "/file":
            filename: str = await websocket.recv()
            if not isinstance(filename, str):
                return
            async with session.open_file(filename, None) as file_writer:
                while isinstance((payload := await websocket.recv()), bytes):
                    await file_writer(payload)

    await websockets.serve(ahandler,
                           network,
                           port,
                           max_size=None)
