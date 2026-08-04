from __future__ import annotations

import io
import json
import subprocess
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest
import structlog
from typer.testing import CliRunner
from xqueue import Xqueue
from xqueue.adapters.sqlite.database import create_sqlite_engine
from xqueue.adapters.sqlite.models import Base
from xqueue.core.errors import ValidationError, XqueueClosedError
from xqueue.jobs.models import EnqueueJobInput, JobDetail, JobListFilters
from xqueue.workers.models import RegisterWorkerInput, WorkerState
from xqueue_cli.main import app

runner = CliRunner()


def test_client_facets_are_cached_and_close_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = Xqueue.open(workspace_root=tmp_path, use_workspace_instance=True)
    dispose = Mock(wraps=client._runtime.engine.dispose)
    monkeypatch.setattr(client._runtime.engine, "dispose", dispose)

    assert client.workspace is client.workspace
    assert client.maintenance is client.maintenance
    assert client.jobs is client.jobs
    assert client.queues is client.queues
    assert client.workers is client.workers
    assert client.controller is client.controller
    assert client.workspace.config().paths.state_root == tmp_path / ".xqueue"

    client.close()
    client.close()

    assert client.is_closed
    dispose.assert_called_once_with()
    with pytest.raises(XqueueClosedError):
        client.workspace.config()


def test_context_manager_closes_client(tmp_path: Path) -> None:
    with Xqueue.open(workspace_root=tmp_path, use_workspace_instance=True) as client:
        assert not client.is_closed

    assert client.is_closed


def test_sdk_and_cli_config_reads_match(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        cli_result = runner.invoke(app, ["config", "show", "--output", "json", "--workspace-instance"])
        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            sdk_payload = client.workspace.config().model_dump(mode="json")

    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout) == sdk_payload


def test_sdk_and_cli_health_reads_match(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            sdk_payload = client.maintenance.health().model_dump(mode="json")
        cli_result = runner.invoke(app, ["health", "--output", "json", "--workspace-instance"])

    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout)["item"] == sdk_payload


def test_maintenance_and_workspace_sdk_return_typed_values(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            database = client.maintenance.check_database()
            doctor = client.maintenance.doctor()
            metrics = client.maintenance.metrics()
            reset_metrics = client.maintenance.reset_metrics()
            hook_status = client.workspace.hook_status()

        cli_result = runner.invoke(app, ["doctor", "--output", "json", "--workspace-instance"])

    assert database.status.value == "ok"
    assert doctor.status.value == "ok"
    assert metrics.path == reset_metrics.path
    assert hook_status.codex.hooks_exists is False
    assert not hasattr(doctor, "item")
    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout)["item"] == doctor.model_dump(mode="json")


def test_jobs_sdk_returns_typed_values_and_matches_cli_envelopes(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            job = client.jobs.enqueue(EnqueueJobInput(queue="agent", command="echo sdk"))
            listed = client.jobs.list(JobListFilters(queue="agent"))
            shown = client.jobs.show(job.id)

        cli_result = runner.invoke(
            app,
            ["jobs", "show", job.id, "--output", "json", "--workspace-instance"],
        )

    assert job.id == shown.id
    assert [item.id for item in listed] == [job.id]
    assert not hasattr(job, "item")
    assert not hasattr(listed, "items")
    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout)["item"] == shown.model_dump(mode="json")


def test_queues_sdk_returns_typed_values_and_matches_cli_envelopes(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            paused = client.queues.pause("agent")
            listed = client.queues.list()
            stats = client.queues.stats()

        cli_result = runner.invoke(app, ["queues", "stats", "--output", "json", "--workspace-instance"])

    assert paused.state.value == "paused"
    assert [item.name for item in listed] == ["agent"]
    assert [item.name for item in stats] == ["agent"]
    assert not hasattr(paused, "item")
    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout)["items"] == [item.model_dump(mode="json") for item in stats]


