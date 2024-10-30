import base64
import os
from itertools import chain
from pathlib import Path

from django.conf import settings
from django.template import engines

from picomet.utils import mdhash

BASE_DIR: Path = settings.BASE_DIR

PLAINTEXT_FILES = [".html", ".js", ".ts", ".css", ".scss"]


def get_comet_id(path: str) -> str:
    path = Path(path)
    if path.is_relative_to(BASE_DIR):
        rel = path.relative_to(BASE_DIR).as_posix()
        return mdhash(rel, 8)
    else:
        return mdhash(path.as_posix(), 8)


def find_comet_name(path: str) -> str | None:
    comet_dirs = list(
        chain.from_iterable(
            [
                [str(d) for d in loader.get_dirs()]
                for loader in engines["picomet"].engine.template_loaders
            ]
        )
    )
    for comet_dir in comet_dirs:
        if path.startswith(comet_dir):
            return path[len(comet_dir) + 1 :]
    return None


def read_source(path: str) -> str:
    name, ext = os.path.splitext(path)
    if ext in PLAINTEXT_FILES:
        with open(path) as f:
            content = f.read()
    else:
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
    return content
