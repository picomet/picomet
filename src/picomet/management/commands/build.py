import timeit
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.urls import get_resolver

from picomet.compiler import parse_patterns
from picomet.parser import ast_cache, compile_tailwind, save_commet, twlayouts

BASE_DIR: Path = settings.BASE_DIR


class Command(BaseCommand):
    help = "Build picomet for production"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument(
            "--verbose",
            action="store_true",
            default=False,
            dest="verbose",
            help="Verbose mode",
        )

    def handle(self, *args: list[Any], **options: dict[str, Any]) -> None:
        start = timeit.default_timer()
        settings.DEBUG = False
        picomet_dir = BASE_DIR / ".picomet"
        build_dir = picomet_dir / "build"
        build_comets_dir = build_dir / "comets"
        build_maps_dir = build_dir / "maps"
        build_assets_dir = build_dir / "assets"
        for d in [
            picomet_dir,
            build_dir,
            build_comets_dir,
            build_maps_dir,
            build_assets_dir,
        ]:
            if not d.is_dir():
                d.mkdir()

        parse_patterns(get_resolver().url_patterns)

        for layout in twlayouts:
            compile_tailwind(layout)
            save_commet(layout, ast_cache[layout], build_comets_dir)

        self.stdout.write(f"✓ built in {round(timeit.default_timer() - start, 2)}s")
        if options["verbose"]:
            self.stdout.write(f"✓ location: {build_dir}")
            comets = len(list(build_comets_dir.glob("*")))
            self.stdout.write(f"✓ comets: {comets}")
            assets = len(list(build_assets_dir.glob("*")))
            self.stdout.write(f"✓ assets: {assets}")
