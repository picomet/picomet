import base64
import os
import re
import sys
from collections.abc import Callable
from copy import deepcopy
from functools import wraps
from glob import glob
from html import unescape
from html.parser import HTMLParser
from itertools import chain
from json import JSONEncoder, dumps, loads
from pathlib import Path
from typing import Any, Literal, TypedDict, TypeVar, cast, override

from django.apps import apps
from django.conf import settings
from django.template import engines, loader
from django.template.backends.django import Template
from django.utils.html import escape

from picomet.helpers import get_comet_id
from picomet.types import (
    Ast,
    AstAttrs,
    AstElement,
    CodeAttrs,
    DoubleQuoteEscapedStr,
    ElementDoubleTag,
    PureAttrs,
    StrCode,
    isNodeElement,
    isNodeWithChildrens,
)
from picomet.utils import escape_double_quote as edq
from picomet.utils import get_atrb, mdhash, set_atrb

tagfind_tolerant = re.compile(r"([a-zA-Z][^\t\n\r\f />\x00]*)(?:\s|/(?!>))*")
attrfind_tolerant = re.compile(
    r'((?<=[\'"\s/])[^\s/>][^\s/=>]*)(\s*=+\s*'
    r'(\'[^\']*\'|"[^"]*"|(?![\'"])[^>\s]*))?(?:\s|/(?!>))*'
)
endendtag = re.compile(">")
endtagfind = re.compile(r"</\s*([a-zA-Z][-.a-zA-Z0-9:_]*)\s*>")


class BaseHTMLParser(HTMLParser):
    # Internal -- handle starttag, return end or -1 if not terminated
    @override
    def parse_starttag(self, i: int) -> int:
        self.__starttag_text = None
        endpos = self.check_for_whole_start_tag(i)
        if endpos < 0:
            return endpos
        rawdata = self.rawdata
        self.__starttag_text = rawdata[i:endpos]

        # Now parse the data between i+1 and j into a tag and attrs
        attrs = []
        match = tagfind_tolerant.match(rawdata, i + 1)
        assert match, "unexpected call to parse_starttag()"
        k = match.end()
        self.lasttag = tag = match.group(1)
        while k < endpos:
            m = attrfind_tolerant.match(rawdata, k)
            if not m:
                break
            attrname, rest, attrvalue = m.group(1, 2, 3)
            if not rest:
                attrvalue = None
            elif (
                attrvalue[:1] == "'" == attrvalue[-1:]
                or attrvalue[:1] == '"' == attrvalue[-1:]
            ):
                attrvalue = attrvalue[1:-1]
            if attrvalue:
                attrvalue = unescape(attrvalue)
            attrs.append((attrname, attrvalue))
            k = m.end()

        end = rawdata[k:endpos].strip()
        if end not in (">", "/>"):
            lineno, offset = self.getpos()
            if "\n" in self.__starttag_text:
                lineno = lineno + self.__starttag_text.count("\n")
                offset = len(self.__starttag_text) - self.__starttag_text.rfind("\n")
            else:
                offset = offset + len(self.__starttag_text)
            self.handle_data(rawdata[i:endpos])
            return endpos
        if end.endswith("/>"):
            # XHTML-style empty tag: <span attr="value" />
            self.handle_startendtag(tag, attrs)
        else:
            self.handle_starttag(tag, attrs)
            if tag in self.CDATA_CONTENT_ELEMENTS:
                self.set_cdata_mode(tag)
        return endpos

    # Internal -- parse endtag, return end or -1 if incomplete
    @override
    def parse_endtag(self, i: int) -> int:
        rawdata = self.rawdata
        assert rawdata[i : i + 2] == "</", "unexpected call to parse_endtag"
        match = endendtag.search(rawdata, i + 1)  # >
        if not match:
            return -1
        gtpos = match.end()
        match = endtagfind.match(rawdata, i)  # </ + tag + >
        if not match:
            if self.cdata_elem is not None:
                self.handle_data(rawdata[i:gtpos])
                return gtpos
            # find the name: w3.org/TR/html5/tokenization.html#tag-name-state
            namematch = tagfind_tolerant.match(rawdata, i + 2)
            if not namematch:
                # w3.org/TR/html5/tokenization.html#end-tag-open-state
                if rawdata[i : i + 3] == "</>":
                    return i + 3
                else:
                    return self.parse_bogus_comment(i)
            tagname = namematch.group(1)
            # consume and ignore other stuff between the name and the >
            # Note: this is not 100% correct, since we might have things like
            # </tag attr=">">, but looking for > after the name should cover
            # most of the cases and is much simpler
            gtpos = rawdata.find(">", namematch.end())
            self.handle_endtag(tagname)
            return gtpos + 1

        elem = match.group(1)  # script or style
        if self.cdata_elem is not None:
            if elem != self.cdata_elem:
                self.handle_data(rawdata[i:gtpos])
                return gtpos

        self.handle_endtag(elem)
        self.clear_cdata_mode()
        return gtpos


