"""Smoke tests for the CloudRISK adapter (no live calls)."""
import importlib
import os

import pytest


def reload_adapter(monkeypatch, url: str | None):
    if url is None:
        monkeypatch.delenv("CLOUDRISK_API_URL", raising=False)
    else:
        monkeypatch.setenv("CLOUDRISK_API_URL", url)
    import cloudrisk_api.services.adaptador_cloudrisk as cr
    importlib.reload(cr)
    return cr


def test_disabled_when_env_missing(monkeypatch):
    cr = reload_adapter(monkeypatch, None)
    assert cr.base_url() is None
    assert cr.is_enabled() is False


def test_enabled_when_env_set(monkeypatch):
    cr = reload_adapter(monkeypatch, "https://team-backend.example.com/")
    # Trailing slash is stripped.
    assert cr.base_url() == "https://team-backend.example.com"
    assert cr.is_enabled() is True


def test_get_locations_raises_when_disabled(monkeypatch):
    cr = reload_adapter(monkeypatch, None)
    with pytest.raises(cr.NotConfigured):
        cr.get_locations()
