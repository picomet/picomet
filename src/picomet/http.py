from django.http import JsonResponse


class PicometResponseRedirect(JsonResponse):
    def __init__(self, redirect_to: str, update: bool = True):
        super().__init__({"redirect": redirect_to, "update": update})
