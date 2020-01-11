import argparse
import ipaddress
import pyperclip
import websockets
import asyncio
import pathlib
import uri as urilib
from typing import Any, Callable, Tuple, Type, Union, Optional, AsyncIterator
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
    uri = urilib.URI(scheme="ws", host=str(ip), port=port, path="/clipboard")
    async def send():
        async with websockets.connect(str(uri)) as websocket:
            await websocket.send(message=pyperclip.paste())
    
    asyncio.run(send())

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
    
    start_server = websockets.serve(root_handler,
                                    network, 
                                    port)
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