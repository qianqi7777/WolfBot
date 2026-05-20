"""
游戏模式模块 — 可插拔的游戏模式系统

新增模式只需：
1. 在 base.py 中继承 BaseGameMode
2. 在 MODE_REGISTRY 中注册
3. 在场景预设或房间设置中指定 mode

Judge 会根据 mode 调用对应的钩子方法。
"""

from app.mode.base import BaseGameMode, ClassicMode, RoleSelectMode, MODE_REGISTRY, get_mode

__all__ = [
    "BaseGameMode",
    "ClassicMode",
    "RoleSelectMode",
    "MODE_REGISTRY",
    "get_mode",
]
