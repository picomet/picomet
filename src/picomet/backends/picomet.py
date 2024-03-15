from json import loads
from typing import Any

from django.http import HttpRequest
from django.template import Origin, TemplateDoesNotExist
from django.template.backends.base import BaseEngine as BaseBackend
from django.template.backends.django import reraise
from django.template.backends.utils import csrf_input_lazy, csrf_token_lazy
from django.template.base import UNKNOWN_SOURCE
from django.template.engine import Engine
from django.utils.functional import cached_property
from django.utils.module_loading import import_string

from picomet.parser import CometParser
from picomet.transformer import Transformer


class Template:
    def __init__(self, template_string, origin=None, name=None, engine=None):
        if origin is None:
            origin = Origin(UNKNOWN_SOURCE)
        self.name = name
        self.origin = origin
        self.engine = engine
        self.source = str(template_string)  # May be lazy

    def render(self, context: dict[str, Any], targets: list[str], keys):
        parser = CometParser()
        parser.feed(self.source, self.origin.name)
        transformer = Transformer(parser.ast, context, targets, keys)
        transformer.transform()
        return transformer.contents if len(targets) else transformer.compile_content()


class PicometEngine(Engine):
    def __init__(self, *args, **kwargs):
        kwargs.setdefault("app_dirs", False)
        kwargs.setdefault("loaders", [])
        kwargs["loaders"] += [
            "picomet.loaders.FilesystemLoader",
            "picomet.loaders.AppdirLoader",
        ]
        self.components = kwargs.pop("components", {})
        super().__init__(*args, **kwargs)

    def get_template(self, template_name):
        """
        Return a compiled Template object for the given template name,
        handling template inheritance recursively.
        """
        template, origin = self.find_template(template_name)
        if not hasattr(template, "render"):
            # template needs to be compiled
            template = Template(template, origin, template_name, engine=self)
        return template

    @cached_property
    def imported_context_processors(self):
        return [import_string(path) for path in self.context_processors]


class PicometTemplates(BaseBackend):
    app_dirname = "comets"

    def __init__(self, params):
        params = params.copy()
        options = params.pop("OPTIONS").copy()
        super().__init__(params)
        self.engine = PicometEngine(self.dirs, **options)

    def from_string(self, template_code):
        return Renderer(self.engine.from_string(template_code), self)

    def get_template(self, template_name):
        try:
            return Renderer(self.engine.get_template(template_name), self)
        except TemplateDoesNotExist as exc:
            reraise(exc, self)


class Renderer:
    def __init__(self, template, backend):
        self.template: Template = template
        self.backend: PicometTemplates = backend

    @property
    def origin(self):
        return self.template.origin

    def render(self, context: dict[str, Any] = {}, request: HttpRequest = None):
        if request is not None:
            context["csrf_input"] = csrf_input_lazy(request)
            context["csrf_token"] = csrf_token_lazy(request)
            for context_processor in self.backend.engine.imported_context_processors:
                context.update(context_processor(request))
        return self.template.render(
            context,
            request.targets,
            loads(request.headers.get("Keys", "[]")),
        )
