import timeit
from pathlib import Path
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand
from django.template.loader import get_template
from django.urls import URLPattern, URLResolver, get_resolver
from django.urls.resolvers import RoutePattern

from picomet.backends.picomet import Renderer
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
        build_assets_dir = build_dir / "assets"
        build_commets_dir = build_dir / "comets"
        for d in [picomet_dir, build_dir, build_assets_dir, build_commets_dir]:
            if not d.is_dir():
                d.mkdir()

        parse_patterns(get_resolver().url_patterns)

        for layout in twlayouts:
            compile_tailwind(layout)

        save_patterns(get_resolver().url_patterns)
        self.stdout.write(f"✓ built in {round(timeit.default_timer() - start, 2)}s")
        if options["verbose"]:
            self.stdout.write(f"✓ location: {build_dir}")
            assets = len(list(build_assets_dir.glob("*")))
            self.stdout.write(f"✓ assets: {assets}")
            comets = len(list(build_commets_dir.glob("*")))
            self.stdout.write(f"✓ comets: {comets}")


def save_patterns(url_patterns: list[URLResolver | URLPattern]) -> None:
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
            ast = ast_cache[html_file]
            save_commet(html_file, ast, BASE_DIR / ".picomet/build/comets")
        elif isinstance(url_pattern, URLResolver):
            save_patterns(
                getattr(
                    url_pattern.urlconf_name,
                    "urlpatterns",
                    url_pattern.urlconf_name,
                ),
            )
