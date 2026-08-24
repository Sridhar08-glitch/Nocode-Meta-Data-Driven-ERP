"""Tests for Command base class."""
import uuid
from datetime import UTC

import pytest

from apps.eventstore.commands import SYSTEM_ACTOR, Command


class SampleCommand(Command):
    pass


def make_ws():
    return uuid.uuid4()


def test_command_is_frozen():
    """Command must be a frozen dataclass — immutable after creation."""
    ws = make_ws()
    cmd = SampleCommand(workspace_id=ws, issued_by=SYSTEM_ACTOR)
    with pytest.raises((AttributeError, TypeError)):
        cmd.workspace_id = uuid.uuid4()  # type: ignore[misc]


def test_command_defaults():
    ws = make_ws()
    cmd = SampleCommand(workspace_id=ws, issued_by=SYSTEM_ACTOR)
    assert cmd.correlation_id is not None
    assert cmd.issued_at is not None
    assert cmd.issued_at.tzinfo == UTC
    assert cmd.expected_version is None
    assert cmd.aggregate_id is None


def test_command_to_dict():
    ws = make_ws()
    actor = uuid.uuid4()
    cmd = SampleCommand(workspace_id=ws, issued_by=actor)
    d = cmd.to_dict()
    assert d["command_type"] == "SampleCommand"
    assert d["workspace_id"] == str(ws)
    assert d["issued_by"] == str(actor)


def test_system_actor_is_zero_uuid():
    assert str(SYSTEM_ACTOR) == "00000000-0000-0000-0000-000000000000"