ltrim_re = re.compile(r"^(\s|\n|\t)+")
rtrim_re = re.compile(r"(\s|\n|\t)+$")

x_re = re.compile(
    r"(?:(?:({\$)\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*\$})|(({{)\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*}})|({%\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*%}))"
)

BUILD = len(sys.argv) > 1 and sys.argv[1] == "build"
COLLECTSTATIC = len(sys.argv) > 1 and sys.argv[1] == "collectstatic"
RUNSERVER = len(sys.argv) > 1 and sys.argv[1] == "runserver"
TEST = len(sys.argv) > 1 and sys.argv[1] == "test"
RECOMPILE = len(sys.argv) > 1 and sys.argv[1] == "recompile"

DEBUG: bool = settings.DEBUG
BASE_DIR: Path = settings.BASE_DIR
STATIC_URL = getattr(settings, "STATIC_URL", "/static/")
ASSETFILES_DIRS = getattr(settings, "ASSETFILES_DIRS", [])

django_engine = engines["django"]

picomet_dir = BASE_DIR / ".picomet"
cache_dir = picomet_dir / "cache"
build_dir = picomet_dir / "build"
assets_dir = (build_dir if (TEST | BUILD | COLLECTSTATIC) else cache_dir) / "assets"

ast_cache: dict[str, Ast] = {}

asset_cache: dict[str, tuple[str, str]] = {}
if not (BUILD | RECOMPILE):
    try:
        with (
            picomet_dir / ("cache" if RUNSERVER else "build") / "assets.json"
        ).open() as f:
            asset_cache = loads(f.read())
    except FileNotFoundError:
        pass

dgraph: dict[str, list[str]] = {}
if RUNSERVER:
    try:
        with (cache_dir / "dgraph.json").open() as f:
            dgraph = loads(f.read())
    except FileNotFoundError:
        pass

twlayouts: dict[str, str] = {}
if RUNSERVER:
    try:
        with (cache_dir / "twlayouts.json").open() as f:
            twlayouts = loads(f.read())
    except FileNotFoundError:
        pass


def save_dgraph() -> None:
    with open(cache_dir / "dgraph.json", "w") as f:
        f.write(dumps(dgraph))


def save_asset_cache() -> None:
    with open(picomet_dir / ("build" if BUILD else "cache") / "assets.json", "w") as f:
        f.write(dumps(asset_cache))


def save_commet(path: str, ast: Ast, folder: Path) -> None:
    _ast = deepcopy(ast)

    def process(node: AstElement) -> None:
        try:
            del node["parent"]  # type: ignore
        except KeyError:
            pass
        if isNodeWithChildrens(node):
            for index, children in enumerate(node["childrens"]):
                if isNodeElement(children):
                    if BUILD:
                        if children["tag"] == "Tailwind":
                            fname = asset_cache[
                                cast(str, get_atrb(children, "layout"))
                            ][0]
                            node["childrens"][index] = {
                                "tag": "link",
                                "attrs": [
                                    ("rel", "stylesheet"),
                                    ("href", f"{STATIC_URL}{fname}"),
                                ],
                            }
                    process(children)
                elif isinstance(children, str):
                    if not settings.DEBUG and node["tag"] != "pre":
                        clean = children
                        if index == 0:
                            clean = re.sub(ltrim_re, "", clean)
                        if index == (len(node["childrens"]) - 1):
                            clean = re.sub(rtrim_re, "", clean)
                        node["childrens"][index] = clean

    process(_ast)

    dest = folder / f"{get_comet_id(path)}.json"
    with dest.open("w") as f:

        class AstEncoder(JSONEncoder):
            def default(self, obj: Any) -> Any:
                if isinstance(obj, StrCode):
                    return {
                        "StrCode": True,
                        "string": obj.string,
                        "filename": obj.filename,
                    }
                elif isinstance(obj, Template):
                    return {"DTL": True, "string": obj.template.source}
                return super().default(obj)

        f.write(dumps(_ast, cls=AstEncoder))


