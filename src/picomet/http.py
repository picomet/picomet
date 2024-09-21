from json import dumps
from urllib.parse import urlparse

from django.core.exceptions import DisallowedRedirect
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.utils.cache import patch_vary_headers
from django.utils.encoding import iri_to_uri


class PicometResponseRedirect(HttpResponse):
    status_code = 302
    allowed_schemes = ["http", "https", "ftp"]
    url = property(lambda self: self["Location"])

    def __init__(
        self,
        request: HttpRequest,
        redirect_to: str,
        update: bool = True,
        headers: dict = {},
    ):
        self.request: HttpRequest = request
        if request.targets or request.action:
            data = dumps({"redirect": redirect_to, "update": update})
            super().__init__(content=data, headers=headers)
            patch_vary_headers(self, ("Targets", "Action"))
        else:
            super().__init__(headers=headers)
            self["Location"] = iri_to_uri(redirect_to)
            parsed = urlparse(str(redirect_to))
            if parsed.scheme and parsed.scheme not in self.allowed_schemes:
                raise DisallowedRedirect(
                    f"Unsafe redirect to URL with protocol '{parsed.scheme}'"
                )

    def __repr__(self) -> str:
        if self.request.targets or self.request.action:
            return super().__repr__(self)
        else:
            return HttpResponseRedirect.__repr__(self)
