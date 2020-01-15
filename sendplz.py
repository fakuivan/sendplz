from io import BytesIO
import click
import pyperclip
import websockets
import asyncio
import pathlib
import uri as urilib
import functools
import protocol
from typing import Awaitable, Optional, BinaryIO, Callable, AsyncContextManager
import typeguard
from contextlib import asynccontextmanager
wscp = websockets.WebSocketClientProtocol

from utils import cast_and_check, register_ws_urls, wrap_aiter
register_ws_urls(urilib)

@click.group()
def cli():
    """Simple network clipboard and file transfer using websockets"""
    pass

port_type = click.IntRange(min=1, max=65535)

@cli.command()
@click.argument("ip")
@click.argument("port", type=port_type)
@click.option("--file", "-f", type=click.File(mode="rb"))
@typeguard.typechecked
def send(ip: str, port: int, file: Optional[BinaryIO] = None):
    """Run program in send mode"""

    if file is not None:
        @asynccontextmanager
        async def reader(file: BytesIO):
            yield (pathlib.Path(file.name).name,
                   wrap_aiter(iter(functools.partial(file.read, 1024 * 1024 * 8), b'')))
        sender = protocol.send_file(ip, port, reader(file))
    else:
        sender = protocol.send_clipboard(ip, port, pyperclip.paste())

    asyncio.run(sender)


class CLISessionHanlder(protocol.SessionHandler):
    def __init__(self):
        self.address: Optional[str] = None
        self.file_handle: Optional[BinaryIO] = None

    @property
    def initialized(self) -> bool:
        return self.address is not None

    async def ip_authenticate(self, address: str) -> bool:
        self.address = address
        click.echo(f"Authenticated address {address!r}")
        return True

    async def set_clipboard(self, clipboard: str) -> None:
        pyperclip.copy(clipboard)
        click.echo(f"Clipboard set to {clipboard!r} by {self.address!r}")

    def open_file(self, filename: str, estimated_size: Optional[int]) -> \
        AsyncContextManager[Callable[[bytes], Awaitable[None]]]:
        click.echo(f"Remote {self.address!r} requested to write to file {filename!r}")
        @asynccontextmanager
        async def manager():
            file = cast_and_check(
                open("./" + pathlib.Path(filename).name, mode="xb"), BinaryIO)
            async def write(payload: bytes):
                assert file.write(payload) == len(payload)
            try:
                yield write
            finally:
                file.close()
        return manager()

    def fatal_error(self) -> None:
        pass

    def __del__(self):
        if self.initialized:
            click.echo(f"Session closed for address {self.address}")


@cli.command()
@click.argument("network")
@click.argument("port", type=port_type)
@typeguard.typechecked
def recieve(network: str, port: int):
    """Run program in listen mode"""
    click.echo(f"Running server in listen mode ({network!r}, {port})")
    asyncio.get_event_loop().run_until_complete(
        protocol.listen(CLISessionHanlder, network, port))
    asyncio.get_event_loop().run_forever()

if __name__ == "__main__": cli()