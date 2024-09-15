from hashlib import md5
from types import CodeType
from typing import Any

from picomet.types import (
    AstAttrs,
    DoubleQuoteEscapedStr,
    ElementWithAttrs,
    PureAttrs,
    StrCode,
)


def get_atrb(
    obj: ElementWithAttrs | AstAttrs | PureAttrs, name: str, default: str | bool = False
) -> DoubleQuoteEscapedStr | StrCode | None | str | bool:
    attrs: AstAttrs | PureAttrs
    if isinstance(obj, dict):
        attrs = obj["attrs"]
    else:
        attrs = obj
    return next(filter(lambda attr: attr[0] == name, attrs), [name, default])[1]


def set_atrb(
    attrs: list[tuple[str, Any]],
    name: str,
    value: DoubleQuoteEscapedStr | CodeType | None,
) -> None:
    for index, attr in enumerate(attrs):
        if attr[0] == name:
            attrs[index] = (name, value)
            return
    attrs.append((name, value))


def remove_atrb(attrs: list[tuple[str, Any]], name: str) -> None:
    for index, attr in enumerate(attrs):
        if attr[0] == name:
            del attrs[index]


def mdhash(string: str, length: int) -> str:
    return md5(string.encode()).hexdigest()[:length]


def escape_double_quote(s: str) -> DoubleQuoteEscapedStr:
    """
    Replace double quote (") character to HTML-safe sequence.
    """
    s = s.replace('"', "&quot;")
    return DoubleQuoteEscapedStr(s)
