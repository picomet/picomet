from typing import Any

from django.contrib.staticfiles.finders import FileSystemFinder
from django.core.checks.messages import CheckMessage
from django.core.files.storage import FileSystemStorage

from picomet.parser import assets_dir


class AssetFinder(FileSystemFinder):
    """
    A asset files finder that looks in the assets directory of each app
    and uses the ``ASSETFILES_DIRS`` setting to locate files.
    """

    def __init__(
        self, app_names: list[str] = [], *args: list[Any], **kwargs: dict[str, Any]
    ):
        # List of locations with asset files
        self.locations: list[tuple[str, str]] = []
        # Maps dir paths to an appropriate storage instance
        self.storages = {}
        for root in [assets_dir.as_posix()]:
            if isinstance(root, list | tuple):
                prefix, root = root
            else:
                prefix = ""
            if (prefix, root) not in self.locations:
                self.locations.append((prefix, root))
        for prefix, root in self.locations:
            filesystem_storage = FileSystemStorage(location=root)
            filesystem_storage.prefix = prefix
            self.storages[root] = filesystem_storage

    def check(self, **kwargs: Any) -> list[CheckMessage]:
        return []
