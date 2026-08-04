from __future__ import annotations

import json
import threading

from typer.testing import CliRunner
from xqueue.adapters.filesystem.metrics import MetricsService
from xqueue_cli.main import app


def test_metrics_show_and_reset_use_xqueue_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XQUEUE_HOME", str(tmp_path))
    MetricsService(tmp_path / "metrics" / "metrics.json").increment("jobs.enqueued")

    path = tmp_path / "metrics" / "metrics.json"
    assert path.exists()

    runner = CliRunner()
    show = runner.invoke(app, ["metrics", "show", "--output", "json"])
    assert show.exit_code == 0
    assert json.loads(show.stdout)["item"]["counters"]["jobs.enqueued"] == 1

    reset = runner.invoke(app, ["metrics", "reset", "--output", "json"])
    assert reset.exit_code == 0
    payload = json.loads(reset.stdout)
    assert payload["item"]["counters"] == {}
    assert payload["item"]["previous_counters"]["jobs.enqueued"] == 1


def test_concurrent_increments_do_not_lose_updates(tmp_path) -> None:
    """Worker slots are threads in one process; increments must not race."""
    metrics = MetricsService(tmp_path / "metrics.json")
    threads = [
        threading.Thread(target=lambda: [metrics.increment("jobs.executed") for _ in range(20)]) for _ in range(8)
    ]
    for thread in threads:
        thread.start()
    for thread in threads:
        thread.join()

    assert metrics.show()["counters"]["jobs.executed"] == 160
    assert not list(tmp_path.glob("*.tmp"))
