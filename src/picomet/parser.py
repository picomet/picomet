import base64
import os
import re
import sys
from copy import deepcopy
from functools import cache
from glob import glob
from itertools import chain
from json import JSONEncoder, dumps, loads
from pathlib import Path
from typing import Any, Literal, cast

from django.apps import apps
from django.conf import settings
from django.template import engines, loader
from django.template.backends.django import Template
from django.utils.html import escape
from htmst import HtmlAst
from htmst.structures import (
    AttrNode,
    CommentNode,
    DoctypeNode,
    DoubleTagNode,
    SingleTagNode,
    TextNode,
)

from picomet.helpers import find_comet_name, get_comet_id
from picomet.types import (
    Ast,
    AstAttr,
    AstAttrs,
    AstElement,
    AstMap,
    ElementDoubleTag,
    ElementSingleTag,
    PureAttrs,
    StrCode,
    Undefined,
    UndefinedType,
    isNodeElement,
    isNodeWithChildren,
)
from picomet.types import DoubleQuoteEscapedStr as DQES
from picomet.utils import escape_double_quote as edq
from picomet.utils import get_atrb, get_span, mdhash

ltrim_re = re.compile(r"^(\s|\n|\t)+")
rtrim_re = re.compile(r"(\s|\n|\t)+$")

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

map_cache: dict[str, AstMap] = {}

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
        if isNodeWithChildren(node):
            for index, child in enumerate(node["children"]):
                if isNodeElement(child):
                    if BUILD:
                        if child["tag"] == "Tailwind":
                            fname = asset_cache[cast(str, get_atrb(child, "layout"))][0]
                            node["children"][index] = {
                                "tag": "link",
                                "attrs": [
                                    ("rel", "stylesheet", None),
                                    ("href", f"{STATIC_URL}{fname}", None),
                                ],
                            }
                    process(child)
                elif isinstance(child, str):
                    if not settings.DEBUG and node["tag"] != "pre":
                        clean = child
                        if index == 0:
                            clean = re.sub(ltrim_re, "", clean)
                        if index == (len(node["children"]) - 1):
                            clean = re.sub(rtrim_re, "", clean)
                        node["children"][index] = clean

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
                elif _dict.get("tag"):
                    for attr in _dict["attrs"]:
                        k, v, span = attr
                        if isinstance(v, str):
                            attr[1] = DQES(v)
                        elif isinstance(v, dict):
                            attr[1] = StrCode(v["string"], v["filename"])
                return _dict

            ast = loads(f.read(), object_hook=ast_decoder)

            def process(node: AstElement) -> None:
                if isNodeWithChildren(node):
                    for child in node["children"]:
                        if isNodeElement(child):
                            child["parent"] = node  # type: ignore
                            process(child)

            process(ast)

            ast_cache[path] = ast


def load_map(path: str, folder: Path) -> None:
    source = folder / f"{get_comet_id(path)}.json"
    if source.exists():
        with source.open() as f:
            map = loads(f.read())
            map_cache[path] = map


x_re = re.compile(
    r"(?:(?:({\$)\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*\$})|(({{)\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*}})|({%\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*%}))"
)