def load_comet(path: str, folder: Path) -> None:
    source = folder / f"{get_comet_id(path)}.json"
    if source.exists():
        with source.open() as f:

            def ast_decoder(_dict: dict) -> dict | StrCode | Template:
                if _dict.get("StrCode"):
                    return StrCode(_dict["string"], _dict["filename"])
                elif _dict.get("DTL"):
                    return django_engine.from_string(_dict["string"])
                return _dict

            ast = loads(f.read(), object_hook=ast_decoder)

            def process(node: AstElement) -> None:
                if isNodeWithChildrens(node):
                    for children in node["childrens"]:
                        if isNodeElement(children):
                            children["parent"] = node  # type: ignore
                            process(children)

            process(ast)

            ast_cache[path] = ast


class Map(TypedDict):
    groups: dict[str, list[list[int]]]
    params: dict[str, list[list[int]]]
    files: dict[str, list[list[int]]]


R = TypeVar("R")


def handle_addition(func: Callable[..., R]) -> Callable[..., R]:
    @wraps(func)
    def wrapper(self: "CometParser", *args: list[Any]) -> None:
        if self.in_debug and not settings.DEBUG:
            return
        if self.in_pro and settings.DEBUG:
            return
        if self.is_page and not self.in_layout:
            return
        func(self, *args)

    return cast(Callable[..., R], wrapper)


