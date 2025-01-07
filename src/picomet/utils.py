from hashlib import md5
from types import CodeType
from typing import Any, Protocol

from htmst.structures import Pos

from picomet.types import (
    AstAttrs,
    AstAttrsDynamic,
    AstElWithAttrs,
    Span,
    StrCode,
    Undefined,
    UndefinedType,
)
from picomet.types import (
    DoubleQuoteEscapedStr as DQES,
)


def has_atrb(attrs: AstAttrs | AstAttrsDynamic, names: list[str]) -> bool:
    for k, v, span in attrs:
        if k in names:
            return True
    return False


def get_atrb(
    obj: AstElWithAttrs | AstAttrs,
    name: str,
    default: DQES | UndefinedType = Undefined,
) -> DQES | StrCode | None | UndefinedType:
    attrs: AstAttrs
    if isinstance(obj, dict):
        attrs = obj["attrs"]
    else:
        attrs = obj
    for attr in attrs:
        if attr[0] == name:
            return attr[1]
    return default


def set_atrb(
    attrs: list[tuple[str, Any]],
    name: str,
    value: DQES | CodeType | None,
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


class Node(Protocol):
    start: Pos
    end: Pos


def get_span(node: Node) -> Span:
    return {
        "start": node.start.to_json(),
        "end": node.end.to_json(),
    }


def mdhash(string: str, length: int) -> str:
    return md5(string.encode()).hexdigest()[:length]


def escape_double_quote(s: str) -> DQES:
    """
    Replace double quote (") characters to HTML-safe sequence.
    """
    s = s.replace('"', "&quot;")
    return DQES(s)
