"""Tests pour config.py — lecture, écriture et rechargement de la configuration."""

import json
from pathlib import Path

import pytest

import config as cfg_module


@pytest.fixture(autouse=True)
def isolated_config(tmp_path, monkeypatch):
    """Redirige _CONFIG_PATH vers un fichier temporaire et réinitialise le cache."""
    config_path = tmp_path / "config" / "settings.json"
    monkeypatch.setattr(cfg_module, "_CONFIG_PATH", config_path)
    monkeypatch.setattr(cfg_module, "_cache", None)
    yield config_path
    cfg_module._cache = None


def _write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


# ── get() ─────────────────────────────────────────────────────────────────────

def test_get_simple_key(isolated_config):
    _write(isolated_config, {"theme": "dark"})
    assert cfg_module.get("theme") == "dark"


def test_get_nested_key(isolated_config):
    _write(isolated_config, {"backup": {"mode": "scheduled"}})
    assert cfg_module.get("backup.mode") == "scheduled"


def test_get_missing_key_returns_default(isolated_config):
    _write(isolated_config, {})
    assert cfg_module.get("nonexistent.key", "fallback") == "fallback"


def test_get_none_default(isolated_config):
    _write(isolated_config, {})
    assert cfg_module.get("missing") is None


def test_get_distinguishes_none_from_missing(isolated_config):
    _write(isolated_config, {"key": None})
    assert cfg_module.get("key", "fallback") is None


# ── set_value() ───────────────────────────────────────────────────────────────

def test_set_value_persists_to_file(isolated_config):
    _write(isolated_config, {"theme": "dark"})
    cfg_module.set_value("theme", "light")
    data = json.loads(isolated_config.read_text(encoding="utf-8"))
    assert data["theme"] == "light"


def test_set_nested_value(isolated_config):
    _write(isolated_config, {"backup": {"mode": "shutdown"}})
    cfg_module.set_value("backup.mode", "scheduled")
    assert cfg_module.get("backup.mode") == "scheduled"


def test_set_creates_missing_nested_keys(isolated_config):
    _write(isolated_config, {})
    cfg_module.set_value("filters.excluded_extensions", [".tmp"])
    assert cfg_module.get("filters.excluded_extensions") == [".tmp"]


def test_set_list_value(isolated_config):
    _write(isolated_config, {})
    cfg_module.set_value("backup.source_disks", ["C:\\", "D:\\"])
    assert cfg_module.get("backup.source_disks") == ["C:\\", "D:\\"]


# ── reload() ─────────────────────────────────────────────────────────────────

def test_reload_reads_from_disk(isolated_config):
    _write(isolated_config, {"theme": "dark"})
    assert cfg_module.get("theme") == "dark"           # met en cache
    isolated_config.write_text(json.dumps({"theme": "light"}), encoding="utf-8")
    result = cfg_module.reload()
    assert result["theme"] == "light"


# ── Initialisation ────────────────────────────────────────────────────────────

def test_missing_file_creates_defaults(isolated_config):
    assert not isolated_config.exists()
    cfg = cfg_module.load()
    assert "version" in cfg
    assert "backup" in cfg
    assert "filters" in cfg


def test_corrupt_json_falls_back_to_defaults(isolated_config):
    isolated_config.parent.mkdir(parents=True, exist_ok=True)
    isolated_config.write_text("{ invalid json }", encoding="utf-8")
    cfg_module._cache = None
    cfg = cfg_module.load()
    assert "backup" in cfg


# ── load() renvoie une copie profonde ─────────────────────────────────────────

def test_load_returns_deep_copy(isolated_config):
    _write(isolated_config, {"backup": {"source_disks": []}})
    cfg1 = cfg_module.load()
    cfg1["backup"]["source_disks"].append("C:\\")
    cfg2 = cfg_module.load()
    assert cfg2["backup"]["source_disks"] == []
