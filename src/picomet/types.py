from types import CodeType
from typing import Self, TypedDict, Union, cast, overload

from django.template.backends.django import Template
from typing_extensions import TypeIs


class StrCode:
    def __init__(self, string: str, filename: str):
        self.string = string
        self.filename = filename
        self.code: CodeType = compile(string, filename, "eval")


class DoubleQuoteEscapedStr(str):
    @overload  # type: ignore
    def __add__(self, rhs: Self) -> Self:
        return cast(Self, super().__add__(rhs))


type Loops = list[tuple[str, int]]

type PureAttrs = list[tuple[str, DoubleQuoteEscapedStr | None]]
type CodeAttrs = list[tuple[str, StrCode]]
type AstAttrValue = DoubleQuoteEscapedStr | StrCode | None
type AstAttr = tuple[str, AstAttrValue]
type AstAttrs = list[AstAttr]
type EscapedAttr = tuple[str, DoubleQuoteEscapedStr | None]
type EscapedAttrs = list[EscapedAttr]

type AstElement = Union[Ast, ElementDoubleTag, ElementSingleTag]  # noqa: UP007
type AstNode = Ast | ElementDoubleTag | ElementSingleTag | str | StrCode | Template


class ElementDoubleTag(TypedDict):
    tag: str
    attrs: AstAttrs
    childrens: list[AstNode]
    parent: "ElementDoubleTag | Ast"


class ElementSingleTag(TypedDict):
    tag: str
    attrs: AstAttrs
    parent: "ElementDoubleTag | Ast"


class AstMap(TypedDict):
    groups: dict[str, list[list[int]]]
    params: dict[str, list[list[int]]]
    files: dict[str, list[list[int]]]


class Ast(TypedDict):
    tag: str
    attrs: AstAttrs
    childrens: list[AstNode]
    parent: ElementDoubleTag | None
    map: AstMap
    file: str


class ElementWithAttrs(TypedDict):
    attrs: AstAttrs


def isNodeElement(node: AstNode) -> TypeIs[AstElement]:
    return isinstance(node, dict)


def isNodeWithChildrens(node: AstNode) -> TypeIs[Ast | ElementDoubleTag]:
    if isNodeElement(node):
        return "childrens" in node
    return False


def isAtrbEscaped(attr: AstAttr) -> TypeIs[EscapedAttr]:
    k, v = attr
    if isinstance(v, str) or v is None:
        return True
    return False
