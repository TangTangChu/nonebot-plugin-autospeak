"""插件核心逻辑测试：星期解析、任务 ID、消息合成与发送。"""

import pytest


@pytest.fixture(scope="module")
def mod(tmp_path_factory):
    """插件模块，存储路径隔离到临时目录。"""
    import nonebot_plugin_autospeak as mod

    tmp = tmp_path_factory.mktemp("autospeak_core")
    orig_cfg, orig_img = mod.CONFIG_PATH, mod.IMAGES_DIR
    mod.CONFIG_PATH = tmp / "config.json"
    mod.IMAGES_DIR = tmp / "images"
    mod.load_config()
    yield mod
    mod.CONFIG_PATH, mod.IMAGES_DIR = orig_cfg, orig_img


# ===== parse_weekdays =====


def test_parse_weekdays_all(mod):
    assert mod.parse_weekdays("") == list(range(7))
    assert mod.parse_weekdays("*") == list(range(7))
    assert mod.parse_weekdays("all") == list(range(7))
    assert mod.parse_weekdays("everyday") == list(range(7))


def test_parse_weekdays_workday(mod):
    assert mod.parse_weekdays("workday") == [0, 1, 2, 3, 4]
    assert mod.parse_weekdays("wd") == [0, 1, 2, 3, 4]


def test_parse_weekdays_numbers(mod):
    assert mod.parse_weekdays("1,3,5") == [0, 2, 4]
    assert mod.parse_weekdays("7") == [6]


def test_parse_weekdays_names(mod):
    assert mod.parse_weekdays("mon,tue,sun") == [0, 1, 6]


def test_parse_weekdays_chinese_separator(mod):
    assert mod.parse_weekdays("1，3、5") == [0, 2, 4]


def test_parse_weekdays_mixed(mod):
    assert mod.parse_weekdays("mon, 3, sat") == [0, 2, 5]


def test_parse_weekdays_invalid(mod):
    with pytest.raises(ValueError):
        mod.parse_weekdays("abc")
    with pytest.raises(ValueError):
        mod.parse_weekdays("8")  # 超出 1~7


# ===== format_weekdays =====


def test_format_weekdays(mod):
    assert mod.format_weekdays(None) == "（未设置，按每天处理）"
    assert mod.format_weekdays([]) == "（未设置，按每天处理）"
    assert mod.format_weekdays([0, 1, 2, 3, 4, 5, 6]) == "每天"
    assert mod.format_weekdays([0, 1, 2, 3, 4]) == "工作日（周一~周五）"
    assert mod.format_weekdays([0, 2, 4]) == "周一、周三、周五"


# ===== ensure_next_id =====


def test_ensure_next_id_scan(mod):
    mod.CONFIG["tasks"] = [{"id": 3}, {"id": 10}, {"id": 1}]
    mod.CONFIG["next_id"] = 1
    mod.ensure_next_id()
    assert mod.CONFIG["next_id"] == 11


def test_ensure_next_id_keep_larger(mod):
    mod.CONFIG["tasks"] = [{"id": 3}]
    mod.CONFIG["next_id"] = 100
    mod.ensure_next_id()
    assert mod.CONFIG["next_id"] == 100


def test_ensure_next_id_empty(mod):
    mod.CONFIG["tasks"] = []
    mod.CONFIG["next_id"] = 1
    mod.ensure_next_id()
    assert mod.CONFIG["next_id"] == 1


# ===== compose_message =====


def test_compose_message_single(mod):
    task = {"messages": ["只有这一条"]}
    assert mod.compose_message(task) == "只有这一条"


def test_compose_message_renders_placeholders(mod, monkeypatch):
    seen = []

    def fake_render(text, images_dir=None):
        seen.append(text)
        return "RENDERED"

    monkeypatch.setattr(mod, "render_placeholders", fake_render)
    task = {"messages": ["早安 {weekday}", "午安 {time}"]}
    assert mod.compose_message(task) == "RENDERED"
    assert len(seen) == 1
    assert seen[0] in task["messages"]


def test_compose_message_empty(mod):
    assert mod.compose_message({"messages": []}) is None
    assert mod.compose_message({}) is None


# ===== send_task_message =====


class _FakeBot:
    def __init__(self, calls):
        self.calls = calls

    async def call_api(self, api, **kwargs):
        self.calls[api] = kwargs


@pytest.mark.asyncio
async def test_send_task_message_group(mod, monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "get_bot", lambda: _FakeBot(calls))
    mod.CONFIG["enabled"] = True
    mod.CONFIG["tasks"] = [
        {"id": 1, "type": "group", "target_id": 123, "messages": ["早安 {weekday}"]}
    ]
    await mod.send_task_message(1)
    assert "send_group_msg" in calls
    assert calls["send_group_msg"]["group_id"] == 123
    msg = calls["send_group_msg"]["message"]
    assert msg.startswith("早安 ") and "{" not in msg


@pytest.mark.asyncio
async def test_send_task_message_private(mod, monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "get_bot", lambda: _FakeBot(calls))
    mod.CONFIG["enabled"] = True
    mod.CONFIG["tasks"] = [
        {"id": 2, "type": "private", "target_id": 456, "messages": ["hi"]}
    ]
    await mod.send_task_message(2)
    assert "send_private_msg" in calls
    assert calls["send_private_msg"]["user_id"] == 456


@pytest.mark.asyncio
async def test_send_task_message_disabled(mod, monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "get_bot", lambda: _FakeBot(calls))
    mod.CONFIG["enabled"] = False
    mod.CONFIG["tasks"] = [{"id": 3, "type": "group", "target_id": 1, "messages": ["x"]}]
    await mod.send_task_message(3)
    assert calls == {}


@pytest.mark.asyncio
async def test_send_task_message_missing_task(mod, monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "get_bot", lambda: _FakeBot(calls))
    mod.CONFIG["enabled"] = True
    mod.CONFIG["tasks"] = []
    # 任务不存在时不发送且不报错，内部会尝试清理不存在的 job
    await mod.send_task_message(999)
    assert calls == {}


@pytest.mark.asyncio
async def test_send_task_message_no_messages(mod, monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "get_bot", lambda: _FakeBot(calls))
    mod.CONFIG["enabled"] = True
    mod.CONFIG["tasks"] = [
        {"id": 4, "type": "group", "target_id": 1, "messages": []}
    ]
    await mod.send_task_message(4)
    assert calls == {}


@pytest.mark.asyncio
async def test_send_task_message_image(mod, monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "get_bot", lambda: _FakeBot(calls))
    mod.CONFIG["enabled"] = True
    mod.CONFIG["tasks"] = [
        {
            "id": 5,
            "type": "group",
            "target_id": 123,
            "messages": ["早安 {image:https://example.com/a.png}"],
        }
    ]
    await mod.send_task_message(5)
    assert (
        calls["send_group_msg"]["message"]
        == "早安 [CQ:image,file=https://example.com/a.png]"
    )


@pytest.mark.asyncio
async def test_send_task_message_once_removed(mod, monkeypatch):
    calls = {}
    monkeypatch.setattr(mod, "get_bot", lambda: _FakeBot(calls))
    mod.CONFIG["enabled"] = True
    mod.CONFIG["tasks"] = [
        {"id": 9, "kind": "once", "type": "private", "target_id": 1, "messages": ["x"]}
    ]
    await mod.send_task_message(9)
    assert "send_private_msg" in calls
    # 一次性任务执行后自动从配置中移除
    assert mod.CONFIG["tasks"] == []
