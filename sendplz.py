import click
import pyperclip
import websockets
import asyncio
import pathlib
import uri as urilib
import datetime
import functools
import protocol
from typing import Any, Optional, BinaryIO, Callable, ContextManager
import typeguard
from contextlib import contextmanager
wscp = websockets.WebSocketClientProtocol

from utils import cast_and_check, IPAddress, IPInterface, register_ws_urls
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
        reader = lambda: (pathlib.Path(file.name).name,
                          iter(functools.partial(file.read, 1024 * 1024 * 8), b''))
        protocol.send_file(ip, port, reader)
    else:
        protocol.send_clipboard(ip, port, pyperclip.paste())


class CLISessionHanlder(protocol.SessionHandler):
    def __init__(self):
        self.address: Optional[str] = None
        self.file_handle: Optional[BinaryIO] = None

    @property
    def initialized(self) -> bool:
        return self.address is not None

    def ip_authenticate(self, address: str) -> bool:
        self.address = address
        click.echo(f"Authenticated address {repr(address)}")
        return True

    def set_clipboard(self, clipboard: str) -> None:
        pyperclip.copy(clipboard)
        click.echo(f"Clipboard set to {repr(clipboard)} by {repr(self.address)}")

    def open_file(self, filename: str, estimated_size: Optional[int]) -> \
        ContextManager[Callable[[bytes], None]]:
        click.echo(f"Remote {repr(self.address)} requested to write to file {repr(filename)}")
        @contextmanager
        def manager():
            try:
                file = cast_and_check(
                    open("./" + pathlib.Path(filename).name, mode="wb"), BinaryIO)
                def write(payload: bytes):
                    assert file.write(payload) == len(payload)
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
    protocol.listen(CLISessionHanlder, network, port)

if __name__ == "__main__": cli()