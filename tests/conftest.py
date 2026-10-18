# -*- coding: utf-8 -*-
"""Keep the real Control_Center/.env out of the test process: config.py
skips loading it when CONTROL_CENTER_NO_DOTENV=1. Set here, before any
test module imports config (directly or through atlas_services,
ui_common or scheduler)."""

import os

import pytest

os.environ["CONTROL_CENTER_NO_DOTENV"] = "1"


@pytest.fixture(autouse=True)
def _isolated_settings(tmp_path, monkeypatch):
    """The real data/settings.json never leaks into a test: senders read
    their daily limits from it, so point it at an empty temp location."""
    from ui import settings_store
    monkeypatch.setattr(settings_store, "_SETTINGS_PATH",
                        tmp_path / "_settings" / "settings.json")
