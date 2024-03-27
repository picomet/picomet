from collections.abc import Callable
from json import loads

from django.http import HttpRequest

from picomet import call_action
from picomet.http import PicometResponseRedirect
from picomet.shortcuts import Redirect


class CommonMiddleware:
    def __init__(self, get_response: Callable):
        self.get_response = get_response

    def __call__(self, request: HttpRequest):
        request.targets = loads(request.headers.get("Targets", "[]"))
        request.action = request.headers.get("Action")

        try:
            if request.method != "GET":
                call_action(request)
        except Redirect as e:
            return PicometResponseRedirect(e.args[0], e.args[1])

        response = self.get_response(request)

        return response
