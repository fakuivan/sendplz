import argparse
import ipaddress
import pyperclip
import websockets
import asyncio
import pathlib
import uri as urilib
import datetime
import functools
from typing import Any, Callable, Tuple, Type, Union, Optional, AsyncIterator, cast, IO
from datetime import date
wscp = websockets.WebSocketClientProtocol

from utils import cast_and_check, IPAddress, IPInterface, register_ws_urls
register_ws_urls(urilib)

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Simple network clipboard and file transfer using websockets")
    subparsers = parser.add_subparsers()
    subparsers.required = True
    send_parser = subparsers.add_parser("send", help="Run program in send mode")
    send_parser.add_argument("--ip", type=ip_arg_parser, required=True,
                             help="IP address of the reciever", dest="send_ip")
    send_parser.add_argument("--port", type=port_parser, required=True,
                             help="Port open on the reciever", dest="send_port")
    send_parser.add_argument("--file", type=argparse.FileType(mode="rb"), default=None,
                             help="File to send to reciever", dest="file")
    send_parser.set_defaults(func=sender_handler)
    recieve_parser = subparsers.add_parser("recieve", help="Run program in listen mode")
    recieve_parser.add_argument("--net", type=str, required=False,
                                help="IP network to listen to", dest="network")
    recieve_parser.add_argument("--port", type=port_parser, required=True,
                                help="Port to listen on", dest="listen_port")
    recieve_parser.set_defaults(func=reciever_handler)
    args = parser.parse_args()
    handler = cast_and_check(args.func, Union[sender_handler, reciever_handler])
    handler(args)

def sender_handler(args: argparse.Namespace):
    ip = cast_and_check(args.send_ip, IPAddress)
    port = cast_and_check(args.send_port, int)
    file = cast_and_check(args.file, Optional[IO])
    uri = urilib.URI(scheme="ws", host=str(ip), port=port)
    async def send_clipboard():
        async with websockets.connect(str(uri / "clipboard")) as websocket:
            await websocket.send(message=pyperclip.paste())

    async def send_file():
        async with websockets.connect(str(uri / "file")) as websocket:
            await websocket.send(message=pathlib.Path(file.name).name)
            file_iter = iter(functools.partial(file.read, 1024 * 1024 * 8), b'')
            for chunk in file_iter:
                #print("sending chunk...")
                await websocket.send(chunk)
            await websocket.send("end")

    
    asyncio.run(send_clipboard() if file is None else send_file())

def reciever_handler(args: argparse.Namespace):
    network = cast_and_check(args.network, str)
    port = cast_and_check(args.listen_port, int)
    
    async def root_handler(
        websocket: websockets.WebSocketServerProtocol,
        path: str
    ) -> Any:
        if path == "/clipboard":
            clipboard = await websocket.recv()
            if not isinstance(clipboard, str): return
            pyperclip.copy(clipboard)
            # :TODO: I should definitely use a logger for this
            print(f"Clipboard set to {repr(clipboard)} from {websocket.remote_address}")
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
            print(f"Written {written} bytes to file {repr(filename)} from{websocket.remote_address}")
            print(f"Transfer took {delta.seconds} seconds with an average packet size of {written // packets} bytes")
            print(f"Average transfer speed was {(written / delta.seconds) / 1024**2} Mb/s")
    
    start_server = websockets.serve(root_handler,
                                    network, 
                                    port,
                                    max_size=None)
    asyncio.get_event_loop().run_until_complete(start_server)
    asyncio.get_event_loop().run_forever()


def ip_arg_parser(input_: str) -> IPAddress:
    try:
        return ipaddress.ip_address(input_)
    except ValueError as error:
        raise argparse.ArgumentTypeError(str(error))

def port_parser(input_: str) -> int:
    try:
        value = int(input_)
        if not 1 <= value <= 65535:
            raise ValueError()
        return value
    except ValueError:
        raise argparse.ArgumentTypeError(f"{repr(input)} is not a valid port number")


if __name__ == "__main__": main()