def test_workers_sdk_returns_typed_values_and_matches_cli_envelopes(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            registered = client.workers.register(RegisterWorkerInput(worker_id="worker-sdk", queues=["agent"]))
            paused = client.workers.set_state("worker-sdk", WorkerState.PAUSED)
            listed = client.workers.list()

        cli_result = runner.invoke(app, ["workers", "list", "--output", "json", "--workspace-instance"])

    assert registered.id == "worker-sdk"
    assert paused.state is WorkerState.PAUSED
    assert [item.id for item in listed] == ["worker-sdk"]
    assert not hasattr(paused, "item")
    assert cli_result.exit_code == 0
    assert json.loads(cli_result.stdout)["items"] == [item.model_dump(mode="json") for item in listed]


def test_controller_sdk_returns_typed_values_and_matches_cli_envelopes(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        Path(".xqueue").mkdir(exist_ok=True)
        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            ensured = client.controller.ensure_pool(name="agent", queues=["agent"], concurrency=1)
            pools = client.controller.list_pools()
            status = client.controller.status(controller_id="sdk")

        cli_result = runner.invoke(
            app,
            ["controller", "status", "--controller-id", "sdk", "--output", "json", "--workspace-instance"],
        )

    assert status.controller_id == "sdk"
    assert ensured.action == "created"
    assert [pool.name for pool in pools] == ["agent"]
    assert not hasattr(status, "item")
    assert cli_result.exit_code == 0
    cli_status = json.loads(cli_result.stdout)["item"]
    assert cli_status["controller_id"] == status.controller_id
    assert cli_status["state"] == status.state.value
    assert cli_status["pools"] == status.model_dump(mode="json")["pools"]


def test_enqueue_counters_use_the_runtime_metrics_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Every action must share the runtime's configured metrics file, not a global default."""
    home = tmp_path / "xqueue-home"
    monkeypatch.setenv("XQUEUE_HOME", str(home))

    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            client.jobs.enqueue(EnqueueJobInput(queue="agent", command="echo metrics"))
            metrics = client.maintenance.metrics()

        assert metrics.path == str((instance / "metrics" / "metrics.json").resolve())
        assert metrics.counters["jobs.enqueued"] == 1

    assert not (home / "metrics" / "metrics.json").exists()


def test_sdk_does_not_replace_host_logging_unless_asked(tmp_path: Path) -> None:
    """A library call must not mutate the embedding application's structlog setup."""
    saved = structlog.get_config()
    try:
        structlog.configure(
            processors=[structlog.processors.KeyValueRenderer()],
            logger_factory=structlog.PrintLoggerFactory(file=io.StringIO()),
        )
        host_factory = structlog.get_config()["logger_factory"]

        with runner.isolated_filesystem(temp_dir=tmp_path):
            Path(".xqueue").mkdir(exist_ok=True)
            with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
                client.workspace.config()
            assert structlog.get_config()["logger_factory"] is host_factory

            with Xqueue.open(
                workspace_root=Path.cwd(),
                use_workspace_instance=True,
                configure_process_logging=True,
            ) as client:
                client.workspace.config()
            assert structlog.get_config()["logger_factory"] is not host_factory
    finally:
        structlog.configure(**saved)


def test_public_import_is_lazy() -> None:
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import sys; from xqueue import Xqueue; "
                "assert Xqueue.__name__ == 'Xqueue'; "
                "assert not ({'typer', 'rich', 'sqlalchemy', "
                "'xqueue.controller.launchd', 'xqueue.controller.systemd'} & set(sys.modules))"
            ),
        ],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def _readme_sdk_snippet() -> str:
    """Return the Python SDK example exactly as README.md publishes it."""
    readme = (Path(__file__).resolve().parents[2] / "README.md").read_text(encoding="utf-8")
    body = readme.split("## Python SDK", 1)[1]
    return body.split("```python", 1)[1].split("```", 1)[0]


def test_readme_sdk_example_runs_as_written(tmp_path: Path) -> None:
    """The first thing an embedding consumer copies has to work verbatim."""
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        namespace: dict[str, object] = {}
        exec(compile(_readme_sdk_snippet(), "README.md", "exec"), namespace)  # noqa: S102

        job = namespace["job"]
        current = namespace["current"]

    assert isinstance(job, JobDetail)
    assert job.queue == "default"
    assert current.id == job.id


def test_enqueue_accepts_field_keywords_and_the_input_model(tmp_path: Path) -> None:
    with runner.isolated_filesystem(temp_dir=tmp_path):
        instance = Path(".xqueue")
        instance.mkdir(exist_ok=True)
        engine = create_sqlite_engine(instance / "xqueue.db")
        Base.metadata.create_all(engine)
        engine.dispose()

        with Xqueue.open(workspace_root=Path.cwd(), use_workspace_instance=True) as client:
            from_keywords = client.jobs.enqueue(queue="agent", command="echo keywords", priority=5)
            from_model = client.jobs.enqueue(EnqueueJobInput(queue="agent", command="echo model", priority=5))

            with pytest.raises(ValidationError, match="not both"):
                client.jobs.enqueue(EnqueueJobInput(queue="agent", command="echo both"), queue="agent")

    assert from_keywords.queue == from_model.queue == "agent"
    assert from_keywords.priority == from_model.priority == 5
    assert from_keywords.command == "echo keywords"
