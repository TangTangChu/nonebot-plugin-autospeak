"""指令流程测试：用 nonebug 模拟群消息，验证 autospk 各子命令。"""

import json
import time
from datetime import datetime, timedelta

import pytest
from nonebug import App
from nonebot.adapters.onebot.v11 import Bot as OneBotV11Bot
from nonebot.adapters.onebot.v11 import GroupMessageEvent, Message, MessageSegment
from nonebot.adapters.onebot.v11.event import Sender

SUPERUSER_ID = 10001


@pytest.fixture()
def plugin(tmp_path, monkeypatch):
    """每用例隔离存储路径并重置状态。"""
    import nonebot_plugin_autospeak as mod

    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(mod, "CONFIG_PATH", tmp_path / "data/autospeak/config.json")
    monkeypatch.setattr(mod, "IMAGES_DIR", tmp_path / "data/autospeak/images")
    mod.load_config()
    mod.schedule_all_tasks()
    return mod


def make_group_event(
    text: str | Message, user_id: int = SUPERUSER_ID, group_id: int = 12345
) -> GroupMessageEvent:
    raw = text if isinstance(text, str) else str(text)
    msg = text if isinstance(text, Message) else Message(text)
    return GroupMessageEvent(
        time=int(time.time()),
        self_id=123456,
        post_type="message",
        message_type="group",
        sub_type="normal",
        group_id=group_id,
        user_id=user_id,
        message_id=1,
        message=msg,
        raw_message=raw,
        font=0,
        sender=Sender(user_id=user_id, nickname="tester"),
    )


async def run_cmd(app: App, plugin, text: str | Message, expected: str):
    """发送一条 autospk 指令并断言回复内容。"""
    cmd = plugin.autospeak_cmd
    async with app.test_matcher(cmd) as ctx:
        bot = ctx.create_bot(base=OneBotV11Bot)
        event = make_group_event(text)
        ctx.receive_event(bot, event)
        ctx.should_call_send(event, expected, result=None)
        ctx.should_finished(cmd)


# ===== 基础指令 =====


@pytest.mark.asyncio
async def test_help(app: App, plugin):
    await run_cmd(app, plugin, "autospk", plugin.HELP_TEXT)


@pytest.mark.asyncio
async def test_unknown_subcommand(app: App, plugin):
    await run_cmd(app, plugin, "autospk foo", "未知子命令，请使用 autospk 查看帮助。")


@pytest.mark.asyncio
async def test_non_superuser_ignored(app: App, plugin):
    """非 SUPERUSER 调用指令：权限不通过，不应有任何回复。"""
    cmd = plugin.autospeak_cmd
    async with app.test_matcher(cmd) as ctx:
        bot = ctx.create_bot(base=OneBotV11Bot)
        ctx.receive_event(bot, make_group_event("autospk list", user_id=99999))


# ===== placeholders / preview =====


@pytest.mark.asyncio
async def test_placeholders_docs(app: App, plugin):
    await run_cmd(app, plugin, "autospk placeholders", plugin.PLACEHOLDERS_HELP)


@pytest.mark.asyncio
async def test_placeholders_alias(app: App, plugin):
    await run_cmd(app, plugin, "autospk ph", plugin.PLACEHOLDERS_HELP)


@pytest.mark.asyncio
async def test_preview(app: App, plugin):
    # 目标日期取 30 天后，渲染结果确定为“还有 30 天”
    target = (datetime.now() + timedelta(days=30)).strftime("%Y-%m-%d")
    await run_cmd(
        app,
        plugin,
        f"autospk preview 距离{{days_until_cn:{target}}}",
        "渲染结果：\n距离还有 30 天",
    )


@pytest.mark.asyncio
async def test_preview_no_arg(app: App, plugin):
    await run_cmd(
        app,
        plugin,
        "autospk preview",
        "用法：autospk preview <文本>\n示例：autospk preview 距离{days_until:2026-06-07}天",
    )


# ===== add =====


@pytest.mark.asyncio
async def test_add(app: App, plugin, tmp_path):
    await run_cmd(
        app,
        plugin,
        "autospk add group here 09:00 早安|早安呀 days=workday",
        "✅ 已添加定时任务：\n"
        "  id: 1\n"
        "  type: group\n"
        "  target: 12345\n"
        "  time: 09:00\n"
        "  weekdays: 工作日（周一~周五）\n"
        "  messages: 2 条",
    )
    # 配置已写入临时目录
    cfg_path = tmp_path / "data/autospeak/config.json"
    assert cfg_path.is_file()
    cfg = json.loads(cfg_path.read_text("utf-8"))
    assert cfg["next_id"] == 2
    task = cfg["tasks"][0]
    assert task["id"] == 1
    assert task["weekdays"] == [0, 1, 2, 3, 4]
    assert task["messages"] == ["早安", "早安呀"]


