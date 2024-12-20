from copy import copy, deepcopy
from html import escape
from importlib import import_module
from json import dumps, loads
from pathlib import Path
from typing import Any, Literal, NotRequired, TypedDict, Unpack, cast

from django.conf import settings
from django.middleware.csrf import get_token
from django.template.backends.django import Template
from django.utils.safestring import SafeString

from picomet.parser import STATIC_URL, asset_cache
from picomet.types import (
    Ast,
    AstAttrs,
    AstAttrValue,
    AstElement,
    AstNode,
    DoubleQuoteEscapedStr,
    ElementDoubleTag,
    ElementWithAttrs,
    EscapedAttrs,
    Loops,
    StrCode,
    StrStore,
    isAtrbEscaped,
    isNodeElement,
    isNodeWithChildrens,
)
from picomet.utils import (
    escape_double_quote as edq,
)
from picomet.utils import (
    get_atrb,
    has_atrb,
    remove_atrb,
    set_atrb,
)

try:
    from py_mini_racer import MiniRacer
except ImportError:
    pass

BASE_DIR: Path = settings.BASE_DIR
DEBUG: bool = settings.DEBUG

EXCLUDES = {
    t: t for t in ["Outlet", "Fragment", "With", "Default", "Children", "Group"]
}


class EscAst(TypedDict):
    tag: str
    attrs: EscapedAttrs
    childrens: list["EscElementDoubleTag | EscElementSingleTag | str"]
    parent: None


class EscElementDoubleTag(TypedDict):
    tag: str
    attrs: EscapedAttrs
    childrens: list["EscElementDoubleTag | EscElementSingleTag | str"]
    parent: "EscAst | EscElementDoubleTag"


class EscElementSingleTag(TypedDict):
    tag: str
    attrs: EscapedAttrs
    parent: "EscAst | EscElementDoubleTag"


class EscGroupElement(TypedDict):
    tag: str
    attrs: EscapedAttrs
    childrens: list[EscElementDoubleTag | EscElementSingleTag]
    parent: EscElementDoubleTag


type Mode = Literal["client", "server"]


class Partial(TypedDict):
    html: str
    css: dict[str, str]
    js: dict[str, str]


class TransformKwargs(TypedDict):
    index: NotRequired[int]
    file: str


class LoopKwargs(TypedDict):
    index: int
    loops: list[tuple[str, int]]
    file: str
    mode: Mode


class SforKwargs(TypedDict):
    loops: list[tuple[str, int]]
    index: int
    depth: int | None
    mode: Mode
    file: str


