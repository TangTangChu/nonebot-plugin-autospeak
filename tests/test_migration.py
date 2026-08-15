"""旧数据迁移与插件配置测试。"""

import json
from pathlib import Path

import pytest


@pytest.fixture()
def plugin(tmp_path, monkeypatch):
    """插件模块实例，存储路径隔离到临时目录。"""
    import nonebot_plugin_autospeak as mod

    monkeypatch.setattr(mod, "CONFIG_PATH", tmp_path / "config/config.json")
    monkeypatch.setattr(mod, "IMAGES_DIR", tmp_path / "data/images")
    return mod


def _write_legacy(root: Path) -> Path:
    """在 root 下构造旧版 data/autospeak/ 目录。"""
    legacy = root / "data/autospeak"
    legacy.mkdir(parents=True, exist_ok=True)
    (legacy / "config.json").write_text(
        json.dumps(
            {"enabled": True, "next_id": 5, "tasks": [{"id": 1, "type": "group"}]},
            ensure_ascii=False,
        ),
        "utf-8",
    )
    (legacy / "images").mkdir(exist_ok=True)
    (legacy / "images/a.png").write_bytes(b"fake-png")
    return legacy


# ===== 旧数据迁移 =====


def test_migrate_legacy_data(plugin, tmp_path, monkeypatch):
    legacy = _write_legacy(tmp_path)
    monkeypatch.setattr(plugin, "LEGACY_DATA_DIR", legacy)

    plugin.migrate_legacy_data()

    assert plugin.CONFIG_PATH.is_file()
    cfg = json.loads(plugin.CONFIG_PATH.read_text("utf-8"))
    assert cfg["enabled"] is True
    assert cfg["next_id"] == 5
    assert cfg["tasks"] == [{"id": 1, "type": "group"}]
    # 图片同步迁移
    assert (plugin.IMAGES_DIR / "a.png").is_file()
    assert (plugin.IMAGES_DIR / "a.png").read_bytes() == b"fake-png"


def test_migrate_skips_when_new_path_has_data(plugin, tmp_path, monkeypatch):
    legacy = _write_legacy(tmp_path)
    monkeypatch.setattr(plugin, "LEGACY_DATA_DIR", legacy)
    # 新路径已有配置，不应被旧数据覆盖
    plugin.CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    plugin.CONFIG_PATH.write_text(
        json.dumps({"enabled": False, "next_id": 1, "tasks": []}, ensure_ascii=False),
        "utf-8",
    )

    plugin.migrate_legacy_data()

    cfg = json.loads(plugin.CONFIG_PATH.read_text("utf-8"))
    assert cfg["enabled"] is False
    assert cfg["next_id"] == 1


def test_migrate_noop_without_legacy(plugin, tmp_path, monkeypatch):
    # 没有旧数据时静默跳过，不创建任何文件
    monkeypatch.setattr(plugin, "LEGACY_DATA_DIR", tmp_path / "no-such-dir")
    plugin.migrate_legacy_data()
    assert not plugin.CONFIG_PATH.exists()
    assert not plugin.IMAGES_DIR.exists()


# ===== 插件配置 =====


def test_default_command_priority(plugin):
    assert plugin.plugin_config.autospeak_command_priority == 10
    # 事件响应器使用可配置的优先级
    assert plugin.autospeak_cmd.priority == 10
