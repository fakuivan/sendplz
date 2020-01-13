import websockets
import asyncio
import uri as urilib
from typing import (Callable, ContextManager, Iterator, Optional, 
                    Any, Protocol, Type, Optional, Tuple)

from utils import register_ws_urls
register_ws_urls(urilib)

def send_clipboard(ip: str, port: int, clipboard: str):
    uri = urilib.URI(scheme="ws", host=str(ip), port=port) / "clipboard"
    async def asend():
        async with websockets.connect(str(uri)) as websocket:
            await websocket.send(message=clipboard)
    asyncio.run(asend())

def send_file(ip: str, port: int,
              reader: Callable[[], Tuple[str, Iterator[bytes]]]):
    uri = urilib.URI(scheme="ws", host=str(ip), port=port) / "file"
    async def asend():
        async with websockets.connect(str(uri)) as websocket:
            filename, stream = reader()
            await websocket.send(message=filename)
            for chunk in stream:
                await websocket.send(chunk)
            await websocket.send("")
    asyncio.run(asend())
    

class SessionHandler(Protocol):
    def __init__(self) -> None: ...
    def ip_authenticate(self, address: str) -> bool: ...
    def set_clipboard(self, clipboard: str) -> None: ...
    def fatal_error(self) -> None: ...
    def write_file(self, filename: str, estimated_size: Optional[int]) -> \
        Callable[[Optional[bytes]], None]: ...
    def open_file(self, filename: str, estimated_size: Optional[int]) -> \
        ContextManager[Callable[[bytes], None]]: ...


def listen(session_handler: Type[SessionHandler],
           network: str, port: int) -> Any:
    async def ahandler(
        websocket: websockets.WebSocketServer,
        path: str
    ) -> Any:
        session = session_handler()
        if not session.ip_authenticate(websocket.remote_address):
            return
        if path == "/clipboard":
            clipboard: str = await websocket.recv()
            if not isinstance(clipboard, str):
                session.fatal_error()
                return
            session.set_clipboard(clipboard)
        elif path == "/file":
            filename: str = await websocket.recv()
            if not isinstance(filename, str):
                session.fatal_error()
            with session.open_file(filename, None) as file_writer:
                while isinstance((payload := await websocket.recv()), bytes):
                    file_writer(payload)

    start_server = websockets.serve(ahandler,
                                    network,
                                    port,
                                    max_size=None)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()
