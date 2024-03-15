import functools
import os
from collections.abc import Callable

from django.http import HttpRequest


def template(template_name: str):
    def deco(function: Callable):
        _template_name = template_name
        if len(os.path.basename(_template_name).split(".")) == 1:
            _template_name = f"{_template_name}.html"
        function.template_name = _template_name

        @functools.wraps(function)
        def wrapper(request: HttpRequest, *args, **kwargs):
            request.template_name = _template_name
            return function(request, *args, **kwargs)

        return wrapper

    return deco
