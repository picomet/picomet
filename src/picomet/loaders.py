import sys
from collections.abc import Iterable
from json import dumps, loads
from pathlib import Path
from typing import override

from django.conf import settings
from django.core.exceptions import SuspiciousFileOperation
from django.template import Origin, TemplateDoesNotExist
from django.template.engine import Engine
from django.template.loaders.base import Loader
from django.template.utils import get_app_template_dirs
from django.utils._os import safe_join

from picomet.backends.picomet import Template
from picomet.utils import mdhash

TEST = len(sys.argv) > 1 and sys.argv[1] == "test"

BASE_DIR: Path = settings.BASE_DIR

cache_dir = BASE_DIR / ".picomet/cache"

fcache: dict[str, str] = {}
fhash: dict[str, str] = {}
if len(sys.argv) > 1 and sys.argv[1] == "runserver":
    try:
        with open(cache_dir / "fhash.json") as f:
            fhash = loads(f.read())
    except FileNotFoundError:
        pass


def cache_file(path: str, content: str) -> None:
    fcache[path] = content
    if len(sys.argv) <= 1 or sys.argv[1] != "build":
        fhash[path] = mdhash(fcache[path], 8)
        with open(cache_dir / "fhash.json", "w") as f:
            f.write(dumps(fhash))


class BaseLoader(Loader):
    def get_template(
        self, template_name: str, skip: list[Origin] | None = None
    ) -> Template:
        """
        Call self.get_template_sources() and return a Template object for
        the first template matching template_name. If skip is provided, ignore
        template origins in skip. This is used to avoid recursion during
        template extending.
        """
        tried = []

        origin: Origin

        for origin in self.get_template_sources(template_name):
            if skip is not None and origin in skip:
                tried.append((origin, "Skipped to avoid recursion"))
                continue

            try:
                contents = self.get_contents(origin)
            except TemplateDoesNotExist:
                tried.append((origin, "Source does not exist"))
                continue
            else:
                return Template(
                    contents,
                    origin,
                    origin.template_name,
                    self.engine,
                )

        raise TemplateDoesNotExist(template_name, tried=tried)


class FilesystemLoader(BaseLoader):
    def __init__(self, engine: Engine):
        super().__init__(engine)

    def get_dirs(self) -> list[str]:
        return self.engine.dirs

    def get_contents(self, origin: Origin) -> str:
        try:
            cached = fcache.get(origin.name)
            if not cached:
                if (not sys.argv[0].endswith("manage.py") or TEST) and Path(
                    origin.name
                ).exists():
                    return ""
                with open(origin.name, encoding=self.engine.file_charset) as fp:
                    cache_file(origin.name, fp.read())
                    return fcache[origin.name]
            return cached
        except FileNotFoundError:
            raise TemplateDoesNotExist(origin)

    def get_template_sources(self, template_name: str) -> Iterable[Origin]:
        """
        Return an Origin object pointing to an absolute path in each directory
        in template_dirs. For security reasons, if a path doesn't lie inside
        one of the template_dirs it is excluded from the result set.
        """
        for template_dir in self.get_dirs():
            try:
                name = safe_join(template_dir, template_name)
            except SuspiciousFileOperation:
                # The joined path was located outside of this template_dir
                # (it might be inside another one, so this isn't fatal).
                continue

            yield Origin(
                name=name,
                template_name=template_name,
                loader=self,
            )


class AppdirLoader(FilesystemLoader):
    @override
    def get_dirs(self) -> list[str]:
        return list(get_app_template_dirs("comets"))
