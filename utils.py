from typing import Generic, TypeVar, Any, Type, Union, cast, Iterator, AsyncIterator
from typeguard import check_type
import ipaddress

IPInterface = Union[ipaddress.IPv4Interface,
                    ipaddress.IPv6Interface]
IPAddress = Union[ipaddress.IPv4Address,
                  ipaddress.IPv6Address]

def register_ws_urls(uri):
    uri.URI.scheme.registry["ws"] = uri.scheme.URLScheme("ws")
    uri.URI.scheme.registry["wss"] = uri.scheme.URLScheme("wss")
    same_uri = lambda uri_: str(uri.URI(uri_)) == uri_
    assert same_uri("ws://localhost:8080/")
    assert same_uri("wss://localhost:8080/")

T = TypeVar("T")

def cast_and_check(obj: Any, type_: Type[T], var_name: str="passed") -> T:
    check_type(var_name, obj, type_)
    return cast(type_, obj)


def wrap_aiter(iterator: Iterator[T]) -> AsyncIterator[T]:
    class AIter(AsyncIterator[T], Generic[T]):
        def __init__(self, iter_: Iterator[T]):
            self.parent = iter_
        def __aiter__(self):
            return self
        async def __anext__(self):
            try:
                return next(self.parent)
            except StopIteration:
                raise StopAsyncIteration
    return AIter(iterator)