class CometParser:
    def __init__(self, source: str, path: str, use_cache: bool = True):
        self.ast: Ast = {
            "tag": "Fragment",
            "attrs": [],
            "children": [],
            "parent": None,
            "file": path,
            "isBase": False,
        }
        self.map: AstMap = {"groups": {}, "params": {}, "layouts": {}, "files": {}}
        self.imports: dict[str, str] = {}
        self.current: Ast | ElementDoubleTag = self.ast
        self.path = path

        ast_cached = ast_cache.get(path)
        map_cached = map_cache.get(path)
        if use_cache and (not ast_cached or not map_cache) and not (BUILD or RECOMPILE):
            load_comet(path, (cache_dir if RUNSERVER else build_dir) / "comets")
            load_map(path, (cache_dir if RUNSERVER else build_dir) / "maps")
        ast_cached = ast_cache.get(path)
        map_cached = map_cache.get(path)

        if (not ast_cached or not map_cached) or not use_cache:
            for d1 in dgraph:
                for i, d2 in enumerate(dgraph[d1]):
                    if d2 == path:
                        del dgraph[d1][i]
            self.handle_children(HtmlAst(source).root.children)
            ast_cache[path] = self.ast
            Mapper(self.ast, path)
            if BUILD:
                if not twlayouts.get(path):
                    save_commet(path, self.ast, build_dir / "comets")
            else:
                save_dgraph()
                save_commet(path, self.ast, cache_dir / "comets")
        else:
            self.ast = ast_cached
            self.map = map_cached

    @property
    @cache
    def name(self) -> str | None:
        return find_comet_name(self.path)

    def handle_children(
        self,
        children: list[
            DoubleTagNode | SingleTagNode | TextNode | CommentNode | DoctypeNode
        ],
    ) -> None:
        for child in children:
            match child:
                case DoubleTagNode():
                    self.handle_doubletag(child)
                case SingleTagNode():
                    self.handle_singletag(child)
                case TextNode():
                    self.handle_text(child)
                case CommentNode():
                    self.handle_comment(child)
                case DoctypeNode():
                    self.handle_doctype(child)

    def handle_doubletag(self, node: DoubleTagNode) -> None:
        tag = node.tag
        attrs = node.attrs
        attributes: AstAttrs
        if tag == "Debug":
            if DEBUG:
                self.handle_children(node.children)
        elif tag == "Pro":
            if not DEBUG:
                self.handle_children(node.children)
        elif (
            tag == "Layout"
            and self.current is self.ast
            and not len(self.ast["children"])
        ):
            component = str(self.get_atrb(attrs, "@"))
            if len(os.path.basename(component).split(".")) == 1:
                component = f"{component}.html"
            template = loader.get_template(component, using="picomet").template
            path = template.origin.name
            parse(template.source, path)
            self.add_dep(path, self.path)
            elLayout: ElementDoubleTag = {
                "tag": "Layout",
                "attrs": self.convert_attrs(attrs),
                "children": [],
                "parent": self.current,
                "span": get_span(node),
            }
            elPage: ElementDoubleTag = {
                "tag": "Fragment",
                "attrs": [],
                "children": [],
                "parent": elLayout,
                "file": self.ast.pop("file"),
            }
            elLayout["children"].append(elPage)

            self.current["children"].append(elLayout)
            self.current = elPage
            self.handle_children(node.children)
            self.current = elLayout["parent"]
        elif (
            self.imports.get(tag)
            or engines["picomet"].engine.components.get(tag)
            or (tag == "Include")
        ):
            component = str(
                self.imports.get(tag)
                or engines["picomet"].engine.components.get(tag)
                or self.get_atrb(attrs, "@")
            )
            if len(os.path.basename(component).split(".")) == 1:
                component = f"{component}.html"
            template = loader.get_template(component, using="picomet").template
            path = template.origin.name
            parse(template.source, path)
            self.add_dep(path, self.path)
            attributes = self.process_attrs(attrs)
            if self.get_atrb(attrs, "@") is Undefined:
                attributes = [AstAttr("@", edq(component), None)] + attributes
            elInclude: ElementDoubleTag = {
                "tag": "Include",
                "attrs": self.process_props(attributes),
                "children": [],
                "parent": self.current,
                "span": get_span(node),
            }
            self.current["children"].append(elInclude)
            self.current = elInclude
            self.handle_children(node.children)
            self.current = self.current["parent"]
        else:
            if tag == "With":
                attributes = self.withs(attrs)
            elif tag == "Default":
                attributes = self.defaults(attrs)
            else:
                attributes = self.process_attrs(attrs)
            element: ElementDoubleTag = {
                "tag": tag,
                "attrs": attributes,
                "children": [],
                "parent": self.current,
                "span": get_span(node),
            }
            self.current["children"].append(element)
            self.current = element
            self.handle_children(node.children)
            self.current = self.current["parent"]

    def handle_singletag(self, node: SingleTagNode) -> None:
        tag = node.tag
        attrs = node.attrs
        elInclude: ElementSingleTag
        if tag == "Outlet":
            attributes: AstAttrs = []
            if self.name:
                layout = edq(mdhash(self.name, 8))
                attributes.append(AstAttr("layout", layout, None))
            elOutlet: ElementDoubleTag = {
                "tag": "Outlet",
                "attrs": attributes,
                "children": [],
                "parent": self.current,
            }
            elInclude = {
                "tag": "Children",
                "attrs": [],
                "parent": elOutlet,
                "span": get_span(node),
            }
            elOutlet["children"].append(elInclude)
            self.current["children"].append(elOutlet)
        elif tag == "Children":
            self.current["children"].append(
                {
                    "tag": tag,
                    "attrs": self.convert_attrs(attrs),
                    "parent": self.current,
                    "span": get_span(node),
                }
            )
        elif tag.startswith("Import."):
            component = self.get_atrb(attrs, "@")
            if component:
                self.imports[tag[7:]] = str(component)
        elif (
            self.imports.get(tag)
            or engines["picomet"].engine.components.get(tag)
            or (tag == "Include")
        ):
            component = (
                self.imports.get(tag)
                or engines["picomet"].engine.components.get(tag)
                or self.get_atrb(attrs, "@")
            )
            if isinstance(component, str):
                if len(os.path.basename(component).split(".")) == 1:
                    component = f"{component}.html"
                template = loader.get_template(component, using="picomet").template
                path = template.origin.name
                parse(template.source, path)
                self.add_dep(path, self.path)
                attributes = self.process_attrs(attrs)
                if self.get_atrb(attrs, "@") is Undefined:
                    attributes = [AstAttr("@", edq(component), None)] + attributes
                elInclude = {
                    "tag": "Include",
                    "attrs": self.process_props(attributes),
                    "parent": self.current,
                    "span": get_span(node),
                }
                self.current["children"].append(elInclude)
        elif tag == "Group":
            self.current["children"].append(
                {
                    "tag": tag,
                    "attrs": self.convert_attrs(attrs),
                    "children": [],
                    "parent": self.current,
                    "span": get_span(node),
                }
            )
        elif tag == "Js" or tag == "Ts" or tag == "Css" or tag == "Sass":
            asset_name = self.get_atrb(attrs, "@")
            if isinstance(asset_name, str):
                asset = find_in_comets(asset_name) or find_in_assets(asset_name)
                if asset:
                    self.add_dep(asset, self.path)
                    if not asset_cache.get(asset):
                        compile_asset(asset)
                    attributes = self.convert_attrs(attrs)
                    self.set_atrb(attributes, "@", DQES(asset))
                    self.current["children"].append(
                        {
                            "tag": tag,
                            "attrs": attributes,
                            "parent": self.current,
                        }
                    )
        elif tag == "Tailwind":
            if self.current["tag"] == "head":
                twlayouts[self.path] = str(self.get_atrb(attrs, "@"))
                if not BUILD:
                    with open(cache_dir / "twlayouts.json", "w") as f:
                        f.write(dumps(twlayouts))
                attributes = self.convert_attrs(attrs)
                attributes = [AstAttr("layout", edq(self.path), None)] + attributes
                self.current["children"].append(
                    {
                        "tag": tag,
                        "attrs": attributes,
                        "parent": self.current,
                    }
                )
        else:
            attributes = self.process_attrs(attrs)
            self.current["children"].append(
                {"tag": tag, "attrs": attributes, "parent": self.current}
            )

    def handle_text(self, node: TextNode) -> None:
        text = node.text
        matches = list(re.finditer(x_re, text))
        if len(matches):
            previous = None
            for match in matches:
                self.current["children"].append(
                    text[previous if previous else 0 : match.start()]
                )
                groups = [group for group in (match.groups()) if group is not None]
                if groups[0] == "{$":
                    self.current["children"].append(StrCode(groups[1], self.path))
                elif groups[0].startswith("{{") or groups[0].startswith("{%"):
                    self.current["children"].append(
                        django_engine.from_string(groups[0])
                    )
                previous = match.end()
            if previous:
                self.current["children"].append(text[previous:])
        else:
            self.current["children"].append(text)

    def handle_doctype(self, node: DoctypeNode) -> None:
        self.ast["isBase"] = True
        self.current["children"].append(f"<!doctype {node.text}>")

    def handle_comment(self, node: CommentNode) -> None:
        self.current["children"].append(f"<!-- {node.text} -->")

    def get_atrb(
        self, attrs: list[AttrNode], name: str, default: str | UndefinedType = Undefined
    ) -> str | None | UndefinedType:
        for attr in attrs:
            if attr.name == name:
                return attr.value
        return default

    def convert_attrs(self, attrs: list[AttrNode]) -> AstAttrs:
        attributes: AstAttrs = []
        for attr in attrs:
            attributes.append(
                AstAttr(attr.name, self.convert_value(attr.value), get_span(attr))
            )
        return attributes

    def convert_value(self, value: str | None) -> DQES | None:
        if value is None:
            return None
        return edq(value)

    def set_atrb(
        self,
        attrs: AstAttrs,
        name: str,
        value: DQES | StrCode | None,
    ) -> None:
        for index, attr in enumerate(attrs):
            if attr[0] == name:
                attrs[index] = AstAttr(name, value, None)
                return
        attrs.append(AstAttr(name, value, None))

    def process_attrs(self, attrs: list[AttrNode]) -> AstAttrs:
        attributes: AstAttrs = []
        for attr in attrs:
            k = attr.name
            v = attr.value
            if (
                k in ["s-show", "s-if", "s-elif", "s-in", "s-of", "s-key", "s-text"]
                or k.startswith("s-prop:")
                or k.startswith("s-bind:")
                or k.startswith("s-toggle:")
                or k.startswith("x-prop:")
            ) and v is not None:
                attributes += [AstAttr(k, self.compile(v), get_span(attr))]
            elif k.startswith("s-asset:") and v is not None:
                asset = find_in_assets(v)
                if asset:
                    if not BUILD:
                        self.add_dep(asset, self.path)
                        attributes += [
                            AstAttr(k, edq(asset), get_span(attr)),
                            AstAttr(
                                "data-asset-id",
                                edq(compile_resouce(asset)),
                                get_span(attr),
                            ),
                            AstAttr(
                                "data-target", edq(k.split(":")[1]), get_span(attr)
                            ),
                        ]
                    else:
                        compile_resouce(asset)
                        attributes += [
                            AstAttr(
                                k.split(":")[1],
                                edq(f"{STATIC_URL}{asset_cache[asset][0]}"),
                                get_span(attr),
                            )
                        ]
            elif k.startswith("s-static:"):
                attributes.append(
                    AstAttr(
                        k.split(":")[1], escape(settings.STATIC_URL + v), get_span(attr)
                    )
                )
            elif k == "server" or k == "client":
                attributes.append(AstAttr("mode", DQES(k), get_span(attr)))
            elif (k.startswith("x-") or k.startswith("@")) and isinstance(v, str):
                sprop = r"\$S\(`([^`]+)`\)"
                for match in re.finditer(sprop, v):
                    expression = match.group(1)
                    name = re.sub(r"[^\w\d_]", "_", expression).lower()
                    attributes.append(
                        AstAttr(f"s-prop:{name}", self.compile(expression), None)
                    )
                    v = v.replace(match.group(0), name)
                xprop = r"\$X\(`([^`]+)`\)"
                for match in re.finditer(xprop, v):
                    expression = match.group(1)
                    name = re.sub(r"[^\w\d_]", "_", expression).lower()
                    attributes.append(
                        AstAttr(f"x-prop:{name}", self.compile(expression), None)
                    )
                    v = v.replace(match.group(0), name)
                attributes.append(AstAttr(k, self.convert_value(v), get_span(attr)))
            else:
                attributes.append(AstAttr(k, self.convert_value(v), get_span(attr)))

        if self.current["tag"] == "Helmet":
            attributes.append(AstAttr("x-head", None, None))

        return attributes

    def process_props(self, attrs: AstAttrs) -> AstAttrs:
        _props: AstAttrs = []
        for attr in attrs:
            k, v, span = attr
            if isinstance(v, str) and k.startswith("."):
                _props.append(
                    AstAttr(
                        k, self.compile("True") if v is None else self.compile(v), span
                    )
                )
            else:
                _props.append(attr)
        return _props

    def compile(self, v: str | DQES) -> StrCode:
        return StrCode(v, self.path)

    def withs(self, attrs: list[AttrNode]) -> AstAttrs:
        _withs: AstAttrs = []
        for attr in attrs:
            k = attr.name
            v = attr.value
            _withs.append(
                AstAttr(
                    k,
                    self.compile("True") if v is None else self.compile(v),
                    get_span(attr),
                )
            )
        return _withs

    def defaults(self, attrs: list[AttrNode]) -> AstAttrs:
        _defaults: AstAttrs = []
        for attr in attrs:
            k = attr.name
            v = attr.value
            if isinstance(v, str):
                _defaults.append(AstAttr(k, self.compile(v), get_span(attr)))
        return _defaults

    def add_dep(self, component: str, dependent: str) -> None:
        dgraph.setdefault(component, [])
        if dependent not in dgraph[component]:
            dgraph[component].append(dependent)


