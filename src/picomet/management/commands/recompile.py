import shutil
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import get_resolver
from picomet.compiler import compile_tailwind, parse_patterns
from picomet.parser import twlayouts

BASE_DIR: Path = settings.BASE_DIR


class Command(BaseCommand):
    help = "Recompile development cache"

    def handle(self, *args, **options):
        picomet_dir = BASE_DIR / ".picomet"
        cache_dir = picomet_dir / "cache"
        if cache_dir.is_dir():
            shutil.rmtree(cache_dir)
        assets_dir = cache_dir / "assets"
        comets_dir = cache_dir / "comets"
        for d in [picomet_dir, cache_dir, assets_dir, comets_dir]:
            if not d.is_dir():
                d.mkdir()

        parse_patterns(get_resolver().url_patterns)

        for layout in twlayouts:
            compile_tailwind(layout)
