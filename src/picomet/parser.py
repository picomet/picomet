import functools
import os
import re
import sys
from copy import deepcopy
from glob import glob
from html import unescape
from html.parser import HTMLParser
from itertools import chain
from json import JSONEncoder, dumps, loads
from pathlib import Path
from types import CodeType
from typing import TypedDict, override

from django.apps import apps
from django.conf import settings
from django.template import engines, loader
from django.template.backends.django import Template
from django.utils.html import escape

from picomet.utils import get_attr, mdhash, set_attr

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
    def parse_starttag(self, i):
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
    def parse_endtag(self, i):
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


class StrCode:
    def __init__(self, string: str, filename: str):
        self.string = string
        self.filename = filename
        self.code: CodeType = compile(string, filename, "eval")


trim_re = re.compile(r"(^(\s|\n|\t)+|(\s|\n|\t)+$)")

x_re = re.compile(
    r"(?:(?:({\$)\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*\$})|(({{)\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*}})|({%\s*((?:\"(?:\\\"|[^\"])*\"|'(?:\\'|[^'])*'|[^\"'\n])*?)\s*%}))"
)

type PureAttrs = list[tuple[str, str | None]]
type AstAttrs = list[tuple[str, str | StrCode | None]]
type Codes = list[tuple[str, StrCode]]
type AstNode = Element | Ast | str | StrCode | Template


class Element(TypedDict):
    tag: str | None
    attrs: AstAttrs
    childrens: list[AstNode] | None
    parent: "Element | Ast"


class AstMap(TypedDict):
    groups: dict[str, list[list[int]]]
    params: dict[str, list[list[int]]]
    files: dict[str, list[list[int]]]


class Ast(TypedDict):
    tag: None
    attrs: list
    childrens: list[AstNode]
    parent: None
    map: AstMap
    file: str


BUILD = sys.argv[1] == "build"
RUNSERVER = sys.argv[1] == "runserver"
RECOMPILE = sys.argv[1] == "recompile"

DEBUG: bool = settings.DEBUG
BASE_DIR: Path = settings.BASE_DIR
ASSET_URL = getattr(settings, "ASSET_URL", "assets/")
ASSETFILES_DIRS = getattr(settings, "ASSETFILES_DIRS", [])

django_engine = engines["django"]

picomet_dir = BASE_DIR / ".picomet"
cache_dir = picomet_dir / "cache"
build_dir = picomet_dir / "build"
assets_dir = (build_dir if BUILD else cache_dir) / "assets"

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


def save_asset_cache():
    with open(picomet_dir / ("build" if BUILD else "cache") / "assets.json", "w") as f:
        f.write(dumps(asset_cache))


def save_commet(id: str, ast: Ast, dest: Path):
    _ast = deepcopy(ast)

    def process(node: Ast | Element):
        try:
            del node["parent"]
        except KeyError:
            pass
        for index, children in enumerate(node.get("childrens", [])):
            if isinstance(children, dict):
                if BUILD:
                    if children["tag"] == "Tailwind":
                        fname = asset_cache[get_attr(children, "layout")][0]
                        node["childrens"][index] = {
                            "tag": "link",
                            "attrs": [
                                ("rel", "stylesheet"),
                                ("href", f"/{ASSET_URL}{fname}"),
                            ],
                        }
                process(children)

    process(_ast)
    with (dest / f"{mdhash(id,8)}.json").open("w") as f:

        class AstEncoder(JSONEncoder):
            def default(self, obj):
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


def load_comet(id: str, source: Path):
    comet = source / f"{mdhash(id,8)}.json"
    if comet.exists():
        with comet.open() as f:

            def ast_decoder(_dict):
                if _dict.get("StrCode"):
                    return StrCode(_dict["string"], _dict["filename"])
                elif _dict.get("DTL"):
                    return django_engine.from_string(_dict["string"])
                return _dict

            ast_cache[id] = loads(f.read(), object_hook=ast_decoder)


