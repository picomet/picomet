import functools
import json

from django.http import HttpRequest, HttpResponseRedirect, JsonResponse
from django.urls import reverse
from furl import furl


def normaluser_required(function):
    @functools.wraps(function)
    def wrapper(request: HttpRequest, *args, **kwargs):
        user = request.user
        REFERER = request.META.get("HTTP_REFERER", "/")
        if user.is_authenticated and not user.is_staff:
            return function(request, *args, **kwargs)
        if request.targets:
            if request.path == furl(REFERER).path:
                return JsonResponse(
                    {"redirect": reverse("core:home"), "update": True},
                    headers={"Targets": json.dumps(request.targets)},
                )
            return JsonResponse(
                {"redirect": furl(REFERER).set({"v": "login"}).url, "update": False}
            )
        return HttpResponseRedirect(
            furl(REFERER or reverse("core:home")).set({"v": "login"}).url
        )

    return wrapper
