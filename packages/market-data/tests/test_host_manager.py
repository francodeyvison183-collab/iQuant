"""TdxHostManager 持久化与编辑测试（不实际联网）。"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from iquant_market_data.tdx.host_manager import DEFAULT_HOSTS, TdxHostManager


def test_load_uses_defaults_when_missing(tmp_path: Path):
    cfg = tmp_path / "tdx_hosts.json"
    hm = TdxHostManager(config_path=cfg)
    hosts = hm.load()
    assert len(hosts) == len(DEFAULT_HOSTS)


def test_add_and_save_persists(tmp_path: Path):
    cfg = tmp_path / "tdx_hosts.json"
    hm = TdxHostManager(config_path=cfg)
    hm.load()
    hm.add(ip="1.2.3.4", port=7709, name="ut")
    assert cfg.exists()
    data = json.loads(cfg.read_text(encoding="utf-8"))
    assert any(h["ip"] == "1.2.3.4" and h["port"] == 7709 for h in data)


def test_remove(tmp_path: Path):
    cfg = tmp_path / "tdx_hosts.json"
    hm = TdxHostManager(config_path=cfg)
    hm.load()
    hm.add(ip="1.2.3.4", port=7709, name="ut")
    assert hm.remove("1.2.3.4", 7709) is True
    assert hm.remove("9.9.9.9", 7709) is False


def test_add_duplicate(tmp_path: Path):
    cfg = tmp_path / "tdx_hosts.json"
    hm = TdxHostManager(config_path=cfg)
    hm.load()
    hm.add(ip="1.2.3.4", port=7709, name="ut")
    with pytest.raises(ValueError):
        hm.add(ip="1.2.3.4", port=7709, name="ut2")