class Transformer:
    def __init__(
        self, ast: Ast, context: dict[str, Any], targets: list[str], keys: Loops
    ):
        self.ast = ast
        self.context = context
        self.ctx = None
        self.targets = targets
        self.keys: Loops = keys
        self.content: EscAst = {
            "tag": "Fragment",
            "attrs": [],
            "childrens": [],
            "parent": None,
        }
        self.current: EscAst | EscElementDoubleTag = self.content
        self.partials: dict[str, Partial] = {}
        self.c_target: str = ""
        self.groups: dict[str, EscGroupElement] = {}

        self.csrf_set = False

    def transform(self) -> None:
        self.clean_targets()
        self._transform(self.ast, "", file=self.ast["file"])

    def clean_targets(self) -> None:
        targets: list[str] = []
        layoutLoc: list[int] = []
        layoutId: str | None = None
        for target in self.targets:
            if not target.startswith("+"):
                targets.append(target)
            else:
                loLoc = self.ast["map"]["layouts"].get(target[1:], [])
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
        loops: Loops = [],
        depth: int | None = None,
        prevRtrn: bool | None = None,
        mode: Mode = "client",
        **kwargs: Unpack[TransformKwargs],
    ) -> bool | None:
        if len(self.targets) and not self.c_target:
            if not isNodeElement(node):
                return None
            GROUPS = cast(str, get_atrb(node, "s-group", default="")).split(",")
            PARAMS = cast(str, get_atrb(node, "s-param", default="")).split(",")
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
                mode = cast(Mode, get_atrb(node, "mode", default=mode))
                if mode == "server" and self.ctx is None:
                    self.ctx = MiniRacer()
                sfor = None

                store: dict[str, Any] = {}
                reset: list[str] = []
                if tag != "With" and tag != "Default":
                    condition = self.handle_conditionals(node, prevRtrn)
                    if not condition:
                        return condition

                    for attr in node["attrs"]:
                        k, v = attr
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

                if isNodeWithChildrens(node):
                    childrens = node["childrens"]
                    if sfor:
                        self.handle_sfor(
                            node,
                            childrens,
                            loc,
                            depth=depth,
                            loops=loops,
                            mode=mode,
                            **kwargs,
                        )
                    else:
                        self.loop(
                            childrens,
                            loc,
                            depth=depth,
                            loops=loops,
                            mode=mode,
                            **kwargs,
                        )
                self.reset_context(reset)
                self.unpack_store(store)
                return None

        if isinstance(node, str):
            if self.c_target:
                self.partials[self.c_target]["html"] += node
            else:
                self.current["childrens"].append(node)
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
                self.current["childrens"].append(string)
            return None
        elif isinstance(node, Template):
            string = node.render(self.context)
            if self.c_target:
                self.partials[self.c_target]["html"] += string
            else:
                self.current["childrens"].append(string)
            return None

        mode = cast(Mode, get_atrb(node, "mode", default=mode))
        if mode == "server" and self.ctx is None:
            self.ctx = MiniRacer()
        tag = node["tag"]
        attrs: EscapedAttrs = []

        text = None
        sfor = None
        mark = (node.get("file") and not node.get("isBase")) if DEBUG else False
        mark_attrs: EscapedAttrs = []

        store = {}
        reset = []
        rtrn = True

        if tag != "With" and tag != "Default":
            condition = self.handle_conditionals(node, prevRtrn)
            if not condition:
                if has_atrb(node["attrs"], ["s-group", "s-param", "x-form"]):
                    self.add_marker_start(loc, mark_attrs)
                    self.add_marker_end(loc)
                    if loc == self.c_target:
                        self.c_target = ""
                return condition

            for attr in node["attrs"]:
                k, v = attr
                if not k.startswith("x-") and not k.startswith("s-") and k != "mode":
                    if isinstance(v, str):
                        attrs.append((k, DoubleQuoteEscapedStr(v)))
                    elif v is None:
                        attrs.append((k, v))

            for attr in node["attrs"]:
                k, v = attr
                if k == "s-group" or k == "s-param":
                    mark = True
                elif k == "x-form" and isAtrbEscaped(attr):
                    mark = True
                    attrs.append(("marker", edq(loc)))
                    attrs.append(attr)
                elif k == "s-context":
                    self.handle_scontext(v, store, reset)
                elif k.startswith("s-prop:"):
                    self.handle_sprop(k, v, attrs, mode)
                elif k == "x-data" and isAtrbEscaped(attr):
                    attrs.append(attr)
                    self.handle_xdata(v, mode)
                elif k == "x-show" and isAtrbEscaped(attr):
                    attrs.append(attr)
                    if mode == "server" and self.ctx and not self.ctx.eval(v):
                        style = get_atrb(attrs, "style", default="")
                        styles = style.split(";") if style else []
                        styles.append("display:none!important")
                        set_atrb(attrs, "style", ";".join(styles))
                elif k == "s-text":
                    v = cast(StrCode, v)
                    text = escape(eval(v.code, self.context), quote=False)
                elif k == "x-text" and isAtrbEscaped(attr):
                    attrs.append(attr)
                    if mode == "server" and self.ctx:
                        text = escape(self.ctx.eval(v), quote=False)
                elif k.startswith("s-bind:"):
                    v = cast(StrCode, v)
                    if k.split(":")[1] == "class":
                        set_atrb(
                            attrs,
                            "class",
                            self.add_classes(
                                cast(str, get_atrb(attrs, "class", default="")),
                                [str(eval(v.code, self.context))],
                            ),
                        )
                    else:
                        value = eval(v.code, self.context)
                        if k.split(":")[1] == "x-prop":
                            value = dumps(value)
                        attrs.append(
                            (
                                ":".join(k.split(":")[1:]),
                                edq(str(value)),
                            )
                        )
                elif k.startswith("s-toggle:"):
                    if isinstance(v, StrCode):
                        val = eval(v.code, self.context)
                        if val is True:
                            attrs.append((":".join(k.split(":")[1:]), None))
                elif k.startswith("x-bind:") and isAtrbEscaped(attr):
                    attrs.append(attr)
                    if mode == "server" and self.ctx:
                        if k.split(":")[1] == "class":
                            if v.startswith("{"):
                                self.ctx.eval(
                                    f"var classes = {v}; var klasses = []; for (let k in classes) {{ if (classes[k]) {{klasses.push(k)}} }};"
                                )
                                set_atrb(
                                    attrs,
                                    "class",
                                    self.add_classes(
                                        get_atrb(attrs, "class", default=""),
                                        loads(self.ctx.eval("JSON.stringify(klasses)")),
                                    ),
                                )
                            else:
                                set_atrb(
                                    attrs,
                                    "class",
                                    edq(str(self.ctx.eval(v))),
                                )
                        else:
                            val = self.ctx.eval(v)
                            if val is not False:
                                attrs.append((k.split(":")[1], edq(str(val))))
                elif k == "s-k" or k == "s-keys":
                    attrs.append(("x-prop:keys", edq(dumps(loops))))
                elif k.startswith("s-asset:"):
                    attrs.append(
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
                elif k.startswith("x-") and isAtrbEscaped(attr):
                    attrs.append(attr)

        if tag == "html" and self.ctx:
            self.ctx.eval("var isServer = true;")
            attrs.append(("x-data", "{isServer: false, keys: []}"))
        elif tag == "Outlet":
            mark = True
            layout = cast(str, get_atrb(node, "layout"))
            if layout:
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
                attributes = self.join_attrs(attrs)
                if mark:
                    self.add_marker_start(loc, mark_attrs)
                if isNodeWithChildrens(node):
                    childrens = node["childrens"]
                    if tag and (tag not in EXCLUDES):
                        self.partials[self.c_target]["html"] += f"<{tag}{attributes}>"
                    if sfor:
                        node = cast(ElementDoubleTag, node)
                        if not self.handle_sfor(
                            node,
                            childrens,
                            loc=loc,
                            loops=loops,
                            depth=depth,
                            mode=mode,
                            **kwargs,
                        ):
                            rtrn = False
                    elif text:
                        self.partials[self.c_target]["html"] += text
                    else:
                        self.loop(
                            childrens,
                            loc=loc,
                            loops=loops,
                            depth=depth,
                            mode=mode,
                            **kwargs,
                        )
                    if tag and (tag not in EXCLUDES):
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
            assets = self.groups[cast(str, get_atrb(node, "group"))]["childrens"]
            exists = False
            for asset in assets:
                if get_atrb(cast(ElementWithAttrs, asset), "data-style-id") == asset_id:
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
                            "childrens": [compiled],
                            "parent": self.current,
                        }
                    )
        elif tag == "Js" or tag == "Ts":
            fname, _ = asset_cache[cast(str, get_atrb(node, "@"))]
            asset_id = edq(fname.split(".")[0])
            remove_atrb(attrs, "@")
            attrs.append(("type", edq("module")))
            attrs.append(("data-script-id", asset_id))
            self.current["childrens"].append(
                {
                    "tag": "script",
                    "attrs": attrs,
                    "childrens": [
                        f'import * as module from "{STATIC_URL}{fname}"; Object.keys(module).forEach((key) => {{if(key == "cleanup"){{window["{asset_id}_cleanup"] = module[key]}} else {{window[key] = module[key]}}}});'
                    ],
                    "parent": self.current,
                }
            )
        elif tag == "Tailwind":
            fname, _ = asset_cache[cast(str, get_atrb(node, "layout"))]
            self.current["childrens"].append(
                {
                    "tag": "link",
                    "attrs": [
                        ("rel", DoubleQuoteEscapedStr("stylesheet")),
                        ("href", edq(f"{STATIC_URL}{fname}")),
                        ("data-tailwind-id", edq(fname.split(".")[0])),
                    ],
                    "parent": self.current,
                }
            )
        else:
            element: EscElementSingleTag | EscElementDoubleTag = {
                "tag": tag,
                "attrs": attrs,
                "parent": self.current,
            }

            if mark:
                self.add_marker_start(loc, mark_attrs)
            self.current["childrens"].append(element)
            if tag == "Group":
                group = get_atrb(node, "name")
                if group != "head":
                    group_element = cast(EscGroupElement, element)
                    group_element["childrens"] = []
                    self.groups[cast(str, group)] = group_element
            if isNodeWithChildrens(node):
                childrens = node["childrens"]
                element = cast(EscElementDoubleTag, element)
                if tag == "head":
                    self.groups[tag] = cast(EscGroupElement, element)
                self.current = element
                element["childrens"] = []
                if sfor:
                    if not self.handle_sfor(
                        node,
                        childrens,
                        loc=loc,
                        loops=loops,
                        depth=depth,
                        mode=mode,
                        **kwargs,
                    ):
                        rtrn = False
                elif text:
                    element["childrens"].append(text)
                else:
                    self.loop(
                        childrens,
                        loc=loc,
                        loops=loops,
                        depth=depth,
                        mode=mode,
                        **kwargs,
                    )
                if tag == "Helmet":
                    metas = deepcopy(cast(EscGroupElement, element)["childrens"])
                    for meta in metas:
                        if isinstance(meta, dict):
                            remove_atrb(meta["attrs"], "x-head")
                    self.groups["head"]["childrens"] += metas
                    remove_atrb(attrs, "group")
                self.current = element["parent"]
            if mark:
                self.add_marker_end(loc)
        self.reset_context(reset)
        self.unpack_store(store)
        return rtrn

    def loop(
        self,
        childrens: list[AstNode],
        loc: str,
        depth: int | None = None,
        **kwargs: Unpack[LoopKwargs],
    ) -> None:
        prevRtrn: bool | None = None
        depth = 0 if depth is None else depth + 1
        for index, children in enumerate(childrens):
            _loc = copy(loc)
            if isNodeElement(children):
                _loc += f"{kwargs['index']}" if not _loc else f",{kwargs['index']}"
                kwargs["file"] = cast(str, children.get("file", kwargs["file"]))
                if (
                    len(self.targets)
                    and not self.c_target
                    and not self.is_required(depth, index, _loc)
                ):
                    continue
            kwargs["index"] = index
            rtrn = self._transform(
                children, _loc, depth=depth, prevRtrn=prevRtrn, **kwargs
            )
            prevRtrn = rtrn if isNodeElement(children) else prevRtrn

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

    def add_marker_start(self, loc: str, attrs: EscapedAttrs) -> None:
        if self.c_target:
            self.partials[self.c_target]["html"] += (
                f'<Marker id="<{loc}"{self.join_attrs(attrs)} hidden></Marker>'
            )
        else:
            self.current["childrens"].append(
                {
                    "tag": "Marker",
                    "attrs": [("id", edq(f"<{loc}")), *attrs, ("hidden", None)],
                    "childrens": [],
                    "parent": self.current,
                }
            )

    def add_marker_end(self, loc: str) -> None:
        if self.c_target:
            self.partials[self.c_target]["html"] += (
                f'<Marker id=">{loc}" hidden></Marker>'
            )
        else:
            self.current["childrens"].append(
                {
                    "tag": "Marker",
                    "attrs": [("id", edq(f">{loc}")), ("hidden", None)],
                    "childrens": [],
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
        childrens: list[AstNode],
        loc: str,
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
            if skey:
                _skey = int(eval(skey.code, self.context))
                _loc = f"{loc}:[{_skey}]"
                loops: Loops = [
                    *kwargs["loops"],
                    (loc, _skey),
                ]
                kwargs["loops"] = loops
            self.loop(childrens, _loc, **kwargs)
        self.context.pop(sfor, None)
        self.unpack_store(store)
        if len(array):
            return True
        return None

    def pack_with(
        self, attrs: AstAttrs, store: dict[str, Any], reset: list[str]
    ) -> None:
        for k, v in attrs:
            if isinstance(v, StrCode):
                reset.append(k)
                if k in self.context:
                    store[k] = self.context[k]
                self.context[k] = eval(v.code, self.context)

    def pack_defaults(
        self, attrs: AstAttrs, store: dict[str, Any], reset: list[str]
    ) -> None:
        for k, v in attrs:
            if isinstance(v, StrCode) and k not in self.context:
                reset.append(k)
                self.context[k] = eval(v.code, self.context)

    def reset_context(self, reset: list[str]) -> None:
        for k in reset:
            self.context.pop(k, None)

    def unpack_store(self, store: dict[str, Any]) -> None:
        for k in store:
            self.context[k] = store[k]

    def add_classes(self, string: str, classes: list[str]) -> DoubleQuoteEscapedStr:
        klasses = string.strip().split(" ")
        for klass in classes:
            if klass and klass not in klasses:
                klasses.append(klass)
        return edq(" ".join(klasses))

    def join_attrs(self, attrs: EscapedAttrs) -> str:
        return "".join(
            map(
                lambda attr: f' {attr[0]}="{attr[1]}"' if attr[1] else f" {attr[0]}",
                attrs,
            )
        )

    def is_required(self, depth: int, index: int, pos: str) -> bool:
        for target in self.targets:
            if target.startswith("$"):
                for loc in self.ast["map"]["files"].get(target[1:], []):
                    if len(loc) > depth and loc[depth] == index:
                        return True
            elif target.startswith("&"):
                for loc in self.ast["map"]["groups"].get(target[1:], []):
                    if len(loc) > depth and loc[depth] == index:
                        return True
            elif target.startswith("?"):
                for loc in self.ast["map"]["params"].get(target[1:], []):
                    if len(loc) > depth and loc[depth] == index:
                        return True
            elif target.startswith("+"):
                loc = self.ast["map"]["layouts"].get(target[1:], [-1])
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
                childrens = node.get("childrens")
                attributes = self.join_attrs(node["attrs"])
                if isinstance(childrens, list):
                    if tag and (tag not in EXCLUDES):
                        content.value += f"<{tag}{attributes}>"
                    for children in childrens:
                        compile(children, content)
                    if tag and (tag not in EXCLUDES):
                        content.value += f"</{tag}>"
                else:
                    content.value += f"<{tag}{attributes} />"

        compile(self.content, html)
        return html.value