class CometParser(BaseHTMLParser):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.ast: Ast = {
            "tag": None,
            "attrs": [],
            "childrens": [],
            "parent": None,
            "map": {"groups": {}, "params": {}, "files": {}},
        }
        self.imports: dict[str, str] = {}
        self.loc: list[int] = []
        self.current: Ast | Element = self.ast
        self.is_layout: bool = False
        self.is_page: bool = False
        self.in_layout: bool = False
        self.in_debug: bool = False

    @override
    def feed(self, data: str, id: str, use_cache: bool = True):
        self.id = id
        cached = ast_cache.get(id)
        if use_cache and not cached and not (BUILD or RECOMPILE):
            load_comet(id, (cache_dir if RUNSERVER else build_dir) / "comets")
        cached = ast_cache.get(id)

        if not use_cache or (use_cache and not cached):
            for f in dgraph:
                for i, d in enumerate(dgraph[f]):
                    if d == id:
                        del dgraph[f][i]
            self.ast["file"] = id
            self.ast["map"]["files"].setdefault(id, [[]])
            super().feed(data)
            ast_cache[id] = self.ast
            if not BUILD:
                save_commet(id, self.ast, cache_dir / "comets")
                with open(cache_dir / "dgraph.json", "w") as f:
                    f.write(dumps(dgraph))
        else:
            self.ast = cached

    def handle_addition(func):
        @functools.wraps(func)
        def wrapper(self: "CometParser", *args):
            if self.in_debug and not DEBUG:
                return
            if self.is_page and not self.in_layout:
                return
            func(self, *args)

        return wrapper

    @handle_addition
    def handle_starttag(self, tag, attrs):
        if tag == "Debug":
            self.in_debug = True
        elif (
            tag == "Layout"
            and self.current is self.ast
            and not len(self.ast["childrens"])
        ):
            self.is_page = True
            self.in_layout = True
            component = get_attr(attrs, "@")
            if len(os.path.basename(component).split(".")) == 1:
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
                el = self.ast
                for _loc in loc:
                    el = el["childrens"][_loc]
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
                or get_attr(attrs, "@")
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
                self.current["childrens"].append(
                    {
                        "tag": "With",
                        "attrs": self.withs(
                            [(k[1:], v) for k, v in attrs if k.startswith(".")]
                        ),
                        "childrens": [ast],
                        "parent": self.current,
                    }
                )
                ast["parent"] = self.current["childrens"][-1]
                self.load_component_map(ast["map"])

                self.loc = (
                    self.loc
                    + [len(self.current["childrens"]), 0]
                    + self.find_loc("Children", ast, [])
                )
                self.current = self.find_node(
                    "Children", self.current["childrens"][-1], []
                )
        else:
            if tag == "With":
                attributes = self.withs(attrs)
            elif tag == "Default":
                attributes = self.defaults(attrs)
            else:
                attributes = self.process_attrs(attrs)
            self.loc.append(len(self.current["childrens"]))
            self.current["childrens"].append(
                {
                    "tag": tag,
                    "attrs": attributes,
                    "childrens": [],
                    "parent": self.current,
                }
            )
            self.current = self.current["childrens"][-1]
            self.add_map(attributes, self.loc.copy())

    @handle_addition
    def handle_startendtag(self, tag, attrs):
        if tag.startswith("Import."):
            component = get_attr(attrs, "@")
            if component:
                self.imports[tag[7:]] = component
        elif tag == "Outlet":
            self.current["childrens"].append(
                {"tag": tag, "attrs": attrs, "childrens": [], "parent": self.current}
            )
        elif tag == "Children":
            self.current["childrens"].append(
                {"tag": tag, "attrs": attrs, "childrens": [], "parent": self.current}
            )
        elif (
            self.imports.get(tag)
            or engines["picomet"].engine.components.get(tag)
            or (tag == "Include")
        ):
            component = (
                self.imports.get(tag)
                or engines["picomet"].engine.components.get(tag)
                or get_attr(attrs, "@")
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
                self.current["childrens"].append(
                    {
                        "tag": "With",
                        "attrs": self.withs(
                            [(k[1:], v) for k, v in attrs if k.startswith(".")]
                        ),
                        "childrens": [ast],
                        "parent": self.current,
                    }
                )
                ast["parent"] = self.current["childrens"][-1]
                self.load_component_map(ast["map"])
        elif tag == "Group":
            self.current["childrens"].append(
                {
                    "tag": tag,
                    "attrs": attrs,
                    "childrens": [],
                    "parent": self.current,
                }
            )
        elif tag == "Js" or tag == "Ts" or tag == "Css" or tag == "Sass":
            asset_name = get_attr(attrs, "@")
            if isinstance(asset_name, str):
                asset = find_in_comets(asset_name) or find_in_assets(asset_name)
                if asset:
                    self.add_dep(asset, self.id)
                    if not asset_cache.get(asset):
                        compile_asset(asset)
                    set_attr(attrs, "@", asset)
                    self.current["childrens"].append(
                        {
                            "tag": tag,
                            "attrs": attrs,
                            "parent": self.current,
                        }
                    )
        elif tag == "Tailwind":
            if self.current["tag"] == "head":
                twlayouts[self.id] = get_attr(attrs, "@")
                if not BUILD:
                    with open(cache_dir / "twlayouts.json", "w") as f:
                        f.write(dumps(twlayouts))
                attrs.append(("layout", self.id))
                self.current["childrens"].append(
                    {
                        "tag": tag,
                        "attrs": attrs,
                        "parent": self.current,
                    }
                )
        else:
            attributes = self.process_attrs(attrs)
            self.current["childrens"].append(
                {"tag": tag, "attrs": attributes, "parent": self.current}
            )
            self.add_map(attributes, self.loc.copy() + [len(self.current["childrens"])])

    def handle_endtag(self, tag):
        if self.in_debug:
            if tag == "Debug":
                self.in_debug = False
                return
            elif not DEBUG:
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
                    self.current = self.current["parent"]
        if len(self.loc):
            self.loc.pop(-1)
        self.current = self.current["parent"]

    @handle_addition
    def handle_data(self, data):
        if not DEBUG and self.current["tag"] != "pre":
            data = re.sub(trim_re, "", data)
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
                elif groups[1] == "{{" or groups[1] == "{%":
                    self.current["childrens"].append(
                        django_engine.from_string(groups[0])
                    )
                previous = match.end()
            if previous:
                self.current["childrens"].append(data[previous:])
        else:
            self.current["childrens"].append(data)

    def handle_decl(self, decl):
        self.is_layout = True
        self.current["childrens"].append(f"<!{decl}>")

    def handle_charref(self, name):
        print("Encountered a charref  :", name)

    def handle_entityref(self, name):
        print("Encountered an entityref  :", name)

    def handle_pi(self, data):
        print("Encountered a pi  :", data)

    def process_attrs(self, attrs: AstAttrs):
        attributes: list[tuple[str, str | None | StrCode]] = []
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
            ):
                attributes.append((k, self.compile(v)))
            elif k.startswith("s-asset:"):
                asset = find_in_assets(v)
                if asset:
                    if not BUILD:
                        self.add_dep(asset, self.id)
                        attributes += [
                            (k, asset),
                            ("data-asset-id", compile_asset(asset)),
                            ("data-target", k.split(":")[1]),
                        ]
                    else:
                        compile_asset(asset)
                        attributes += [
                            (k.split(":")[1], f"/{ASSET_URL}{asset_cache[asset][0]}")
                        ]
            elif k.startswith("s-static:"):
                attributes.append((k.split(":")[1], escape(settings.STATIC_URL + v)))
            elif k == "server" or k == "client":
                attributes.append(("mode", k))
            else:
                attributes.append((k, v))

        if self.current["tag"] == "Helmet":
            attributes.append(("x-head", None))

        return attributes

    def compile(self, v: str):
        return StrCode(v, self.id)

    def withs(self, attrs: PureAttrs):
        _withs: Codes = []
        for k, v in attrs:
            _withs.append(
                (
                    k,
                    self.compile("True") if v is None else self.compile(v),
                )
            )
        return _withs

    def defaults(self, attrs: PureAttrs):
        _defaults: Codes = []
        for k, v in attrs:
            _defaults.append((k, self.compile(v)))
        return _defaults

    def add_props(self, element: Element, props: AstAttrs):
        for index, attr in enumerate(element["attrs"]):
            if attr[0] == "props":
                element["attrs"] = tuple(
                    list(element["attrs"])[:index]
                    + list(props)
                    + list(element["attrs"])[index + 1 :]
                )
        for children in element.get("childrens", []):
            if isinstance(children, dict):
                self.add_props(children, props)

    def add_dep(self, component: str, dependent: str):
        dgraph.setdefault(component, [])
        if dependent not in dgraph[component]:
            dgraph[component].append(dependent)

    def add_map(self, attrs: AstAttrs, loc: list[int]):
        sgroup = get_attr(attrs, "s-group")
        if sgroup:
            for group in sgroup.split(","):
                self.ast["map"]["groups"].setdefault(group, [])
                self.ast["map"]["groups"][group].append(loc)
        sparam = get_attr(attrs, "s-param")
        if sparam:
            for param in sparam.split(","):
                self.ast["map"]["params"].setdefault(param, [])
                self.ast["map"]["params"][param].append(loc)

    def find_loc(self, tag: str, ast: Ast | Element, attrs: AstAttrs, loc=None):
        loc = loc or []
        if ast["tag"] == tag:
            for attr in attrs:
                if not (get_attr(ast, attr[0]) == attr[1]):
                    break
            else:
                return loc
        for index, children in enumerate(ast.get("childrens", [])):
            if isinstance(children, dict):
                loc.append(index)
                _loc = self.find_loc(tag, children, attrs, loc=loc)
                if _loc:
                    return _loc
                loc.pop(-1)

    def find_node(self, tag: str, ast: Ast | Element, attrs: AstAttrs):
        if ast["tag"] == tag:
            for attr in attrs:
                if not (get_attr(ast, attr[0]) == attr[1]):
                    break
            else:
                return ast
        for children in ast.get("childrens", []):
            if isinstance(children, dict):
                node = self.find_node(tag, children, attrs)
                if node:
                    return node

    def load_component_map(self, map):
        for target in map:
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


