from django.http import JsonResponse
from django.utils.cache import patch_vary_headers


class PicometResponseRedirect(JsonResponse):
    def __init__(self, redirect_to: str, update: bool = True, headers: dict = {}):
        super().__init__({"redirect": redirect_to, "update": update}, headers=headers)
        patch_vary_headers(self, ("Targets", "Action"))
