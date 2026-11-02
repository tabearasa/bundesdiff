"""Spec 003: the data is updated once a day."""

from __future__ import annotations

import importlib
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).parents[1]


@pytest.mark.spec("UPD-1")
def test_workflow_runs_once_a_day_in_the_evening():
    workflow = (ROOT / ".github" / "workflows" / "update.yml").read_text()
    crons = re.findall(r'^\s*- cron: "([^"]+)"', workflow, re.M)
    assert crons == ["23 19 * * *"]
    assert "workflow_dispatch:" in workflow


@pytest.mark.spec("UPD-2")
def test_local_server_checks_once_a_day(monkeypatch):
    monkeypatch.delenv("BUNDESDIFF_WATCH_MINUTES", raising=False)
    import bundesdiff.app as app
    assert importlib.reload(app).WATCH_MINUTES == 24 * 60
