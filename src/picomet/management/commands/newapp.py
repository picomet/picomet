import shutil

from django.conf import settings
from django.core.management import call_command
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = "Create new app in the apps folder"

    def add_arguments(self, parser):
        parser.add_argument("app", nargs="+", type=str, help="new app name")

    def handle(self, *args, **options):
        appname = options["app"][0]
        BASE_DIR = settings.BASE_DIR
        call_command("startapp", appname)
        oldapp = BASE_DIR / appname
        newapp = BASE_DIR / "apps" / appname
        shutil.move(oldapp, newapp)