class CometParser(BaseHTMLParser):
    def __init__(self, *args: list[Any], **kwargs: dict[str, bool]):
        super().__init__()
        self.ast: Ast = {
            "tag": "Fragment",
            "attrs": [],
            "childrens": [],
            "parent": None,
            "map": {"groups": {}, "params": {}, "files": {}},
            "file": "",
        }
        self.imports: dict[str, str] = {}
        self.loc: list[int] = []
        self.current: Ast | ElementDoubleTag = self.ast
        self.is_layout: bool = False
        self.is_page: bool = False
        self.in_layout: bool = False
        self.in_debug: bool = False
        self.in_pro: bool = False
        self.id: str = ""

    @override  # type: ignore
    def feed(self, data: str, id: str, use_cache: bool = True) -> None:
        self.id = id
        cached = ast_cache.get(id)
        if use_cache and not cached and not (BUILD or RECOMPILE):
            load_comet(id, (cache_dir if RUNSERVER else build_dir) / "comets")
        cached = ast_cache.get(id)

        if not cached or not use_cache:
            for d1 in dgraph:
                for i, d2 in enumerate(dgraph[d1]):
                    if d2 == id:
                        del dgraph[d1][i]
            self.ast["file"] = id
            self.ast["map"]["files"].setdefault(id, [[]])
            super().feed(data)
            ast_cache[id] = self.ast
            if not BUILD:
                save_commet(id, self.ast, cache_dir / "comets")
                save_dgraph()
        else:
            self.ast = cached

    @override
    @handle_addition
    def handle_starttag(self, tag: str, attrs: PureAttrs) -> None:
        element: ElementDoubleTag
        if tag == "Debug":
            self.in_debug = True
        elif tag == "Pro":
            self.in_pro = True
        elif (
            tag == "Layout"
            and self.current is self.ast
            and not len(self.ast["childrens"])
        ):
            self.is_page = True
            self.in_layout = True
            component = get_atrb(attrs, "@")
            if len(os.path.basename(str(component)).split(".")) == 1:
                component = f"{component}.html"
            template = loader.get_template(component, using="picomet").template
            id = template.origin.name
            parser = CometParser()
            parser.feed(template.source, id)
            self.add_dep(id, self.id)
            ast = deepcopy(self.ast)
            self.ast = deepcopy(parser.ast)
            loc = self.find_loc("Outlet", self.ast, [])
            if loc:
                el: Ast | ElementDoubleTag = self.ast
                for _l in loc:
                    el = cast(Ast | ElementDoubleTag, el["childrens"][_l])
                el["childrens"].append(ast)
                self.loc = loc + [0]
                for file in ast["map"]["files"]:
                    for _loc in ast["map"]["files"][file]:
                        self.ast["map"]["files"].setdefault(file, [])
                        self.ast["map"]["files"][file].append(self.loc + _loc)
                self.current = ast
        elif (
            self.imports.get(tag)
            or engines["picomet"].engine.components.get(tag)
            or (tag == "Include")
        ):
            component = (
                self.imports.get(tag)
                or engines["picomet"].engine.components.get(tag)
                or get_atrb(attrs, "@")
            )
            if isinstance(component, str):
                if len(os.path.basename(component).split(".")) == 1:
                    component = f"{component}.html"
                template = loader.get_template(component, using="picomet").template
                id = template.origin.name
                parser = CometParser()
                parser.feed(template.source, id)
                ast = deepcopy(parser.ast)
                self.add_props(
                    ast,
                    self.process_attrs(
                        [(k, v) for k, v in attrs if k != "@" and not k.startswith(".")]
                    ),
                )
                self.add_dep(id, self.id)
                element = {
                    "tag": "With",
                    "attrs": cast(
                        AstAttrs,
                        self.withs([(k[1:], v) for k, v in attrs if k.startswith(".")]),
                    ),
                    "childrens": [ast],
                    "parent": self.current,
                }
                self.current["childrens"].append(element)
                ast["parent"] = element
                self.load_component_map(ast["map"])

                childrenLoc = self.find_loc("Children", ast, [])
                childrenElement = self.find_node("Children", element, [])
                if childrenLoc and childrenElement:
                    self.loc = (
                        self.loc + [len(self.current["childrens"]), 0] + childrenLoc
                    )
                    self.current = cast(ElementDoubleTag, childrenElement)
        else:
            attributes: AstAttrs
            if tag == "With":
                attributes = cast(AstAttrs, self.withs(attrs))
            elif tag == "Default":
                attributes = cast(AstAttrs, self.defaults(attrs))
            else:
                attributes = self.process_attrs(attrs)
            self.loc.append(len(self.current["childrens"]))
            element = {
                "tag": tag,
                "attrs": attributes,
                "childrens": [],
                "parent": self.current,
            }
            self.current["childrens"].append(element)
            self.current = element
            self.add_map(attributes, self.loc.copy())

    @override
    @handle_addition
    def handle_startendtag(self, tag: str, attrs: PureAttrs) -> None:
        if tag.startswith("Import."):
            component = get_atrb(attrs, "@")
            if component:
                self.imports[tag[7:]] = str(component)
        elif tag == "Outlet":
            self.current["childrens"].append(
                {
                    "tag": tag,
                    "attrs": cast(AstAttrs, attrs),
                    "childrens": [],
                    "parent": self.current,
                }
            )
        elif tag == "Children":
            self.current["childrens"].append(
                {
                    "tag": tag,
                    "attrs": cast(AstAttrs, attrs),
                    "childrens": [],
                    "parent": self.current,
                }
            )
        elif (
            self.imports.get(tag)
            or engines["picomet"].engine.components.get(tag)
            or (tag == "Include")
        ):
            component = (
                self.imports.get(tag)
                or engines["picomet"].engine.components.get(tag)
                or get_atrb(attrs, "@")
            )
            if isinstance(component, str):
                if len(os.path.basename(component).split(".")) == 1:
                    component = f"{component}.html"
                template = loader.get_template(component, using="picomet").template
                id = template.origin.name
                parser = CometParser()
                parser.feed(template.source, id)
                ast = deepcopy(parser.ast)
                self.add_dep(id, self.id)
                self.add_props(
                    ast,
                    self.process_attrs(
                        [(k, v) for k, v in attrs if k != "@" and not k.startswith(".")]
                    ),
                )
                element: ElementDoubleTag = {
                    "tag": "With",
                    "attrs": cast(
                        AstAttrs,
                        self.withs([(k[1:], v) for k, v in attrs if k.startswith(".")]),
                    ),
                    "childrens": [ast],
                    "parent": self.current,
                }
                self.current["childrens"].append(element)
                ast["parent"] = element
                self.load_component_map(ast["map"])
        elif tag == "Group":
            self.current["childrens"].append(
                {
                    "tag": tag,
                    "attrs": cast(AstAttrs, attrs),
                    "childrens": [],
                    "parent": self.current,
                }
            )
        elif tag == "Js" or tag == "Ts" or tag == "Css" or tag == "Sass":
            asset_name = get_atrb(attrs, "@")
            if isinstance(asset_name, str):
                asset = find_in_comets(asset_name) or find_in_assets(asset_name)
                if asset:
                    self.add_dep(asset, self.id)
                    if not asset_cache.get(asset):
                        compile_asset(asset)
                    set_atrb(attrs, "@", cast(DoubleQuoteEscapedStr, asset))
                    self.current["childrens"].append(
                        {
                            "tag": tag,
                            "attrs": cast(AstAttrs, attrs),
                            "parent": self.current,
                        }
                    )
        elif tag == "Tailwind":
            if self.current["tag"] == "head":
                twlayouts[self.id] = str(get_atrb(attrs, "@"))
                if not BUILD:
                    with open(cache_dir / "twlayouts.json", "w") as f:
                        f.write(dumps(twlayouts))
                attrs.append(("layout", edq(self.id)))
                self.current["childrens"].append(
                    {
                        "tag": tag,
                        "attrs": cast(AstAttrs, attrs),
                        "parent": self.current,
                    }
                )
        else:
            attributes = self.process_attrs(attrs)
            self.current["childrens"].append(
                {"tag": tag, "attrs": attributes, "parent": self.current}
            )
            self.add_map(attributes, self.loc.copy() + [len(self.current["childrens"])])

    def handle_endtag(self, tag: str) -> None:
        if self.in_debug:
            if tag == "Debug":
                self.in_debug = False
                return
            elif not settings.DEBUG:
                return
        if self.in_pro:
            if tag == "Pro":
                self.in_pro = False
                return
            elif settings.DEBUG:
                return

        if tag == "Layout":
            self.in_layout = False
        elif (
            self.imports.get(tag)
            or engines["picomet"].engine.components.get(tag)
            or (tag == "Include")
        ):
            while True:
                if self.current["tag"] == "With":
                    break
                else:
                    if len(self.loc):
                        self.loc.pop(-1)
                    if self.current["parent"]:
                        self.current = self.current["parent"]
        if len(self.loc):
            self.loc.pop(-1)
        if self.current["parent"]:
            self.current = self.current["parent"]

    @handle_addition
    def handle_data(self, data: str) -> None:
        matches = list(re.finditer(x_re, data))
        if len(matches):
            previous = None
            for match in matches:
                self.current["childrens"].append(
                    data[previous if previous else 0 : match.start()]
                )
                groups = [group for group in (match.groups()) if group is not None]
                if groups[0] == "{$":
                    self.current["childrens"].append(StrCode(groups[1], self.id))
                elif groups[0].startswith("{{") or groups[0].startswith("{%"):
                    self.current["childrens"].append(
                        django_engine.from_string(groups[0])
                    )
                previous = match.end()
            if previous:
                self.current["childrens"].append(data[previous:])
        else:
            self.current["childrens"].append(data)

    def handle_decl(self, decl: str) -> None:
        self.is_layout = True
        self.current["childrens"].append(f"<!{decl}>")

    def handle_charref(self, name: str) -> None:
        print("Encountered a charref  :", name)

    def handle_entityref(self, name: str) -> None:
        print("Encountered an entityref  :", name)

    def handle_pi(self, data: str) -> None:
        print("Encountered a pi  :", data)

    def process_attrs(self, attrs: PureAttrs) -> AstAttrs:
        attributes: AstAttrs = []
        for k, v in attrs:
            if (
                k == "s-show"
                or k == "s-if"
                or k == "s-elif"
                or k == "s-in"
                or k == "s-of"
                or k == "s-key"
                or k == "s-text"
                or k.startswith("s-prop:")
                or k.startswith("s-bind:")
                or k.startswith("s-toggle:")
            ) and v is not None:
                attributes.append((k, self.compile(v)))
            elif k.startswith("s-asset:") and v is not None:
                asset = find_in_assets(v)
                if asset:
                    if not BUILD:
                        self.add_dep(asset, self.id)
                        attributes += [
                            (k, edq(asset)),
                            ("data-asset-id", edq(compile_resouce(asset))),
                            ("data-target", edq(k.split(":")[1])),
                        ]
                    else:
                        compile_resouce(asset)
                        attributes += [
                            (
                                k.split(":")[1],
                                edq(f"{STATIC_URL}{asset_cache[asset][0]}"),
                            )
                        ]
            elif k.startswith("s-static:"):
                attributes.append((k.split(":")[1], escape(settings.STATIC_URL + v)))
            elif k == "server" or k == "client":
                attributes.append(("mode", DoubleQuoteEscapedStr(k)))
            else:
                attributes.append((k, v))

        if self.current["tag"] == "Helmet":
            attributes.append(("x-head", None))

        return attributes

    def compile(self, v: str | DoubleQuoteEscapedStr) -> StrCode:
        return StrCode(v, self.id)

    def withs(self, attrs: PureAttrs) -> CodeAttrs:
        _withs: CodeAttrs = []
        for k, v in attrs:
            _withs.append(
                (
                    k,
                    self.compile("True") if v is None else self.compile(v),
                )
            )
        return _withs

    def defaults(self, attrs: PureAttrs) -> CodeAttrs:
        _defaults: CodeAttrs = []
        for k, v in attrs:
            if isinstance(v, str):
                _defaults.append((k, self.compile(v)))
        return _defaults

    def add_props(self, element: AstElement, props: AstAttrs) -> None:
        for index, attr in enumerate(element["attrs"]):
            if attr[0] == "s-props":
                element["attrs"] = list(
                    list(element["attrs"])[:index]
                    + list(props)
                    + list(element["attrs"])[index + 1 :]
                )
        if not isNodeWithChildrens(element):
            return
        element = cast(ElementDoubleTag, element)
        for children in element["childrens"]:
            if isNodeElement(children):
                self.add_props(children, props)

    def add_dep(self, component: str, dependent: str) -> None:
        dgraph.setdefault(component, [])
        if dependent not in dgraph[component]:
            dgraph[component].append(dependent)

    def add_map(self, attrs: AstAttrs, loc: list[int]) -> None:
        sgroup = get_atrb(attrs, "s-group")
        if isinstance(sgroup, str):
            for group in sgroup.split(","):
                self.ast["map"]["groups"].setdefault(group, [])
                self.ast["map"]["groups"][group].append(loc)
        sparam = get_atrb(attrs, "s-param")
        if isinstance(sparam, str):
            for param in sparam.split(","):
                self.ast["map"]["params"].setdefault(param, [])
                self.ast["map"]["params"][param].append(loc)

    def find_loc(
        self, tag: str, ast: AstElement, attrs: AstAttrs, loc: list[int] | None = None
    ) -> list[int] | None:
        loc = loc or []
        if ast["tag"] == tag:
            for attr in attrs:
                if not (get_atrb(ast, attr[0]) == attr[1]):
                    break
            else:
                return loc
        if "childrens" not in ast:
            return None
        ast = cast(ElementDoubleTag, ast)
        for index, children in enumerate(ast["childrens"]):
            if isinstance(children, dict):
                children = cast(AstElement, children)
                loc.append(index)
                _loc = self.find_loc(tag, children, attrs, loc=loc)
                if _loc:
                    return _loc
                loc.pop(-1)
        return None

    def find_node(
        self, tag: str, ast: AstElement, attrs: AstAttrs
    ) -> AstElement | None:
        if ast["tag"] == tag:
            for attr in attrs:
                if not (get_atrb(ast, attr[0]) == attr[1]):
                    break
            else:
                return ast
        if not isNodeWithChildrens(ast):
            return None
        for children in ast["childrens"]:
            if isNodeElement(children):
                node = self.find_node(tag, children, attrs)
                if node:
                    return node
        return None

    def load_component_map(self, map: Map) -> None:
        for target in map:
            target = cast(Literal["files", "groups", "params"], target)
            for id in map[target]:
                self.ast["map"][target].setdefault(id, [])
                self.ast["map"][target][id] += list(
                    [
                        (self.loc + [len(self.current["childrens"]) - 1, 0] + _loc)
                        for _loc in map[target][id]
                    ]
                )