@pytest.mark.asyncio
async def test_add_invalid_time(app: App, plugin):
    await run_cmd(
        app,
        plugin,
        "autospk add group here 25:99 hi",
        "时间格式错误，请使用 24 小时制 HH:MM，例如 09:00 或 21:30。",
    )


@pytest.mark.asyncio
async def test_add_invalid_target(app: App, plugin):
    await run_cmd(
        app,
        plugin,
        "autospk add group xyz 09:00 hi",
        "目标 ID 解析失败，请使用数字，或在群里用 here，在私聊用 me。",
    )


@pytest.mark.asyncio
async def test_add_invalid_weekdays(app: App, plugin):
    await run_cmd(
        app,
        plugin,
        "autospk add group here 09:00 hi days=abc",
        "days= 参数解析失败，请使用：\n"
        "  - 不写：默认每天\n"
        "  - days=workday / days=wd      => 周一~周五\n"
        "  - days=1,3,5                  => 周一、周三、周五\n"
        "  - days=mon,tue,fri            => 周一、周二、周五\n"
        "  - days=* / all / everyday     => 每天",
    )


# ===== 图文混排 =====


def _image_seg(url: str = "https://example.com/a.png") -> MessageSegment:
    return MessageSegment("image", {"file": "x.png", "url": url})


@pytest.fixture()
def fake_download(monkeypatch):
    """拦截图片下载，返回固定内容。"""
    from nonebot_plugin_autospeak import images

    async def _fake(url):
        return b"img-data", "image/png"

    monkeypatch.setattr(images, "download_image", _fake)
    return b"img-data"


@pytest.mark.asyncio
async def test_add_with_image(app: App, plugin, fake_download):
    """add 图文混排：图片自动保存并转为 {image:文件名}。"""
    from hashlib import md5

    msg = Message(
        [
            MessageSegment.text("autospk add group here 09:00 早安"),
            _image_seg(),
        ]
    )
    await run_cmd(
        app,
        plugin,
        msg,
        "✅ 已添加定时任务：\n"
        "  id: 1\n"
        "  type: group\n"
        "  target: 12345\n"
        "  time: 09:00\n"
        "  weekdays: 每天\n"
        "  messages: 1 条",
    )
    name = md5(fake_download).hexdigest() + ".png"
    assert plugin.CONFIG["tasks"][0]["messages"] == [f"早安{{image:{name}}}"]
    assert (plugin.IMAGES_DIR / name).is_file()


@pytest.mark.asyncio
async def test_add_image_middle(app: App, plugin, fake_download):
    """图片在消息中间时，占位符按原位置拼接。"""
    from hashlib import md5

    msg = Message(
        [
            MessageSegment.text("autospk add group here 09:00 早安"),
            _image_seg(),
            MessageSegment.text("！"),
        ]
    )
    await run_cmd(
        app,
        plugin,
        msg,
        "✅ 已添加定时任务：\n"
        "  id: 1\n"
        "  type: group\n"
        "  target: 12345\n"
        "  time: 09:00\n"
        "  weekdays: 每天\n"
        "  messages: 1 条",
    )
    name = md5(fake_download).hexdigest() + ".png"
    assert plugin.CONFIG["tasks"][0]["messages"] == [f"早安{{image:{name}}}！"]


@pytest.mark.asyncio
async def test_add_once_with_image(app: App, plugin, fake_download):
    """addonce 图文混排。"""
    from hashlib import md5

    msg = Message(
        [
            MessageSegment.text("autospk addonce private 67890 2099-01-01 09:00 新年"),
            _image_seg(),
        ]
    )
    await run_cmd(
        app,
        plugin,
        msg,
        "✅ 已添加一次性任务：\n"
        "  id: 1\n"
        "  type: private\n"
        "  target: 67890\n"
        "  fire at: 2099-01-01 09:00\n"
        "  messages: 1 条\n"
        "（仅触发一次，到点后自动删除）",
    )
    name = md5(fake_download).hexdigest() + ".png"
    assert plugin.CONFIG["tasks"][0]["messages"] == [f"新年{{image:{name}}}"]


@pytest.mark.asyncio
async def test_edit_msg_with_image(app: App, plugin, fake_download):
    """edit msg 图文混排。"""
    from hashlib import md5

    plugin.CONFIG["tasks"] = [
        {
            "id": 1,
            "type": "group",
            "target_id": 12345,
            "time": "09:00",
            "weekdays": [],
            "messages": ["a"],
        }
    ]
    msg = Message(
        [
            MessageSegment.text("autospk edit msg 1 新内容"),
            _image_seg(),
        ]
    )
    await run_cmd(
        app,
        plugin,
        msg,
        "✅ 任务消息已修改：\n" "  id: 1\n" "  messages: 1 条",
    )
    name = md5(fake_download).hexdigest() + ".png"
    assert plugin.CONFIG["tasks"][0]["messages"] == [f"新内容{{image:{name}}}"]


