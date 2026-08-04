"""Lifecycle-safe public xqueue client."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from pathlib import Path
from typing import TYPE_CHECKING, TypeVar, cast

from xqueue.core.errors import XqueueClosedError

if TYPE_CHECKING:
    from xqueue.controller.api import Controller
    from xqueue.jobs.api import Jobs
    from xqueue.maintenance.api import Maintenance
    from xqueue.queues.api import Queues
    from xqueue.runtime.composition import Runtime
    from xqueue.workers.api import Workers
    from xqueue.workspace.api import Workspace

    # The typed location, distinct from the `workspace` capability facet above.
    from xqueue.workspace.paths import Workspace as WorkspaceLocation

FacetT = TypeVar("FacetT")


class Xqueue:
    """One in-process client over one owned xqueue runtime."""

    def __init__(self, runtime: Runtime) -> None:
        self._runtime = runtime
        self._facets: dict[str, object] = {}
        self._closed = False

    @classmethod
    def open(
        cls,
        *,
        config_path: Path | None = None,
        env_name: str | None = None,
        overrides: Mapping[str, str] | None = None,
        workspace_root: Path | None = None,
        use_workspace_instance: bool = False,
        workspace: WorkspaceLocation | None = None,
        configure_process_logging: bool = False,
    ) -> Xqueue:
        """Resolve configuration and open one owned runtime.

        ``config_path``, ``env_name``, and ``overrides`` are the SDK spelling of
        the CLI's ``--config``, ``--env``, and ``--set``: a file that replaces
        the packaged base, a packaged overlay to layer over it, and dotted paths
        that win over everything.

        Pass ``workspace`` to skip resolution entirely, when the caller has
        already decided — two clients on two workspaces coexist in one process,
        because nothing here is process-global.

        Pass ``configure_process_logging=True`` to let xqueue install its structlog
        configuration; by default the embedding application keeps its own.
        """
        from xqueue.runtime.composition import Runtime

        return cls(
            Runtime.open(
                config_path=config_path,
                env_name=env_name,
                overrides=overrides,
                workspace_root=workspace_root,
                use_workspace_instance=use_workspace_instance,
                workspace=workspace,
                configure_process_logging=configure_process_logging,
            )
        )

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def workspace(self) -> Workspace:
        from xqueue.workspace.api import Workspace

        return self._facet("workspace", Workspace)

    @property
    def maintenance(self) -> Maintenance:
        from xqueue.maintenance.api import Maintenance

        return self._facet("maintenance", Maintenance)

    @property
    def jobs(self) -> Jobs:
        from xqueue.jobs.api import Jobs

        return self._facet("jobs", Jobs)

    @property
    def queues(self) -> Queues:
        from xqueue.queues.api import Queues

        return self._facet("queues", Queues)

    @property
    def workers(self) -> Workers:
        from xqueue.workers.api import Workers

        return self._facet("workers", Workers)

    @property
    def controller(self) -> Controller:
        from xqueue.controller.api import Controller

        return self._facet("controller", Controller)

    def _facet(self, name: str, facet_type: Callable[[Runtime], FacetT]) -> FacetT:
        self._ensure_open()
        cached = self._facets.get(name)
        if cached is not None:
            # The cache is keyed by facet name, so the stored value is this type.
            return cast(FacetT, cached)
        facet = facet_type(self._runtime)
        self._facets[name] = facet
        return facet

    def _ensure_open(self) -> None:
        if self._closed:
            raise XqueueClosedError("xqueue client is closed")

    def close(self) -> None:
        """Dispose owned resources; repeated closes are safe."""
        if self._closed:
            return
        self._runtime.close()
        self._closed = True

    def __enter__(self) -> Xqueue:
        self._ensure_open()
        return self

    def __exit__(self, _exc_type: object, _exc: object, _traceback: object) -> None:
        self.close()