sass_load_paths = [
    os.path.join(BASE_DIR, "assets"),
    *[os.path.join(app.path, "assets") for app in apps.get_app_configs()],
]


def compile_asset(path: str) -> str:
    from picomet.loaders import cache_file, fcache

    if not fcache.get(path):
        with open(path) as f:
            cache_file(path, f.read())

    name, ext = os.path.splitext(os.path.basename(path))
    compiled: str
    if ext == ".ts":
        from javascript import require

        compiled = (
            require("esbuild")
            .buildSync(
                {
                    "target": "es6",
                    "stdin": {
                        "contents": fcache[path],
                        "loader": "ts",
                    },
                    "write": False,
                    "minify": BUILD,
                }
            )
            .outputFiles[0]
            .text
        )
        ext = ".js"
    elif ext == ".scss":
        from javascript import require

        compiled = (
            require("sass")
            .compileString(
                fcache[path],
                {
                    "loadPaths": sass_load_paths,
                    "style": "compressed" if BUILD else "expanded",
                },
            )
            .css
        )
        ext = ".css"
    else:
        compiled = fcache[path]
    id = f"{name}-{mdhash(path,6)}"
    fname = f"{id}.{mdhash(compiled,6)}{ext}"
    asset_cache[path] = (fname, compiled)
    for file in glob(str(assets_dir / f"{id}.*{ext}")):
        if os.path.exists(str(file)):
            os.remove(str(file))
    with open(assets_dir / fname, "w") as f:
        f.write(compiled)
    save_asset_cache()

    return id


