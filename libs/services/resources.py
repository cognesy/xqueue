"""Access to packaged xqueue resources."""

from __future__ import annotations

from contextlib import contextmanager
from importlib import resources
from importlib.resources.abc import Traversable
from pathlib import Path
from typing import Iterator

RESOURCE_PACKAGE = "xqueue_resources"


def resource_file(*parts: str) -> Traversable:
    """Return a traversable packaged resource."""

    return resources.files(RESOURCE_PACKAGE).joinpath(*parts)


@contextmanager
def resource_path(*parts: str) -> Iterator[Path]:
    """Expose a packaged resource as a filesystem path for libraries that need one."""

    with resources.as_file(resource_file(*parts)) as path:
        yield path
