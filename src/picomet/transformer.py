import sys
from copy import copy, deepcopy
from html import escape
from importlib import import_module
from json import dumps, loads
from pathlib import Path
from typing import Any, Literal, TypedDict, Unpack, cast

from django.conf import settings
from django.middleware.csrf import get_token
from django.template import loader
from django.template.backends.django import Template
from django.utils.safestring import SafeString

from picomet.parser import STATIC_URL, asset_cache, parse
from picomet.types import (
    Ast,
    AstAttr,
    AstAttrs,
    AstAttrsDynamic,
    AstAttrValue,
    AstElement,
    AstElWithAttrs,
    AstMap,
    AstNode,
    ElementDoubleTag,
    EscapedAttrs,
    Loops,
    StrCode,
    StrStore,
    isNodeElement,
    isNodeWithChildren,
)
from picomet.types import (
    DoubleQuoteEscapedStr as DQES,
)
from picomet.utils import escape_double_quote as edq
from picomet.utils import get_atrb, has_atrb, remove_atrb, set_atrb

try:
    from py_mini_racer import MiniRacer
except ImportError:
    pass

BASE_DIR: Path = settings.BASE_DIR
DEBUG: bool = settings.DEBUG

RUNSERVER = len(sys.argv) > 1 and sys.argv[1] == "runserver"

WRAPPERS = {t: t for t in ["Outlet", "Fragment", "With", "Default", "Group"]}


class EscAst(TypedDict):
    tag: str
    attrs: EscapedAttrs
    children: list["EscElementDoubleTag | EscElementSingleTag | str"]
    parent: None


class EscElementDoubleTag(TypedDict):
    tag: str
    attrs: EscapedAttrs
    children: list["EscElementDoubleTag | EscElementSingleTag | str"]
    parent: "EscAst | EscElementDoubleTag"


class EscElementSingleTag(TypedDict):
    tag: str
    attrs: EscapedAttrs
    parent: "EscAst | EscElementDoubleTag"


class EscGroupElement(TypedDict):
    tag: str
    attrs: EscapedAttrs
    children: list[EscElementDoubleTag | EscElementSingleTag]
    parent: EscElementDoubleTag


type Mode = Literal["client", "server"]


class Partial(TypedDict):
    html: str
    css: dict[str, str]
    js: dict[str, str]


class TransformKwargs(TypedDict):
    loops: Loops
    propAttrs: list[AstAttr]
    propChildren: list[list[AstNode]]


class LoopKwargs(TypedDict):
    mode: Mode
    propAttrs: list[AstAttr]
    propChildren: list[list[AstNode]]


class SforKwargs(TypedDict):
    depth: int | None
    mode: Mode
    propAttrs: list[AstAttr]
    propChildren: list[list[AstNode]]


