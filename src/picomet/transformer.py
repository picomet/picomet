from collections.abc import Iterable
from copy import copy, deepcopy
from json import dumps, loads
from pathlib import Path
from types import CodeType
from typing import Any, Literal, TypedDict

from django.conf import settings
from django.template.backends.django import Template
from django.utils.html import escape

from picomet.parser import (
    ASSET_URL,
    Ast,
    AstNode,
    Codes,
    PureAttrs,
    StrCode,
    asset_cache,
)
from picomet.utils import get_attr, remove_attr, set_attr

try:
    from py_mini_racer import MiniRacer
except ImportError:
    pass

DEBUG: bool = settings.DEBUG
BASE_DIR: Path = settings.BASE_DIR

EXCLUDES = ["Outlet", "Fragment", "With", "Default", "Children", "Group"]


class Element(TypedDict):
    tag: str | None
    attrs: PureAttrs
    childrens: list["Element | str"] | None
    parent: "Element | None"


type Mode = Literal["client", "server"]


class Partial(TypedDict):
    html: str
    css: dict[str, str]
    js: dict[str, str]


class Transformer:
    def __init__(self, ast: Ast, context: dict[str, Any], targets: list[str], keys):
        self.ast = ast
        self.context = context
        self.ctx = None
        self.targets = targets
        self.keys = keys
        self.content: Element = {
            "tag": None,
            "attrs": [],
            "childrens": [],
            "parent": None,
        }
        self.current: Element = self.content
        self.partials: dict[str, Partial] = {}
        self.c_target: str = ""
        self.groups: dict[str, Element] = {}

    def transform(self):
        self._transform(self.ast)

    def _transform(
        self,
        node: AstNode,
        xpath="",
        loops=[],
        depth=None,
        previous: bool | None = None,
        mode: Mode = "client",
        file=None,
        **kwargs,
    ):
        if len(self.targets) and not self.c_target:
            if not isinstance(node, dict):
                return
            GROUPS = get_attr(node, "s-group", default="").split(",")
            PARAMS = get_attr(node, "s-param", default="").split(",")
            tag = node["tag"]
            if (
                any(f"&{group}" in self.targets for group in GROUPS)
                or any(f"?{param}" in self.targets for param in PARAMS)
                or ((f"${file}" in self.targets) and tag and (tag not in EXCLUDES))
                or (xpath in self.targets)
            ):
                self.partials[xpath] = {"html": "", "css": {}, "js": {}}
                self.c_target = xpath
            else:
                mode = get_attr(node, "mode", default=mode)
                if mode == "server" and self.ctx is None:
                    self.ctx = MiniRacer()
                childrens = node.get("childrens", [])
                sfor = None

                for attr in node["attrs"]:
                    k, v = attr
                    if k.startswith("s-prop:"):
                        self.handle_sprop(k, v, None, mode)
                    elif k == "x-data":
                        self.handle_xdata(v, mode)
                    elif k == "s-for":
                        sfor = v
                store = {}
                if tag == "html" and self.ctx:
                    self.ctx.eval("var isServer = true;")
                elif tag == "With":
                    self.pack_with(node["attrs"], store)
                elif tag == "Default":
                    self.pack_defaults(node["attrs"], store)

                if sfor:
                    self.handle_sfor(
                        node,
                        childrens,
                        xpath=xpath,
                        loops=loops,
                        depth=depth,
                        mode=mode,
                        file=file,
                        **kwargs,
                    )
                else:
                    self.loop(
                        childrens,
                        xpath=xpath,
                        loops=loops,
                        depth=depth,
                        mode=mode,
                        file=file,
                        **kwargs,
                    )
                self.unpack_store(store)
                return

        if isinstance(node, str):
            if self.c_target:
                self.partials[self.c_target]["html"] += node
            else:
                self.current["childrens"].append(node)
            return
        elif isinstance(node, StrCode):
            string = escape(str(eval(node.code, self.context)))
            if self.c_target:
                self.partials[self.c_target]["html"] += string
            else:
                self.current["childrens"].append(string)
            return
        elif isinstance(node, Template):
            string = node.render(self.context)
            if self.c_target:
                self.partials[self.c_target]["html"] += string
            else:
                self.current["childrens"].append(string)
            return

        mode = get_attr(node, "mode", default=mode)
        if mode == "server" and self.ctx is None:
            self.ctx = MiniRacer()
        tag = node["tag"]
        attrs: PureAttrs = []
        childrens = node.get("childrens")

        show = get_attr(node, "s-show")
        if show and not eval(show.code, self.context):
            if self.c_target:
                self.partials[self.c_target]["html"] += (
                    f"<{tag} hidden></{tag}>" if childrens else f"<{tag} hidden />"
                )
                if xpath == self.c_target and tag and (tag not in EXCLUDES):
                    self.c_target = ""
            else:
                self.current["childrens"].append(
                    {
                        "tag": tag,
                        "attrs": [("hidden", None)],
                        "parent": self.current,
                        **({"childrens": []} if childrens else {}),
                    }
                )
            return False
        elif get_attr(node, "s-if") and not eval(
            get_attr(node, "s-if").code, self.context
        ):
            return False
        elif get_attr(node, "s-elif"):
            if previous is True:
                return True
            elif not eval(get_attr(node, "s-elif").code, self.context):
                return False
        elif get_attr(node, "s-else") is None and previous is True:
            return
        elif get_attr(node, "s-empty") is None and previous is True:
            return

        for attr in node["attrs"]:
            k, _ = attr
            if not k.startswith("x-") and not k.startswith("s-") and k != "mode":
                attrs.append(attr)

        text = None
        sfor = None

        for attr in node["attrs"]:
            k, v = attr
            if k.startswith("s-prop:"):
                self.handle_sprop(k, v, attrs, mode)
            elif k == "x-data":
                attrs.append(attr)
                self.handle_xdata(v, mode)
            elif k == "x-show":
                attrs.append(attr)
                if mode == "server" and self.ctx and not self.ctx.eval(v):
                    styles = get_attr(attrs, "style", default="").split(";")
                    styles.append("display:none!important")
                    set_attr(attrs, "style", ";".join(styles))
            elif k == "s-text":
                text = escape(eval(v.code, self.context))
            elif k == "x-text":
                attrs.append(attr)
                if mode == "server" and self.ctx:
                    text = escape(self.ctx.eval(v))
            elif k.startswith("s-bind:"):
                if k.split(":")[1] == "class":
                    set_attr(
                        attrs,
                        "class",
                        self.add_classes(
                            get_attr(attrs, "class", default=""),
                            [escape(eval(v.code, self.context))],
                        ),
                    )
                else:
                    value = eval(v.code, self.context)
                    if k.split(":")[1] == "x-prop":
                        value = dumps(value)
                    attrs.append((":".join(k.split(":")[1:]), escape(value)))
            elif k.startswith("s-toggle:"):
                val = eval(v.code, self.context)
                if val is True:
                    attrs.append((":".join(k.split(":")[1:]), None))
            elif k.startswith("x-bind:"):
                attrs.append(attr)
                if mode == "server" and self.ctx:
                    if k.split(":")[1] == "class":
                        if v.startswith("{"):
                            self.ctx.eval(
                                f"var classes = {v}; var klasses = []; for (let k in classes) {{ if (classes[k]) {{klasses.push(k)}} }};"
                            )
                            set_attr(
                                attrs,
                                "class",
                                self.add_classes(
                                    get_attr(attrs, "class", default=""),
                                    loads(self.ctx.eval("JSON.stringify(klasses)")),
                                ),
                            )
                        else:
                            set_attr(attrs, "class", escape(self.ctx.eval(v)))
                    else:
                        val = self.ctx.eval(v)
                        if val is not False:
                            attrs.append((k.split(":")[1], escape(val)))
            elif k == "s-k":
                attrs.append(("k", escape(loops[-1][1])))
                attrs.append(("x-prop:keys", escape(dumps(loops))))
            elif k.startswith("s-asset:"):
                attrs.append((k.split(":")[1], f"/{ASSET_URL}{asset_cache.get(v)[0]}"))
            elif k == "s-for":
                sfor = v
            elif k.startswith("x-"):
                attrs.append(attr)

        store = {}
        if tag == "html" and self.ctx:
            self.ctx.eval("var isServer = true;")
            attrs.append(("x-data", "{isServer: false, keys: []}"))
        elif tag == "With":
            self.pack_with(attrs, store)
        elif tag == "Default":
            self.pack_defaults(attrs, store)

        if self.c_target:
            if tag == "Css" or tag == "Sass":
                fname, _ = asset_cache[get_attr(node, "@")]
                self.partials[self.c_target]["css"][fname.split(".")[0]] = (
                    f"/{ASSET_URL}{fname}"
                )
            elif tag == "Js" or tag == "Ts":
                fname, _ = asset_cache[get_attr(node, "@")]
                self.partials[self.c_target]["js"][fname.split(".")[0]] = (
                    f"/{ASSET_URL}{fname}"
                )
            else:
                attributes = self.join_attrs(attrs)
                if isinstance(childrens, list):
                    if tag and (tag not in EXCLUDES):
                        self.partials[self.c_target]["html"] += f"<{tag}{attributes}>"
                    if sfor:
                        if not self.handle_sfor(
                            node,
                            childrens,
                            xpath=xpath,
                            loops=loops,
                            depth=depth,
                            mode=mode,
                            **kwargs,
                        ):
                            self.unpack_store(store)
                            return False
                    elif text:
                        self.partials[self.c_target]["html"] += text
                    else:
                        self.loop(
                            childrens,
                            xpath=xpath,
                            loops=loops,
                            depth=depth,
                            mode=mode,
                            **kwargs,
                        )
                    if tag and (tag not in EXCLUDES):
                        self.partials[self.c_target]["html"] += f"</{tag}>"

                    if xpath == self.c_target and tag and (tag not in EXCLUDES):
                        self.c_target = ""
                else:
                    self.partials[self.c_target]["html"] += f"<{tag}{attributes} />"
        elif tag == "Css" or tag == "Sass":
            fname, compiled = asset_cache[get_attr(node, "@")]
            asset_id = fname.split(".")[0]
            assets = self.groups[get_attr(node, "group")]["childrens"]
            exists = False
            for asset in assets:
                if get_attr(asset, "data-style-id") == asset_id:
                    exists = True
            if not exists:
                if DEBUG:
                    assets.append(
                        {
                            "tag": "link",
                            "attrs": [
                                ("rel", "stylesheet"),
                                ("href", f"/{ASSET_URL}{fname}"),
                                ("data-style-id", asset_id),
                            ],
                        }
                    )
                else:
                    assets.append(
                        {
                            "tag": "style",
                            "attrs": [("data-style-id", asset_id)],
                            "childrens": [compiled],
                        }
                    )
        elif tag == "Js" or tag == "Ts":
            fname, _ = asset_cache[get_attr(node, "@")]
            asset_id = fname.split(".")[0]
            remove_attr(attrs, "@")
            attrs.append(("type", "module"))
            attrs.append(("data-script-id", asset_id))
            self.current["childrens"].append(
                {
                    "tag": "script",
                    "attrs": attrs,
                    "childrens": [
                        f'import * as module from "/{ASSET_URL}{fname}"; Object.keys(module).forEach((key) => {{if(key == "cleanup"){{window["{asset_id}_cleanup"] = module[key]}} else {{window[key] = module[key]}}}});'
                    ],
                }
            )
        elif tag == "Tailwind":
            fname, _ = asset_cache[get_attr(node, "layout")]
            self.current["childrens"].append(
                {
                    "tag": "link",
                    "attrs": [
                        ("rel", "stylesheet"),
                        ("href", f"/{ASSET_URL}{fname}"),
                        ("data-tailwind-id", fname.split(".")[0]),
                    ],
                }
            )
        else:
            element: Element = {"tag": tag, "attrs": attrs, "parent": self.current}
            self.current["childrens"].append(element)
            if tag == "head":
                self.groups[tag] = element
            elif tag == "Group":
                group = get_attr(node, "name")
                if group != "head":
                    self.groups[get_attr(node, "name")] = element
            if isinstance(childrens, list):
                self.current = element
                element["childrens"] = []
                if sfor:
                    if not self.handle_sfor(
                        node,
                        childrens,
                        xpath=xpath,
                        loops=loops,
                        depth=depth,
                        mode=mode,
                        **kwargs,
                    ):
                        self.unpack_store(store)
                        return False
                elif text:
                    element["childrens"].append(text)
                else:
                    self.loop(
                        childrens,
                        xpath=xpath,
                        loops=loops,
                        depth=depth,
                        mode=mode,
                        **kwargs,
                    )
                if tag == "Helmet":
                    metas = deepcopy(element["childrens"])
                    for meta in metas:
                        if isinstance(meta, dict):
                            remove_attr(meta["attrs"], "x-head")
                    self.groups["head"]["childrens"] += metas
                    remove_attr(attrs, "group")
                self.current = element["parent"]

        self.unpack_store(store)
        return True

    def loop(self, childrens: list[AstNode], **kwargs):
        previous = None
        xpath = kwargs.pop("xpath")
        file = kwargs.get("file")
        kwargs["depth"] = 0 if kwargs["depth"] is None else kwargs["depth"] + 1

        el_index = {} if kwargs.get("el_index") is None else kwargs.get("el_index")
        for index, children in enumerate(childrens):
            _xpath = copy(xpath)
            if isinstance(children, dict):
                tag = children["tag"]
                _file = children.get("file") or file
                kwargs["file"] = _file
                if tag and (tag not in EXCLUDES):
                    el_index.setdefault(tag, 0)
                    el_index[tag] += 1
                    k = get_attr(children, "s-k")
                    _index = (
                        f"@k={kwargs['loops'][-1][1]}" if k is None else el_index[tag]
                    )
                    _xpath += f"/{tag}[{_index}]"
                    kwargs["el_index"] = None
                else:
                    kwargs["el_index"] = el_index
                if (
                    len(self.targets)
                    and not self.c_target
                    and (
                        not (
                            self.is_required(kwargs["depth"], index, _xpath)
                            or (f"${_file}" in self.targets)
                        )
                    )
                ):
                    if isinstance(kwargs.get("el_index"), dict):

                        def traverse(node: Element):
                            for children in node.get("childrens", []):
                                if isinstance(children, dict):
                                    tag = children["tag"]
                                    if tag and (tag not in EXCLUDES):
                                        el_index.setdefault(tag, 0)
                                        el_index[tag] += 1
                                    else:
                                        traverse(children)

                        traverse(children)
                    continue
            _return = self._transform(
                node=children, xpath=_xpath, previous=previous, **kwargs
            )
            previous = _return if isinstance(children, dict) else previous

    def handle_sprop(
        self, k: str, v: str | CodeType, attrs: PureAttrs | None, mode: Mode
    ):
        if mode == "server" and self.ctx:
            prop = k.split(":")[1]
            value = dumps(eval(v.code, self.context))
            self.ctx.eval(f"var {prop} = JSON.parse('{value.replace("'","\\'")}');")
            if isinstance(attrs, list):
                attrs.append((f"x-prop:{prop}", escape(value)))

    def handle_xdata(self, v: str, mode: str):
        if mode == "server" and self.ctx and v.strip().startswith("{"):
            self.ctx.eval(
                f"var data = {v}; for (let k in data) {{ globalThis[k] = data[k] }};"
            )

    def handle_sfor(self, node: AstNode, childrens, **kwargs):
        sfor = get_attr(node, "s-for")
        skey = get_attr(node, "s-key")
        array: Iterable = None
        for key in self.keys:
            if kwargs["xpath"] == key[0]:
                array = eval(get_attr(node, "s-of").code, self.context, {"key": key[1]})
        if not array:
            array = eval(get_attr(node, "s-in").code, self.context)
        el_index = {}
        kwargs["el_index"] = el_index

        outer = self.context.get(sfor)
        for index, item in enumerate(array):
            self.context[sfor] = item
            self.context["index"] = index
            if skey:
                loops = [
                    *kwargs["loops"],
                    [kwargs["xpath"], eval(skey.code, self.context)],
                ]
                kwargs["loops"] = loops
            self.loop(childrens, **kwargs)
        self.context[sfor] = outer
        if len(array):
            return True

    def pack_with(self, attrs: Codes, store: dict[str, Any]):
        for k, v in attrs:
            store[k] = self.context.get(k)
            self.context[k] = eval(v.code, self.context)

    def pack_defaults(self, attrs: Codes, store: dict[str, Any]):
        for k, v in attrs:
            if not self.context.get(k):
                store[k] = self.context.get(k)
                self.context[k] = eval(v.code, self.context)

    def unpack_store(self, store: dict[str, Any]):
        for k in store:
            self.context[k] = store[k]

    def add_classes(self, string: str, classes):
        klasses = string.strip().split(" ")
        for klass in classes:
            if klass and klass not in klasses:
                klasses.append(klass)
        return " ".join(klasses)

    def join_attrs(self, attrs: PureAttrs):
        return "".join(
            map(
                lambda attr: f' {attr[0]}="{attr[1]}"' if attr[1] else f" {attr[0]}",
                attrs,
            )
        )

    def is_required(self, depth: int, index: int, xpath: str):
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
            elif target.startswith("/"):
                if target.startswith(xpath):
                    return True
        return False

    def compile_content(self):
        content = {"html": ""}

        def compile(node: Element | str, content):
            if not isinstance(node, dict):
                content["html"] += str(node)
            else:
                tag = node["tag"]
                childrens = node.get("childrens")
                attributes = self.join_attrs(node["attrs"])
                if isinstance(childrens, list):
                    if tag and (tag not in EXCLUDES):
                        content["html"] += f"<{tag}{attributes}>"
                    for children in childrens:
                        compile(children, content)
                    if tag and (tag not in EXCLUDES):
                        content["html"] += f"</{tag}>"
                else:
                    content["html"] += f"<{tag}{attributes} />"

        compile(self.content, content)
        return content["html"]
