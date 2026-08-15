"""测试辅助。

- load_module：直接加载 placeholders.py 源码，不经过包 __init__，
  避免收集阶段触发 NoneBot 相关代码
- 插件主模块由 conftest 通过 NoneBot 加载，测试内直接 import
"""

import importlib.util
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent


def load_module(rel: str):
    """加载插件包内的模块源码，如 placeholders => placeholders.py。"""
    full = rel  # 独立模块名，不占用插件包命名空间
    if full in sys.modules:
        return sys.modules[full]
    spec = importlib.util.spec_from_file_location(
        full, _ROOT / "nonebot_plugin_autospeak" / f"{rel}.py"
    )
    mod = importlib.util.module_from_spec(spec)
    sys.modules[full] = mod
    spec.loader.exec_module(mod)
    return mod
