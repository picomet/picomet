from typing import Any

from django.http import HttpRequest, HttpResponse, JsonResponse
from django.template import loader

from picomet.backends.picomet import Renderer


def render(
    request: HttpRequest,
    context: dict[str, Any] = {},
    content_type: str | None = None,
    status: int | None = None,
) -> HttpResponse | JsonResponse:
    template: Renderer = loader.get_template(request.template_name, using="picomet")
    content = template.render(context, request)
    if not isinstance(content, dict):
        return HttpResponse(content, content_type, status)
    return JsonResponse(
        content,
        content_type=content_type,
        status=status,
        headers={"Vary": "Targets,Action"},
    )