class Transformer:
    def __init__(
        self,
        ast: Ast,
        map: AstMap,
        context: dict[str, Any],
        targets: list[str],
        keys: Loops,
    ):
        self.ast: Ast = ast
        self.map: AstMap = map
        self.context: dict[str, Any] = context
        self.ctx: MiniRacer | None = None
        self.targets: list[str] = targets
        self.keys: Loops = keys
        self.content: EscAst = {
            "tag": "Fragment",
            "attrs": [],
            "children": [],
            "parent": None,
        }
        self.current: EscAst | EscElementDoubleTag = self.content
        self.partials: dict[str, Partial] = {}
        self.c_target: str = ""
        self.groups: dict[str, EscGroupElement] = {}

        self.csrf_set = False

    def transform(self) -> None:
        self.clean_targets()
        self._transform(self.ast, "", loops=[], propChildren=[], propAttrs=[])

    def clean_targets(self) -> None:
        targets: list[str] = []
        layoutLoc: list[int] = []
        layoutId: str | None = None
        for target in self.targets:
            if not target.startswith("+"):
                targets.append(target)
            else:
                loLoc = self.map["layouts"].get(target[1:], [])
                if len(loLoc) > len(layoutLoc):
                    layoutLoc = loLoc
                    layoutId = target[1:]
        if layoutId:
            targets.append(f"+{layoutId}")
        self.targets = targets

    def _transform(
        self,
        node: AstNode,
        loc: str,
        depth: int | None = None,
        prevRtrn: bool | None = None,
        mode: Mode = "client",
        **kwargs: Unpack[TransformKwargs],
    ) -> bool | None:
        store: dict[str, Any]
        reset: list[str]
        if isNodeElement(node):
            tag = node["tag"]
            comet: str
            if isNodeWithChildren(node):
                if tag in ["Layout", "Include"]:
                    at = get_atrb(node, "@")
                    if isinstance(at, str):
                        comet = at
                        if not comet.endswith(".html"):
                            comet = f"{comet}.html"
                        template = loader.get_template(comet, using="picomet").template
                        ast = parse(template.source, template.origin.name).ast
                        withs, props = self.sort_props(node["attrs"])
                        store, reset = {}, []
                        self.pack_with(withs, store, reset)
                        kwargs["propAttrs"] = props
                        kwargs.setdefault("propChildren", [])
                        kwargs["propChildren"].append(node["children"])
                        self._transform(ast, loc, depth, mode=mode, **kwargs)
                        self.reset_context(reset)
                        self.unpack_store(store)
                    return True
            elif tag == "Include":
                at = get_atrb(node, "@")
                if isinstance(at, str):
                    comet = at
                    if not comet.endswith(".html"):
                        comet = f"{comet}.html"
                    template = loader.get_template(comet, using="picomet").template
                    ast = parse(template.source, template.origin.name).ast
                    withs, props = self.sort_props(node["attrs"])
                    store, reset = {}, []
                    self.pack_with(withs, store, reset)
                    kwargs["propAttrs"] = props
                    self._transform(ast, loc, depth=depth, mode=mode, **kwargs)
                    self.reset_context(reset)
                    self.unpack_store(store)
                return True
            elif tag == "Children":
                propChildren = kwargs["propChildren"].pop()
                self.loop(propChildren, loc=loc, depth=depth, mode=mode, **kwargs)
                return True
        if len(self.targets) and not self.c_target:
            if not isNodeElement(node):
                return None
            GROUPS = cast(str, get_atrb(node, "s-group", default=edq(""))).split(",")
            PARAMS = cast(str, get_atrb(node, "s-param", default=edq(""))).split(",")
            tag = node["tag"]
            if (
                any(f"&{group}" in self.targets for group in GROUPS)
                or any(f"?{param}" in self.targets for param in PARAMS)
                or (loc in self.targets)
                or (f"${node.get('file')}" in self.targets)
                or (tag == "Outlet" and f"+{get_atrb(node, "layout")}" in self.targets)
            ):
                self.partials[loc] = {"html": "", "css": {}, "js": {}}
                self.c_target = loc
            else:
                attrs = AstAttrsDynamic(node["attrs"], kwargs["propAttrs"])
                mode = cast(Mode, get_atrb(node, "mode", default=edq(mode)))
                if mode == "server" and self.ctx is None:
                    self.ctx = MiniRacer()
                sfor = None

                store, reset = {}, []
                if tag not in ["With", "Default"]:
                    condition = self.handle_conditionals(node, prevRtrn)
                    if not condition:
                        return condition

                    for attr in attrs:
                        k, v, span = attr
                        if k == "s-context":
                            self.handle_scontext(v, store, reset)
                        elif k.startswith("s-prop:"):
                            self.handle_sprop(k, v, None, mode)
                        elif k == "x-data":
                            self.handle_xdata(v, mode)
                        elif k == "s-for":
                            sfor = v
                if tag == "html" and self.ctx:
                    self.ctx.eval("var isServer = true;")
                elif tag == "With":
                    self.pack_with(node["attrs"], store, reset)
                elif tag == "Default":
                    self.pack_defaults(node["attrs"], store, reset)

                if isNodeWithChildren(node):
                    children = node["children"]
                    if sfor:
                        self.handle_sfor(
                            node, children, loc, depth=depth, mode=mode, **kwargs
                        )
                    else:
                        self.loop(children, loc, depth=depth, mode=mode, **kwargs)
                self.reset_context(reset)
                self.unpack_store(store)
                return None

        if isinstance(node, str):
            if self.c_target:
                self.partials[self.c_target]["html"] += node
            else:
                self.current["children"].append(node)
            return None
        elif isinstance(node, StrCode):
            e = eval(node.code, self.context)
            if isinstance(e, SafeString):
                string = e
            else:
                string = escape(str(e), quote=False)
            if self.c_target:
                self.partials[self.c_target]["html"] += string
            else:
                self.current["children"].append(string)
            return None
        elif isinstance(node, Template):
            string = node.render(self.context)
            if self.c_target:
                self.partials[self.c_target]["html"] += string
            else:
                self.current["children"].append(string)
            return None

        mode = cast(Mode, get_atrb(node, "mode", default=edq(mode)))
        if mode == "server" and self.ctx is None:
            self.ctx = MiniRacer()
        tag = node["tag"]
        attrs = AstAttrsDynamic(node["attrs"], kwargs["propAttrs"])
        eattrs: EscapedAttrs = []

        text: str | None = None
        sfor = None
        mark = (node.get("file") and not node.get("isBase")) if DEBUG else False
        mark_attrs: EscapedAttrs = []

        store: dict[str, Any] = {}
        reset: list[str] = []
        rtrn: bool = True

        if tag not in ["With", "Default"]:
            condition = self.handle_conditionals(node, prevRtrn)
            if not condition:
                if has_atrb(attrs, ["s-group", "s-param", "x-form"]):
                    self.add_marker_start(loc, mark_attrs)
                    self.add_marker_end(loc)
                    if loc == self.c_target:
                        self.c_target = ""
                return condition

            for attr in attrs:
                k, v, span = attr
                if not k.startswith("x-") and not k.startswith("s-") and k != "mode":
                    if isinstance(v, DQES):
                        eattrs.append((k, v))
                    elif v is None:
                        eattrs.append((k, v))

            for attr in attrs:
                k, v, span = attr
                if k == "s-group" or k == "s-param":
                    mark = True
                elif k == "x-form" and isinstance(v, str | type(None)):
                    mark = True
                    eattrs.append(("marker", edq(loc)))
                    eattrs.append((k, v))
                elif k == "s-context":
                    self.handle_scontext(v, store, reset)
                elif k.startswith("s-prop:"):
                    self.handle_sprop(k, v, eattrs, mode)
                elif k.startswith("x-prop:"):
                    if isinstance(v, StrCode):
                        value = dumps(eval(v.code, self.context))
                        eattrs.append((k, edq(value)))
                elif k == "x-data" and isinstance(v, str):
                    eattrs.append((k, v))
                    self.handle_xdata(v, mode)
                elif k == "x-show" and isinstance(v, str):
                    eattrs.append((k, v))
                    if mode == "server" and self.ctx and not self.ctx.eval(v):
                        style = self.get_atrb(eattrs, "style", default=DQES(""))
                        styles = style.split(";") if isinstance(style, DQES) else []
                        styles.append("display:none!important")
                        set_atrb(eattrs, "style", DQES(";".join(styles)))
                elif k == "s-text":
                    if isinstance(v, StrCode):
                        text = escape(eval(v.code, self.context), quote=False)
                elif k == "x-text" and isinstance(v, str):
                    eattrs.append((k, v))
                    if mode == "server" and self.ctx:
                        text = escape(str(self.ctx.eval(v)), quote=False)
                elif k.startswith("s-bind:"):
                    if isinstance(v, StrCode) and k.split(":")[1] == "class":
                        set_atrb(
                            eattrs,
                            "class",
                            self.add_classes(
                                cast(
                                    str,
                                    self.get_atrb(
                                        eattrs,
                                        "class",
                                        default=DQES(""),
                                    ),
                                ),
                                [str(eval(v.code, self.context))],
                            ),
                        )
                    elif isinstance(v, StrCode):
                        value = eval(v.code, self.context)
                        if k.split(":")[1] == "x-prop":
                            value = dumps(value)
                        eattrs.append(
                            (
                                ":".join(k.split(":")[1:]),
                                edq(str(value)),
                            )
                        )
                elif k.startswith("s-toggle:"):
                    if isinstance(v, StrCode):
                        val = eval(v.code, self.context)
                        if val is True:
                            eattrs.append((":".join(k.split(":")[1:]), None))
                elif k.startswith("x-bind:") and isinstance(v, str):
                    eattrs.append((k, v))
                    if mode == "server" and self.ctx:
                        if k.split(":")[1] == "class":
                            if v.startswith("{"):
                                self.ctx.eval(
                                    f"var classes = {v}; var klasses = []; for (let k in classes) {{ if (classes[k]) {{klasses.push(k)}} }};"
                                )
                                clas = self.get_atrb(eattrs, "class", default=DQES(""))
                                if isinstance(clas, str):
                                    set_atrb(
                                        eattrs,
                                        "class",
                                        self.add_classes(
                                            clas,
                                            loads(
                                                str(
                                                    self.ctx.eval(
                                                        "JSON.stringify(klasses)"
                                                    )
                                                )
                                            ),
                                        ),
                                    )
                            else:
                                set_atrb(
                                    eattrs,
                                    "class",
                                    edq(str(self.ctx.eval(v))),
                                )
                        else:
                            val = self.ctx.eval(v)
                            if val is not False:
                                eattrs.append((k.split(":")[1], edq(str(val))))
                elif k == "s-k" or k == "s-keys":
                    eattrs.append(("x-prop:keys", edq(dumps(kwargs["loops"]))))
                elif k.startswith("s-asset:"):
                    eattrs.append(
                        (
                            k.split(":")[1],
                            edq(f"{STATIC_URL}{asset_cache[str(v)][0]}"),
                        )
                    )
                elif k == "s-for":
                    sfor = v
                elif k == "s-csrf" and not self.csrf_set:
                    request = self.context.get("request")
                    if request:
                        get_token(request)
                        self.csrf_set = True
                elif k.startswith("x-") and isinstance(v, str | type(None)):
                    eattrs.append((k, v))

        if tag == "html" and self.ctx:
            self.ctx.eval("var isServer = true;")
            eattrs.append(("x-data", DQES("{isServer: false, keys: []}")))
        elif tag == "Outlet":
            mark = True
            layout = get_atrb(node, "layout")
            if isinstance(layout, str):
                mark_attrs.append(("group", edq("layout")))
                mark_attrs.append(("gId", edq(layout)))
        elif tag == "With":
            self.pack_with(node["attrs"], store, reset)
        elif tag == "Default":
            self.pack_defaults(node["attrs"], store, reset)

        if self.c_target:
            if tag == "Css" or tag == "Sass":
                fname, _ = asset_cache[cast(str, get_atrb(node, "@"))]
                self.partials[self.c_target]["css"][fname.split(".")[0]] = (
                    f"{STATIC_URL}{fname}"
                )
            elif tag == "Js" or tag == "Ts":
                fname, _ = asset_cache[cast(str, get_atrb(node, "@"))]
                self.partials[self.c_target]["js"][fname.split(".")[0]] = (
                    f"{STATIC_URL}{fname}"
                )
            else:
                attributes = self.join_attrs(eattrs)
                if mark:
                    self.add_marker_start(loc, mark_attrs)
                if isNodeWithChildren(node):
                    children = node["children"]
                    if tag and (tag not in WRAPPERS):
                        self.partials[self.c_target]["html"] += f"<{tag}{attributes}>"
                    if sfor:
                        node = cast(ElementDoubleTag, node)
                        if not self.handle_sfor(
                            node, children, loc, depth=depth, mode=mode, **kwargs
                        ):
                            rtrn = False
                    elif text:
                        self.partials[self.c_target]["html"] += text
                    else:
                        self.loop(children, loc, depth=depth, mode=mode, **kwargs)
                    if tag and (tag not in WRAPPERS):
                        self.partials[self.c_target]["html"] += f"</{tag}>"
                else:
                    self.partials[self.c_target]["html"] += f"<{tag}{attributes} />"

                if mark:
                    self.add_marker_end(loc)
                if loc == self.c_target:
                    self.c_target = ""
        elif tag == "Css" or tag == "Sass":
            fname, compiled = asset_cache[cast(str, get_atrb(node, "@"))]
            asset_id = edq(fname.split(".")[0])
            assets = self.groups[cast(str, get_atrb(node, "group"))]["children"]
            exists = False
            for asset in assets:
                if get_atrb(cast(AstElWithAttrs, asset), "data-style-id") == asset_id:
                    exists = True
            if not exists:
                if settings.DEBUG:
                    assets.append(
                        {
                            "tag": "link",
                            "attrs": [
                                ("rel", edq("stylesheet")),
                                ("href", edq(f"{STATIC_URL}{fname}")),
                                ("data-style-id", asset_id),
                            ],
                            "parent": self.current,
                        }
                    )
                else:
                    assets.append(
                        {
                            "tag": "style",
                            "attrs": [("data-style-id", asset_id)],
                            "children": [compiled],
                            "parent": self.current,
                        }
                    )
        elif tag == "Js" or tag == "Ts":
            fname, _ = asset_cache[cast(str, get_atrb(node, "@"))]
            asset_id = edq(fname.split(".")[0])
            remove_atrb(eattrs, "@")
            eattrs.append(("type", edq("module")))
            eattrs.append(("data-script-id", asset_id))
            self.current["children"].append(
                {
                    "tag": "script",
                    "attrs": eattrs,
                    "children": [
                        f'import * as module from "{STATIC_URL}{fname}"; Object.keys(module).forEach((key) => {{if(key == "cleanup"){{window["{asset_id}_cleanup"] = module[key]}} else {{window[key] = module[key]}}}});'
                    ],
                    "parent": self.current,
                }
            )
        elif tag == "Tailwind":
            fname, _ = asset_cache[cast(str, get_atrb(node, "layout"))]
            self.current["children"].append(
                {
                    "tag": "link",
                    "attrs": [
                        ("rel", DQES("stylesheet")),
                        ("href", edq(f"{STATIC_URL}{fname}")),
                        ("data-tailwind-id", edq(fname.split(".")[0])),
                    ],
                    "parent": self.current,
                }
            )
        else:
            element: EscElementSingleTag | EscElementDoubleTag = {
                "tag": tag,
                "attrs": eattrs,
                "parent": self.current,
            }

            if mark:
                self.add_marker_start(loc, mark_attrs)
            self.current["children"].append(element)
            if tag == "Group":
                group = get_atrb(node, "name")
                if group != "head":
                    group_element = cast(EscGroupElement, element)
                    group_element["children"] = []
                    self.groups[cast(str, group)] = group_element
            if isNodeWithChildren(node):
                children = node["children"]
                element = cast(EscElementDoubleTag, element)
                if tag == "head":
                    self.groups[tag] = cast(EscGroupElement, element)
                self.current = element
                element["children"] = []
                if sfor:
                    if not self.handle_sfor(
                        node, children, loc=loc, depth=depth, mode=mode, **kwargs
                    ):
                        rtrn = False
                elif text:
                    element["children"].append(text)
                else:
                    self.loop(children, loc=loc, depth=depth, mode=mode, **kwargs)
                if tag == "Helmet":
                    metas = deepcopy(cast(EscGroupElement, element)["children"])
                    for meta in metas:
                        if isinstance(meta, dict):
                            remove_atrb(meta["attrs"], "x-head")
                    self.groups["head"]["children"] += metas
                    remove_atrb(eattrs, "group")
                self.current = element["parent"]
            if mark:
                self.add_marker_end(loc)
        self.reset_context(reset)
        self.unpack_store(store)
        return rtrn

    def loop(
        self,
        children: list[AstNode] | list[AstElement],
        loc: str,
        depth: int | None = None,
        loops: list[tuple[str, int]] = [],
        **kwargs: Unpack[LoopKwargs],
    ) -> None:
        prevRtrn: bool | None = None
        for index, child in enumerate(children):
            _depth: int = 0 if depth is None else depth + 1
            _loc: str = loc
            if isNodeElement(child) and child["tag"] not in ["Layout"]:
                _loc += f"{index}" if not _loc else f",{index}"
                if (
                    len(self.targets)
                    and not self.c_target
                    and not self.is_required(_depth, index, _loc)
                ):
                    continue
            rtrn = self._transform(
                child, _loc, _depth, prevRtrn=prevRtrn, loops=loops, **kwargs
            )
            prevRtrn = rtrn if isNodeElement(child) else prevRtrn

    def handle_scontext(
        self, v: AstAttrValue, store: dict[str, Any], reset: list[str]
    ) -> None:
        context_module, context_name = str(v).split(".")
        module = f"{context_module}.contexts"
        contexts = import_module(module)
        context = getattr(contexts, context_name)
        for k, v in context(self.context).items():
            reset.append(k)
            if k in self.context:
                store[k] = self.context[k]
            self.context[k] = v

    def handle_conditionals(
        self, node: AstElement, prevRtrn: bool | None
    ) -> bool | None:
        show = get_atrb(node, "s-show")
        if isinstance(show, StrCode) and not eval(show.code, self.context):
            return False
        elif get_atrb(node, "s-if") and not eval(
            cast(StrCode, get_atrb(node, "s-if")).code, self.context
        ):
            return False
        elif get_atrb(node, "s-elif"):
            if prevRtrn is True:
                return True
            elif not eval(cast(StrCode, get_atrb(node, "s-elif")).code, self.context):
                return False
        elif get_atrb(node, "s-else") is None and prevRtrn is True:
            return None
        elif get_atrb(node, "s-empty") is None and prevRtrn is True:
            return None

        return True

    def sort_props(self, attrs: AstAttrs) -> tuple[AstAttrs, AstAttrs]:
        withs = [
            AstAttr(attr[0][1:], attr[1], attr[2])
            for attr in attrs
            if attr[0].startswith(".")
        ]
        props = [
            attr for attr in attrs if not (attr[0].startswith(".") or attr[0] == "@")
        ]
        return withs, props

    def get_atrb(
        self,
        attrs: EscapedAttrs,
        name: str,
        default: DQES | bool = False,
    ) -> DQES | None | bool:
        for attr in attrs:
            if attr[0] == name:
                return attr[1]
        return default

    def add_marker_start(self, loc: str, attrs: EscapedAttrs) -> None:
        if self.c_target:
            self.partials[self.c_target]["html"] += (
                f'<Marker id="<{loc}"{self.join_attrs(attrs)} hidden></Marker>'
            )
        else:
            self.current["children"].append(
                {
                    "tag": "Marker",
                    "attrs": [("id", edq(f"<{loc}")), *attrs, ("hidden", None)],
                    "children": [],
                    "parent": self.current,
                }
            )

    def add_marker_end(self, loc: str) -> None:
        if self.c_target:
            self.partials[self.c_target]["html"] += (
                f'<Marker id=">{loc}" hidden></Marker>'
            )
        else:
            self.current["children"].append(
                {
                    "tag": "Marker",
                    "attrs": [("id", edq(f">{loc}")), ("hidden", None)],
                    "children": [],
                    "parent": self.current,
                }
            )

    def handle_sprop(
        self, k: str, v: AstAttrValue, attrs: EscapedAttrs | None, mode: Mode
    ) -> None:
        if isinstance(v, StrCode) and mode == "server" and self.ctx:
            prop = k.split(":")[1]
            value = dumps(eval(v.code, self.context))
            self.ctx.eval(f"var {prop} = JSON.parse('{value.replace("'","\\'")}');")
            if isinstance(attrs, list):
                attrs.append((f"x-prop:{prop}", edq(value)))

    def handle_xdata(self, v: AstAttrValue, mode: Mode) -> None:
        if isinstance(v, str) and mode == "server" and self.ctx:
            if v.strip().startswith("{"):
                self.ctx.eval(
                    f"var data = {v}; for (let k in data) {{ globalThis[k] = data[k] }};"
                )

    def handle_sfor(
        self,
        node: Ast | ElementDoubleTag,
        children: list[AstNode],
        loc: str,
        loops: list[tuple[str, int]],
        **kwargs: Unpack[SforKwargs],
    ) -> bool | None:
        sfor = cast(str, get_atrb(node, "s-for"))
        skey = cast(StrCode, get_atrb(node, "s-key"))
        array: list[Any] = []
        for key in self.keys:
            if loc == key[0]:
                array = eval(
                    cast(StrCode, get_atrb(node, "s-of")).code,
                    self.context,
                    {"key": key[1]},
                )
        if not array:
            array = eval(cast(StrCode, get_atrb(node, "s-in")).code, self.context)

        _loc = copy(loc)
        store: dict[str, Any] = {}
        if sfor in self.context:
            store[sfor] = self.context[sfor]
        for index, item in enumerate(array):
            self.context[sfor] = item
            self.context["index"] = index
            _loops = deepcopy(loops)
            if skey:
                _skey = int(eval(skey.code, self.context))
                _loc = f"{loc}:[{_skey}]"
                _loops = [*_loops, (copy(loc), _skey)]
            self.loop(children, _loc, loops=_loops, **kwargs)
        self.context.pop(sfor, None)
        self.unpack_store(store)
        if len(array):
            return True
        return None

    def pack_with(
        self, attrs: AstAttrs, store: dict[str, Any], reset: list[str]
    ) -> None:
        for key, val, span in attrs:
            if isinstance(val, StrCode):
                reset.append(key)
                if key in self.context:
                    store[key] = self.context[key]
                self.context[key] = eval(val.code, self.context)

    def pack_defaults(
        self, attrs: AstAttrs, store: dict[str, Any], reset: list[str]
    ) -> None:
        for key, val, span in attrs:
            if isinstance(val, StrCode) and key not in self.context:
                reset.append(key)
                self.context[key] = eval(val.code, self.context)

    def reset_context(self, reset: list[str]) -> None:
        for k in reset:
            self.context.pop(k, None)

    def unpack_store(self, store: dict[str, Any]) -> None:
        for k in store:
            self.context[k] = store[k]

    def add_classes(self, string: str, classes: list[str]) -> DQES:
        klasses = string.strip().split(" ")
        for klass in classes:
            if klass and klass not in klasses:
                klasses.append(klass)
        return edq(" ".join(klasses))

    def join_attrs(self, attrs: EscapedAttrs) -> str:
        attributes: str = ""
        for k, v in attrs:
            if v is None:
                attributes += f" {k}"
            else:
                attributes += f' {k}="{v}"'
        return attributes

    def is_required(self, depth: int, index: int, pos: str) -> bool:
        for target in self.targets:
            if target.startswith("$"):
                for loc in self.map["files"].get(target[1:], []):
                    if len(loc) > depth and loc[depth] == index:
                        return True
            elif target.startswith("&"):
                for loc in self.map["groups"].get(target[1:], []):
                    if len(loc) > depth and loc[depth] == index:
                        return True
            elif target.startswith("?"):
                for loc in self.map["params"].get(target[1:], []):
                    if len(loc) > depth and loc[depth] == index:
                        return True
            elif target.startswith("+"):
                loc = self.map["layouts"].get(target[1:], [-1])
                if len(loc) > depth and loc[depth] == index:
                    return True
            elif target.startswith(pos):
                return True
        return False

    def compile_content(self) -> str:
        html = StrStore("")

        def compile(
            node: EscAst | EscElementDoubleTag | EscElementSingleTag | str,
            content: StrStore,
        ) -> None:
            if not isinstance(node, dict):
                content.value += node
            else:
                tag = node["tag"]
                children = node.get("children")
                attributes = self.join_attrs(node["attrs"])
                if isinstance(children, list):
                    if tag and (tag not in WRAPPERS):
                        content.value += f"<{tag}{attributes}>"
                    for child in children:
                        compile(child, content)
                    if tag and (tag not in WRAPPERS):
                        content.value += f"</{tag}>"
                else:
                    content.value += f"<{tag}{attributes} />"

        compile(self.content, html)
        return html.value
