import click
import pyperclip
import websockets
import asyncio
import pathlib
import uri as urilib
import datetime
import functools
from typing import Any, Callable, Tuple, Type, Union, Optional, AsyncIterator, cast, IO
from datetime import date
import typeguard
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
def send(ip: str, port: int, file: Optional[IO] = None):
    """Run program in send mode"""

    uri = urilib.URI(scheme="ws", host=str(ip), port=port)
    async def send_clipboard():
        async with websockets.connect(str(uri / "clipboard")) as websocket:
            await websocket.send(message=pyperclip.paste())

    async def send_file():
        async with websockets.connect(str(uri / "file")) as websocket:
            await websocket.send(message=pathlib.Path(file.name).name)
            file_iter = iter(functools.partial(file.read, 1024 * 1024 * 8), b'')
            for chunk in file_iter:
                await websocket.send(chunk)
            await websocket.send("end")

    
    asyncio.run(send_clipboard() if file is None else send_file())

@cli.command()
@click.argument("network")
@click.argument("port", type=port_type)
@typeguard.typechecked
def recieve(network: str, port: int):
    """Run program in listen mode"""
    
    async def root_handler(
        websocket: websockets.WebSocketServerProtocol,
        path: str
    ) -> Any:
        click.echo(f"Recieved connection from {websocket.remote_address} with path {path}")
        if path == "/clipboard":
            clipboard = await websocket.recv()
            if not isinstance(clipboard, str): return
            pyperclip.copy(clipboard)
            # :TODO: I should definitely use a logger for this
            click.echo(f"Clipboard set to {repr(clipboard)} from {websocket.remote_address}")
        elif path == "/file":
            prev = datetime.datetime.now()
            filename: str = await websocket.recv()
            if not isinstance(filename, str): return
            filename = pathlib.Path(filename).name
            written = 0
            packets = 0
            with open("./"+filename, mode="xb") as fileio:
                while isinstance((payload := await websocket.recv()), bytes):
                    written += len(payload)
                    packets += 1
                    #print(f"Writing payload {repr(payload)}")
                    fileio.write(payload)
                fileio.flush()
            delta = datetime.datetime.now() - prev
            click.echo(f"Written {written} bytes to file {repr(filename)} from {websocket.remote_address}")
            click.echo(f"Transfer took {delta.seconds} seconds with an average packet size of {written // packets} bytes")
            click.echo(f"Average transfer speed was {(written / delta.seconds) / 1024**2} Mb/s")
    
    start_server = websockets.serve(root_handler,
                                    network, 
                                    port,
                                    max_size=None)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


if __name__ == "__main__": cli()