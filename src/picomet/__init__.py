from importlib import import_module

from django.http import HttpRequest

cache = {}


def call_action(request: HttpRequest):
    action = request.headers.get("Action")
    if action:
        action_module, action_name = action.split(".")
        module = f"{action_module}.actions"
        if not cache.get(module):
            try:
                actions = import_module(module)
                if hasattr(actions, action_name):
                    targets = getattr(actions, action_name)(request)
                    for target in targets:
                        if target not in request.targets:
                            request.targets.append(target)
            except ModuleNotFoundError:
                pass
        else:
            actions = cache[module]
            if hasattr(actions, action_name):
                targets = getattr(actions, action_name)(request)
                for target in targets:
                    if target not in request.targets:
                        request.targets.append(target)
