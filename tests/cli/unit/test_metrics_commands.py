from __future__ import annotations

import json

from typer.testing import CliRunner

from apps.cli.main import app
from libs.services.metrics import MetricsService


def test_metrics_show_and_reset_use_xqueue_home(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("XQUEUE_HOME", str(tmp_path))
    MetricsService().increment("jobs.enqueued")

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