# ===== addonce =====


@pytest.mark.asyncio
async def test_addonce_past_time(app: App, plugin):
    await run_cmd(
        app,
        plugin,
        "autospk addonce group here 2020-01-01 09:00 hi",
        "指定时间 2020-01-01 09:00 已经过去，请使用未来时间。",
    )


@pytest.mark.asyncio
async def test_addonce_success(app: App, plugin, tmp_path):
    await run_cmd(
        app,
        plugin,
        "autospk addonce private 67890 2099-01-01 09:00 新年快乐！",
        "✅ 已添加一次性任务：\n"
        "  id: 1\n"
        "  type: private\n"
        "  target: 67890\n"
        "  fire at: 2099-01-01 09:00\n"
        "  messages: 1 条\n"
        "（仅触发一次，到点后自动删除）",
    )
    cfg = json.loads((tmp_path / "data/autospeak/config.json").read_text("utf-8"))
    assert cfg["tasks"][0]["kind"] == "once"


# ===== list / del / edit =====


@pytest.mark.asyncio
async def test_list(app: App, plugin):
    plugin.CONFIG["tasks"] = [
        {
            "id": 1,
            "type": "group",
            "target_id": 12345,
            "time": "09:00",
            "weekdays": [0, 1, 2, 3, 4],
            "messages": ["a", "b"],
        },
        {
            "id": 2,
            "kind": "once",
            "type": "private",
            "target_id": 67890,
            "datetime": "2099-01-01 09:00",
            "messages": ["x"],
        },
    ]
    await run_cmd(
        app,
        plugin,
        "autospk list",
        "当前定时任务如下：\n"
        "- id: 1  [循环]\n"
        "  type: group  target: 12345\n"
        "  time: 09:00  weekdays: 工作日（周一~周五）\n"
        "  messages: 2 条\n"
        "- id: 2  [一次性]\n"
        "  type: private  target: 67890\n"
        "  fire at: 2099-01-01 09:00\n"
        "  messages: 1 条",
    )


@pytest.mark.asyncio
async def test_list_empty(app: App, plugin):
    await run_cmd(app, plugin, "autospk list", "当前没有任何定时任务。")


@pytest.mark.asyncio
async def test_del(app: App, plugin):
    plugin.CONFIG["tasks"] = [
        {
            "id": 1,
            "type": "group",
            "target_id": 12345,
            "time": "09:00",
            "weekdays": [],
            "messages": ["a"],
        }
    ]
    await run_cmd(app, plugin, "autospk del 1", "✅ 任务 1 已删除。")
    assert plugin.CONFIG["tasks"] == []


@pytest.mark.asyncio
async def test_del_not_found(app: App, plugin):
    await run_cmd(app, plugin, "autospk del 42", "未找到任务 id = 42。")


@pytest.mark.asyncio
async def test_del_invalid_id(app: App, plugin):
    await run_cmd(
        app,
        plugin,
        "autospk del abc",
        "task_id 必须为整数，请从 autospk list 中复制。",
    )


@pytest.mark.asyncio
async def test_edit_time(app: App, plugin):
    plugin.CONFIG["tasks"] = [
        {
            "id": 1,
            "type": "group",
            "target_id": 12345,
            "time": "09:00",
            "weekdays": [0, 1, 2, 3, 4],
            "messages": ["a"],
        }
    ]
    await run_cmd(
        app,
        plugin,
        "autospk edit time 1 08:30",
        "✅ 任务时间已修改：\n"
        "  id: 1\n"
        "  new time: 08:30\n"
        "  weekdays: 工作日（周一~周五）",
    )
    assert plugin.CONFIG["tasks"][0]["time"] == "08:30"


@pytest.mark.asyncio
async def test_edit_msg(app: App, plugin):
    plugin.CONFIG["tasks"] = [
        {
            "id": 1,
            "type": "group",
            "target_id": 12345,
            "time": "09:00",
            "weekdays": [],
            "messages": ["a"],
        }
    ]
    await run_cmd(
        app,
        plugin,
        "autospk edit msg 1 新消息1|新消息2",
        "✅ 任务消息已修改：\n" "  id: 1\n" "  messages: 2 条",
    )
    assert plugin.CONFIG["tasks"][0]["messages"] == ["新消息1", "新消息2"]


@pytest.mark.asyncio
async def test_edit_not_found(app: App, plugin):
    await run_cmd(
        app,
        plugin,
        "autospk edit time 42 08:30",
        "未找到任务 id = 42。",
    )
