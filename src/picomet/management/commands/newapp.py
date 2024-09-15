import shutil
from typing import Any, TypedDict, Unpack

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Options(TypedDict):
    app: list[str]


class Command(BaseCommand):
    help = "Create new app in the apps folder"

    def add_arguments(self, parser: Any) -> None:
        parser.add_argument("app", nargs="+", type=str, help="new app name")

    def handle(self, *args: list[Any], **options: Unpack[Options]) -> None:
        appname = options["app"][0]
        BASE_DIR = settings.BASE_DIR
        call_command("startapp", appname)
        oldapp = BASE_DIR / appname
        newapp = BASE_DIR / "apps" / appname
        shutil.move(oldapp, newapp)
