import functools
import os
from collections.abc import Callable
from typing import Any, Protocol, cast

from django.http import HttpRequest, HttpResponse


class View(Protocol):
    template_name: str

    def __call__(
        self, request: HttpRequest, *args: list[Any], **kwargs: dict[str, Any]
    ) -> HttpResponse: ...


def template(template_name: str) -> Callable[[View], View]:
    def deco(function: View) -> View:
        _template_name = template_name
        if len(os.path.basename(_template_name).split(".")) == 1:
            _template_name = f"{_template_name}.html"
        function.template_name = _template_name

        @functools.wraps(function)
        def wrapper(
            request: HttpRequest, *args: list[Any], **kwargs: dict[str, Any]
        ) -> HttpResponse:
            request.template_name = _template_name
            return function(request, *args, **kwargs)

        return cast(View, wrapper)

    return deco
