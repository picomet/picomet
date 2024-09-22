from pathlib import Path

from django.conf import settings

from picomet.utils import mdhash

BASE_DIR: Path = settings.BASE_DIR


def get_comet_id(path: str) -> str:
    path = Path(path)
    if path.is_relative_to(BASE_DIR):
        rel = path.relative_to(BASE_DIR).as_posix()
        return mdhash(rel, 8)
    else:
        return mdhash(path.as_posix(), 8)
