import os
import site
import sys
import threading
import time
from copy import deepcopy
from itertools import chain
from pathlib import Path
from typing import Any

from asgiref.sync import async_to_sync
from django.apps import apps
from django.conf import settings
from django.template import engines
from django.template.loader import get_template
from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.resolvers import RoutePattern

from picomet.backends.picomet import Renderer
from picomet.helpers import get_comet_id, read_source
from picomet.loaders import cache_file, fcache, fhash
from picomet.parser import (
    ASSETFILES_DIRS,
    STATIC_URL,
    CometParser,
    asset_cache,
    compile_asset,
    compile_resouce,
    compile_tailwind,
    dgraph,
    twlayouts,
)
from picomet.utils import mdhash

try:
    from channels.layers import get_channel_layer
except ImportError:
    pass

BASE_DIR: Path = settings.BASE_DIR
picomet_dir = BASE_DIR / ".picomet"
cache_dir = picomet_dir / "cache"


def setup() -> None:
    if len(sys.argv) > 1 and sys.argv[1] == "runserver":

        def watch(path: str) -> None:
            from watchdog.events import FileSystemEvent, FileSystemEventHandler
            from watchdog.observers import Observer

            class EventHandler(FileSystemEventHandler):
                def __init__(self, *args: list[Any], **kwargs: dict[str, Any]):
                    super().__init__(*args, **kwargs)
                    self.time: dict[str, dict[str, float]] = {"modified": {}}

                def dispatch(self, event: FileSystemEvent) -> None:
                    src_path = event.src_path
                    _, ext = os.path.splitext(src_path)
                    tm = time.time()
                    if event.event_type == "modified":
                        self.time["modified"][src_path] = tm
                    if (
                        (event.event_type == "closed")
                        and self.time["modified"].get(src_path)
                        and ((tm - self.time["modified"][src_path]) <= 1)
                        and is_file_changed(src_path)
                    ):
                        compile_file(src_path)

            event_handler = EventHandler()
            observer = Observer()
            observer.schedule(event_handler, path, recursive=True)
            observer.start()
            try:
                while True:
                    time.sleep(1)
            except KeyboardInterrupt:
                observer.stop()
            observer.join()

        if not picomet_dir.is_dir():
            picomet_dir.mkdir()
        if not cache_dir.is_dir():
            cache_dir.mkdir()

            comets_dir = cache_dir / "comets"
            assets_dir = cache_dir / "assets"
            for folder in [comets_dir, assets_dir]:
                if not folder.is_dir():
                    folder.mkdir()

            parse_patterns(get_resolver().url_patterns)

            for layout in twlayouts:
                compile_tailwind(layout)
        else:

            def validate_cache() -> None:
                for file in fhash:
                    if Path(file).exists():
                        content = read_source(file)
                        if mdhash(content, 8) != fhash[file]:
                            cache_file(file, content)
                            compile_file(file)

            thread = threading.Thread(target=validate_cache, daemon=True)
            thread.start()

        if settings.DEBUG:
            package_dirs = [
                site.getusersitepackages(),
                *[path for path in site.getsitepackages()],
            ]

            comet_dirs = list(
                chain.from_iterable(
                    [
                        [str(d) for d in loader.get_dirs()]
                        for loader in engines["picomet"].engine.template_loaders
                    ]
                )
            )
            usr_comet_dirs = comet_dirs.copy()
            for comet_dir in comet_dirs:
                for package_dir in package_dirs:
                    if Path(comet_dir).is_relative_to(package_dir):
                        if comet_dir in usr_comet_dirs:
                            usr_comet_dirs.remove(comet_dir)
            for d in usr_comet_dirs:
                if os.path.isdir(d):
                    thread = threading.Thread(target=watch, args=(d,), daemon=True)
                    thread.start()

            asset_dirs = [
                *[str(d) for d in ASSETFILES_DIRS],
                *[os.path.join(app.path, "assets") for app in apps.get_app_configs()],
            ]
            usr_asset_dirs = asset_dirs.copy()
            for asset_dir in asset_dirs:
                for package_dir in package_dirs:
                    if Path(asset_dir).is_relative_to(package_dir):
                        if asset_dir in usr_asset_dirs:
                            usr_asset_dirs.remove(asset_dir)
            for d in usr_asset_dirs:
                if os.path.isdir(d):
                    thread = threading.Thread(target=watch, args=(d,), daemon=True)
                    thread.start()


