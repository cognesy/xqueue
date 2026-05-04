"""Runtime metrics actions."""

from __future__ import annotations

from xqueue_libs.domain.models import RuntimeMetricsResetView, RuntimeMetricsView
from xqueue_libs.domain.responses import DetailResponse, MutationResponse
from xqueue_libs.services.metrics import MetricsService


class ShowMetricsAction:
    def __init__(self, metrics: MetricsService | None = None) -> None:
        self._metrics = metrics or MetricsService()

    def __call__(self) -> DetailResponse[RuntimeMetricsView]:
        return DetailResponse(item=RuntimeMetricsView.model_validate(self._metrics.show()))


class ResetMetricsAction:
    def __init__(self, metrics: MetricsService | None = None) -> None:
        self._metrics = metrics or MetricsService()

    def __call__(self) -> MutationResponse[RuntimeMetricsResetView]:
        return MutationResponse(item=RuntimeMetricsResetView.model_validate(self._metrics.reset()))