def compile_resouce(path: str) -> str:
    from picomet.loaders import cache_file, fcache

    if not fcache.get(path):
        with open(path, "rb") as f:
            cache_file(path, base64.b64encode(f.read()).decode("utf-8"))
    name, ext = os.path.splitext(os.path.basename(path))
    compiled = fcache[path]
    id = f"{name}-{mdhash(path,6)}"
    fname = f"{id}.{mdhash(compiled,6)}{ext}"
    asset_cache[path] = (fname, compiled)
    for file in glob(str(assets_dir / f"{id}.*{ext}")):
        if os.path.exists(str(file)):
            os.remove(str(file))
    with open(assets_dir / fname, "wb") as f:
        f.write(base64.b64decode(compiled))
    save_asset_cache()
    return id


def compile_tailwind(layout: str) -> None:
    source_id = twlayouts[layout]
    picomet_engine = engines["picomet"].engine
    input_css = picomet_engine.find_template(f"{source_id}.tailwind.css")[1].name
    tailwind_conf = picomet_engine.find_template(f"{source_id}.tailwind.js")[1].name
    postcss_conf = picomet_engine.find_template(f"{source_id}.postcss.js")[1].name

    content = []

    def traverse(f: str) -> None:
        if f not in content:
            content.append(f)
        for d1 in dgraph:
            for d2 in dgraph[d1]:
                if d2 == f:
                    traverse(d1)

    traverse(layout)

    for f in dgraph[layout]:
        traverse(f)

    from javascript import require

    css, fname, compiled = require("./tailwind.js").compile(
        input_css,
        tailwind_conf,
        postcss_conf,
        assets_dir.as_posix(),
        f"{os.path.basename(source_id)}-{mdhash(layout,6)}",
        content,
        DEBUG,
    )
    from picomet.loaders import cache_file

    cache_file(input_css, css)
    asset_cache[layout] = (fname, compiled)
    save_asset_cache()


def find_in_comets(name: str) -> str | None:
    comet_dirs = list(
        chain.from_iterable(
            [
                [str(d) for d in loader.get_dirs()]
                for loader in engines["picomet"].engine.template_loaders
            ]
        )
    )
    return find_in_dirs(name, comet_dirs)


def find_in_assets(name: str) -> str | None:
    asset_dirs = [
        *[str(d) for d in ASSETFILES_DIRS],
        *[os.path.join(app.path, "assets") for app in apps.get_app_configs()],
    ]
    return find_in_dirs(name, asset_dirs)


def find_in_dirs(name: str, dirs: list[str]) -> str | None:
    for d in dirs:
        directory = Path(d)
        if directory.is_dir():
            file = directory / name
            if file.exists():
                return file.as_posix()
    return None
