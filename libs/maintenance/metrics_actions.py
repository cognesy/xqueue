"""Runtime metrics actions owned by maintenance."""

from __future__ import annotations

from xqueue.adapters.filesystem.metrics import MetricsService
from xqueue.maintenance.models import RuntimeMetricsResetView, RuntimeMetricsView


class ShowMetricsAction:
    def __init__(self, metrics: MetricsService) -> None:
        self._metrics = metrics

    def __call__(self) -> RuntimeMetricsView:
        return RuntimeMetricsView.model_validate(self._metrics.show())


class ResetMetricsAction:
    def __init__(self, metrics: MetricsService) -> None:
        self._metrics = metrics

    def __call__(self) -> RuntimeMetricsResetView:
        return RuntimeMetricsResetView.model_validate(self._metrics.reset())