def parse(source: str, path: str, use_cache: bool = True) -> CometParser:
    return CometParser(source, path, use_cache)


class Mapper:
    def __init__(self, ast: Ast, path: str) -> None:
        self.ast: Ast = ast
        self.path: str = path
        self.map: AstMap = {"groups": {}, "params": {}, "layouts": {}, "files": {}}
        self.map_node(ast)

        map_cache[path] = self.map

        maps_dir = (build_dir if BUILD else cache_dir) / "maps"
        dest = maps_dir / f"{get_comet_id(path)}.json"
        with dest.open("w") as f:
            f.write(dumps(self.map))

    def map_node(self, node: AstElement, loc: list[int] = []) -> None:
        tag = node["tag"]
        comet: str
        file = node.get("file")
        if isinstance(file, str):
            self.map["files"].setdefault(file, [])
            self.map["files"][file].append(loc.copy())

        self.map_group_n_param(node["attrs"], loc)
        if isNodeWithChildren(node):
            if tag in ["Layout", "Include"]:
                at = get_atrb(node, "@")
                if isinstance(at, str):
                    comet = at
                    if not comet.endswith(".html"):
                        comet = f"{comet}.html"
                    template = loader.get_template(comet, using="picomet").template
                    parser = parse(template.source, template.origin.name)
                    self.load_map(parser.map, loc)
                    children = self.find_loc("Children", parser.ast, [])
                    if children:
                        for index, child in enumerate(node["children"]):
                            if isNodeElement(child):
                                self.map_node(child, loc + children + [index])
                return
            elif tag == "Outlet":
                layout = get_atrb(node, "layout")
                if isinstance(layout, str):
                    self.map["layouts"].setdefault(layout, [])
                    self.map["layouts"][layout] = loc.copy()
                return

            for index, child in enumerate(node["children"]):
                if isNodeElement(child):
                    self.map_node(child, loc + [index])
        elif tag == "Include":
            at = get_atrb(node, "@")
            if isinstance(at, str):
                comet = at
                if not comet.endswith(".html"):
                    comet = f"{comet}.html"
                template = loader.get_template(comet, using="picomet").template
                parser = parse(template.source, template.origin.name)
                self.load_map(parser.map, loc)

    def find_loc(
        self, tag: str, ast: AstElement, attrs: PureAttrs, loc: list[int] | None = None
    ) -> list[int] | None:
        loc = loc or []
        if ast["tag"] == tag:
            for attr in attrs:
                if not (get_atrb(ast, attr[0]) == attr[1]):
                    break
            else:
                return loc
        if "children" not in ast:
            return None
        ast = cast(ElementDoubleTag, ast)
        for index, child in enumerate(ast["children"]):
            if isinstance(child, dict):
                child = cast(AstElement, child)
                loc.append(index)
                _loc = self.find_loc(tag, child, attrs, loc=loc)
                if _loc:
                    return _loc
                loc.pop(-1)
        return None

    def find_node(
        self, tag: str, ast: AstElement, attrs: PureAttrs
    ) -> AstElement | None:
        if ast["tag"] == tag:
            for attr in attrs:
                if not (get_atrb(ast, attr[0]) == attr[1]):
                    break
            else:
                return ast
        if not isNodeWithChildren(ast):
            return None
        for child in ast["children"]:
            if isNodeElement(child):
                node = self.find_node(tag, child, attrs)
                if node:
                    return node
        return None

    def map_group_n_param(self, attrs: AstAttrs, loc: list[int]) -> None:
        sgroup = get_atrb(attrs, "s-group")
        if isinstance(sgroup, str):
            for group in sgroup.split(","):
                self.map["groups"].setdefault(group, [])
                self.map["groups"][group].append(loc.copy())
        sparam = get_atrb(attrs, "s-param")
        if isinstance(sparam, str):
            for param in sparam.split(","):
                self.map["params"].setdefault(param, [])
                self.map["params"][param].append(loc.copy())

    def load_map(self, map: AstMap, loc: list[int]) -> None:
        for target in map:
            if target in ["files", "groups", "params"]:
                target = cast(Literal["files", "groups", "params"], target)
                for id in map[target]:
                    self.map[target].setdefault(id, [])
                    self.map[target][id] += list(
                        [(loc + _loc) for _loc in map[target][id]]
                    )
        layouts = map["layouts"]
        for id in layouts:
            self.map["layouts"][id] = loc + layouts[id]


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

    def find_depending(f: str) -> None:
        if f not in content:
            content.append(f)
        for d1 in dgraph:
            for d2 in dgraph[d1]:
                if d2 == f:
                    find_depending(d1)

    def find_depended(f: str) -> None:
        if f not in content:
            content.append(f)
        for d in dgraph.get(f, []):
            find_depended(d)
            find_depending(d)

    find_depending(layout)
    find_depended(layout)

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


def find_in_comets(name: str | DQES) -> str | None:
    comet_dirs = list(
        chain.from_iterable(
            [
                [str(d) for d in loader.get_dirs()]
                for loader in engines["picomet"].engine.template_loaders
            ]
        )
    )
    return find_in_dirs(name, comet_dirs)


def find_in_assets(name: str | DQES) -> str | None:
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
