"""pytest 全局配置。

- NoneBot 初始化参数：不加载插件、不启动 APScheduler、预设 SUPERUSER
- 插件必须通过 NoneBot 加载：localstore 通过调用栈识别插件，
  手动 exec 的模块无法被识别
"""

import os
import sys
from pathlib import Path

import pytest
import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter
from nonebug import NONEBOT_INIT_KWARGS

_PLUGIN_ROOT = Path(__file__).resolve().parent.parent


def pytest_configure(config: pytest.Config):
    # 插件未安装到 site-packages，把源码根目录加入导入路径
    if str(_PLUGIN_ROOT) not in sys.path:
        sys.path.insert(0, str(_PLUGIN_ROOT))
    config.stash[NONEBOT_INIT_KWARGS] = {
        "plugin_dirs": [],
        "apscheduler_autostart": False,
        "superusers": {"10001"},
        "command_start": [""],  # 插件帮助中的示例均不带前缀
    }


@pytest.fixture(scope="session", autouse=True)
async def after_nonebot_init(after_nonebot_init: None, tmp_path_factory):
    """注册适配器并加载插件。"""
    driver = nonebot.get_driver()
    driver.register_adapter(OneBotV11Adapter)
    # 插件加载时 localstore 按当前工作目录计算路径，
    # 先切到临时目录，避免在仓库根目录生成 config/、data/
    old_cwd = os.getcwd()
    os.chdir(tmp_path_factory.mktemp("autospeak_session"))
    try:
        nonebot.load_plugin("nonebot_plugin_autospeak")
    finally:
        os.chdir(old_cwd)