def compile_asset(path: str):
    from picomet.loaders import cache_file, fcache

    if not fcache.get(path):
        with open(path) as f:
            cache_file(path, f.read())

    name, ext = os.path.splitext(os.path.basename(path))
    if ext == ".ts":
        from javascript import require

        compiled: str = (
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

        compiled: str = (
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
    for f in glob(str(assets_dir / f"{id}.*{ext}")):
        if os.path.exists(f):
            os.remove(f)
    with open(assets_dir / fname, "w") as f:
        f.write(compiled)
    save_asset_cache()

    return id


def compile_tailwind(layout: str):
    source_id = twlayouts[layout]
    picomet_engine = engines["picomet"].engine
    input_css = picomet_engine.find_template(f"{source_id}.tailwind.css")[1].name
    tailwind_conf = picomet_engine.find_template(f"{source_id}.tailwind.js")[1].name
    postcss_conf = picomet_engine.find_template(f"{source_id}.postcss.js")[1].name

    content = []

    def traverse(f: str):
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
    )
    from picomet.loaders import cache_file

    cache_file(input_css, css)
    asset_cache[layout] = (fname, compiled)
    save_asset_cache()


def find_in_comets(name: str):
    comet_dirs = list(
        chain.from_iterable(
            [
                [str(d) for d in loader.get_dirs()]
                for loader in engines["picomet"].engine.template_loaders
            ]
        )
    )
    return find_in_dirs(name, comet_dirs)


def find_in_assets(name: str):
    asset_dirs = [
        *[str(d) for d in ASSETFILES_DIRS],
        *[os.path.join(app.path, "assets") for app in apps.get_app_configs()],
    ]
    return find_in_dirs(name, asset_dirs)


def find_in_dirs(name: str, dirs: list[str]):
    for d in dirs:
        directory = Path(d)
        if directory.is_dir():
            file = directory / name
            if file.exists():
                return file.as_posix()
