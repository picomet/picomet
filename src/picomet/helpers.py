import base64
import os
from pathlib import Path

from django.conf import settings

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


def read_source(path: str) -> str:
    name, ext = os.path.splitext(path)
    if ext in PLAINTEXT_FILES:
        with open(path) as f:
            content = f.read()
    else:
        with open(path, "rb") as f:
            content = base64.b64encode(f.read()).decode("utf-8")
    return content
