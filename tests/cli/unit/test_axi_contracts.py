from __future__ import annotations

import pytest
from xqueue_cli.axi_contracts import COMMAND_CONTRACTS, get_command_contract, validate_requested_fields


def test_contract_registry_covers_current_command_surface() -> None:
    expected = {
        "home",
        "enqueue",
        "health",
        "doctor",
        "config.show",
        "controller.run",
        "controller.status",
        "controller.install",
        "controller.uninstall",
        "controller.start",
        "controller.pause-intake",
        "controller.resume-intake",
        "controller.drain",
        "controller.restart",
        "controller.stop",
        "db.check",
        "db.vacuum",
        "db.reset-workspace-instance",
        "db.cleanup-retention",
        "jobs.list",
        "jobs.show",
        "jobs.cancel",
        "jobs.retry",
        "jobs.delete",
        "jobs.tail",
        "jobs.purge",
        "queues.list",
        "queues.stats",
        "queues.pause",
        "queues.resume",
        "recover.stale-leases",
        "worker",
        "worker.run",
        "workers.list",
        "workers.pause",
        "workers.resume",
        "workers.drain",
        "workers.stop",
        "hooks.install",
        "hooks.status",
        "hooks.session-end",
        "error",
    }

    assert expected <= COMMAND_CONTRACTS.keys()


def test_jobs_list_contract_is_derived_from_response_and_row_models() -> None:
    contract = get_command_contract("jobs.list")

    assert contract.allowed_fields == ("items", "meta")
    assert contract.list_key == "items"
    assert contract.default_row_fields == ("id", "queue", "state", "available_at")
    assert "command" in contract.list_row_fields


def test_jobs_show_contract_validates_nested_item_fields() -> None:
    contract = get_command_contract("jobs.show")

    assert validate_requested_fields(contract, ("item", "id", "item.command")) == ("item", "id", "item.command")

    with pytest.raises(ValueError):
        validate_requested_fields(contract, ("item.missing",))
