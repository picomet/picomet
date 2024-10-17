from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import get_resolver

from picomet.compiler import parse_patterns, reset_cache
from picomet.parser import compile_tailwind, twlayouts

BASE_DIR: Path = settings.BASE_DIR


class Command(BaseCommand):
    help = "Recompile development cache"

    def handle(self, *args: list[Any], **options: dict[str, Any]) -> None:
        reset_cache()

        parse_patterns(get_resolver().url_patterns)

        for layout in twlayouts:
            compile_tailwind(layout)