def parse_patterns(url_patterns: list[URLResolver | URLPattern]) -> None:
    for url_pattern in url_patterns:
        if (
            isinstance(url_pattern, URLPattern)
            and isinstance(url_pattern.pattern, RoutePattern)
            and hasattr(url_pattern.callback, "template_name")
        ):
            renderer: Renderer = get_template(
                url_pattern.callback.template_name, using="picomet"
            )
            html_file = renderer.origin.name
            with open(html_file) as f:
                cache_file(html_file, f.read())
            parser = CometParser()
            parser.feed(fcache[html_file], html_file)
        elif isinstance(url_pattern, URLResolver):
            parse_patterns(
                getattr(
                    url_pattern.urlconf_name,
                    "urlpatterns",
                    url_pattern.urlconf_name,
                ),
            )


def is_file_changed(path: str) -> bool:
    content = read_source(path)
    cached = fhash.get(path)
    if cached:
        changed = mdhash(content, 8) != cached
        cache_file(path, content)
        return changed
    else:
        cache_file(path, content)
        return True


def compile_file(path: str) -> None:
    _, ext = os.path.splitext(path)

    if (
        ext == ".html"
        and (cache_dir / "comets" / f"{get_comet_id(path)}.json").exists()
    ):
        parser = CometParser()
        parser.feed(fcache[path], path, use_cache=False)
        dmap = deepcopy(dgraph)

        def update(p: str) -> None:
            for d in dmap.get(p, []):
                if not fcache.get(d):
                    if os.path.exists(d):
                        with open(d) as f:
                            cache_file(d, f.read())
                    else:
                        return
                parser = CometParser()
                parser.feed(fcache[d], d, use_cache=False)
                update(d)

        update(path)

        if path in twlayouts.keys():
            compile_tailwind(path)
        else:
            compiled = []

            def traverse(f: str) -> None:
                if f in twlayouts.keys():
                    if f not in compiled:
                        compile_tailwind(f)
                        compiled.append(f)
                        hmr_send_message(
                            {
                                "staticUrl": STATIC_URL,
                                "tailwind": asset_cache[f][0],
                            }
                        )

                for layout in twlayouts.keys():
                    if f in dgraph.get(layout, []):
                        if layout not in compiled:
                            compile_tailwind(layout)
                            compiled.append(layout)
                            hmr_send_message(
                                {
                                    "staticUrl": STATIC_URL,
                                    "tailwind": asset_cache[layout][0],
                                }
                            )
                for d in dgraph.get(f, []):
                    traverse(d)

            traverse(path)

        hmr_send_message({"layout" if parser.is_layout else "template": path})
    elif (ext == ".js" or ext == ".ts") and len(dgraph.get(path, [])):
        compile_asset(path)
        hmr_send_message(
            {
                "staticUrl": STATIC_URL,
                "script": asset_cache[path][0],
            }
        )
    elif (ext == ".css" or ext == ".scss") and len(dgraph.get(path, [])):
        compile_asset(path)
        hmr_send_message(
            {
                "staticUrl": STATIC_URL,
                "style": asset_cache[path][0],
            }
        )
    elif ext == ".css" and path.endswith(".tailwind.css"):
        for layout in twlayouts:
            if path == os.path.join(
                os.path.dirname(layout),
                f"{twlayouts[layout]}.tailwind.css",
            ):
                compile_tailwind(layout)
                hmr_send_message(
                    {
                        "staticUrl": STATIC_URL,
                        "tailwind": asset_cache[layout][0],
                    }
                )
    elif dgraph.get(path):
        compile_resouce(path)
        hmr_send_message(
            {
                "staticUrl": STATIC_URL,
                "link": asset_cache[path][0],
            }
        )


def hmr_send_message(message: dict) -> None:
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        "hmr",
        {"type": "send.message", "message": message},
    )
