from importlib.metadata import version

from django.core.management.utils import get_random_secret_key
from jinja2 import Environment
from jinja2.ext import Extension


class VarsExtension(Extension):
    """This extension adds required vars for picomet starter."""

    def __init__(self, environment: Environment) -> None:
        super().__init__(environment)
        environment.globals["DJ_SECRET_KEY"] = get_random_secret_key()
        environment.globals["PICOMET_VERSION"] = version("picomet")
        environment.globals["DJANGO_VERSION"] = version("django")
