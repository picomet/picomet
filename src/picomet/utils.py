from hashlib import md5
from types import CodeType
from typing import Any, Self, overload


def get_attr[T](obj: dict | list, name: str, default: T = False):
    if isinstance(obj, dict):
        attrs = obj["attrs"]
    elif isinstance(obj, list):
        attrs = obj
    return next(filter(lambda attr: attr[0] == name, attrs), [name, default])[1]


def set_attr(attrs: list[tuple[str, Any]], name: str, value: str | CodeType | None):
    for index, attr in enumerate(attrs):
        if attr[0] == name:
            attrs[index] = (name, value)
            return
    attrs.append((name, value))


def remove_attr(attrs: list[tuple[str, Any]], name: str):
    for index, attr in enumerate(attrs):
        if attr[0] == name:
            del attrs[index]


def mdhash(string: str, length: int):
    return md5(string.encode()).hexdigest()[:length]


class DoubleQuoteEscapedStr(str):
    @overload
    def __add__(self, rhs: Self) -> Self: ...
    @overload
    def __add__(self, rhs: str) -> str: ...
    @overload
    def __iadd__(self, rhs: Self) -> Self: ...
    @overload
    def __iadd__(self, rhs: str) -> str: ...


def escape_double_quote(s: str):
    """
    Replace double quote (") character to HTML-safe sequence.
    """
    s = s.replace('"', "&quot;")
    return DoubleQuoteEscapedStr(s)
