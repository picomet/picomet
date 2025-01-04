from collections.abc import Iterable, Iterator
from types import CodeType
from typing import NamedTuple, NotRequired, Self, TypedDict, cast, overload

from django.template.backends.django import Template
from typing_extensions import TypeIs


class UndefinedType:
    def __str__(self) -> str:
        return "Undefined"

    def __repr__(self) -> str:
        return "Undefined"

    def __bool__(self) -> bool:
        return False


Undefined = UndefinedType()


class StrStore:
    __slots__ = ("value",)

    def __init__(self, value: str):
        self.value: str = value

    def __str__(self) -> str:
        return self.value


class StrCode:
    __slots__ = ("string", "filename", "code")

    def __init__(self, string: str, filename: str):
        self.string: str = string
        self.filename: str = filename
        self.code: CodeType = compile(string, filename, "eval")


class DoubleQuoteEscapedStr(str):
    @overload  # type: ignore
    def __add__(self, rhs: Self) -> Self:
        return cast(Self, super().__add__(rhs))


class Position(TypedDict):
    row: int
    col: int


class Span(TypedDict):
    start: Position
    end: Position


type Loops = list[tuple[str, int]]

type PureAttrs = list[tuple[str, DoubleQuoteEscapedStr | None]]
type AstAttrValue = DoubleQuoteEscapedStr | StrCode | None


class AstAttr(NamedTuple):
    key: str
    val: AstAttrValue
    span: Span | None


type AstAttrs = list[AstAttr]


class AstAttrsIterator(Iterator[AstAttr]):
    def __init__(self, array: AstAttrs, insert: AstAttrs):
        self.array: AstAttrs = array
        self.insert: AstAttrs = insert
        self.array_position = 0
        self.inserting = False
        self.insert_position = 0

    def __next__(self) -> AstAttr:
        if self.inserting:
            if self.insert_position == len(self.insert):
                self.inserting = False
                self.insert_position = 0
                self.array_position += 1
                return self.__next__()
            value = self.insert[self.insert_position]
            self.insert_position += 1
            return value
        else:
            if self.array_position == len(self.array):
                self.array_position = 0
                raise StopIteration
            value = self.array[self.array_position]
            if value[0] == "s-props":
                self.inserting = True
                return self.__next__()
            self.array_position += 1
            return value


class AstAttrsDynamic(Iterable[AstAttr]):
    def __init__(self, array: AstAttrs, insert: AstAttrs):
        self.array: AstAttrs = array
        self.insert: AstAttrs = insert

    def __iter__(self) -> AstAttrsIterator:
        return AstAttrsIterator(self.array, self.insert)

    def __getitem__(self, index: int) -> AstAttr:
        for i, attr in enumerate(self):
            if i == index:
                return attr
        raise IndexError


type EscapedAttr = tuple[str, DoubleQuoteEscapedStr | None]
type EscapedAttrs = list[EscapedAttr]

type AstElement = Ast | ElementDoubleTag | ElementSingleTag
type AstNode = Ast | ElementDoubleTag | ElementSingleTag | str | StrCode | Template


class ElementDoubleTag(TypedDict):
    tag: str
    attrs: AstAttrs
    children: list[AstNode]
    span: NotRequired[Span]
    parent: "ElementDoubleTag | Ast"
    file: NotRequired[str]


class ElementSingleTag(TypedDict):
    tag: str
    attrs: AstAttrs
    span: Span
    parent: "ElementDoubleTag | Ast"


class AstMap(TypedDict):
    groups: dict[str, list[list[int]]]
    params: dict[str, list[list[int]]]
    layouts: dict[str, list[int]]
    files: dict[str, list[list[int]]]


class Ast(TypedDict):
    tag: str
    attrs: AstAttrs
    children: list[AstNode]
    parent: ElementDoubleTag | None
    file: NotRequired[str]
    isBase: bool


class AstElWithAttrs(TypedDict):
    attrs: AstAttrs


def isNodeElement(node: AstNode) -> TypeIs[AstElement]:
    return isinstance(node, dict)


def isNodeWithChildren(node: AstNode) -> TypeIs[Ast | ElementDoubleTag]:
    if isNodeElement(node):
        return "children" in node
    return False
