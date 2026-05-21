"""
角色行动模块 (Role Action Modules)

每个角色一个独立模块，包含该角色的：
- 夜间行动逻辑
- 白天特殊逻辑（如猎人开枪、白痴翻牌等）
- AI决策策略

板子预设通过 active_roles 列表决定加载哪些角色模块。
"""

from typing import Protocol, runtime_checkable

from app.domain.enums import RoleType


@runtime_checkable
class RoleAction(Protocol):
    """角色行动接口协议"""

    role_type: RoleType

    @classmethod
    async def night_action(cls, judge, game) -> None:
        """夜间行动：法官询问该角色，处理AI/真人行动"""
        ...

    @classmethod
    async def day_action(cls, judge, game) -> None:
        """白天特殊行动（如猎人开枪、白痴翻牌等），可选"""
        ...

    @classmethod
    def ai_night_target(cls, game, player) -> tuple[str, str]:
        """AI夜间目标选择，返回 (target_id, action_type)"""
        ...


# 角色模块注册表
ROLE_ACTION_REGISTRY: dict[RoleType, type[RoleAction]] = {}


def register_role_action(role_type: RoleType, action_class: type[RoleAction]) -> None:
    """注册角色行动模块"""
    ROLE_ACTION_REGISTRY[role_type] = action_class


def get_role_action(role_type: RoleType) -> type[RoleAction] | None:
    """获取角色行动模块"""
    return ROLE_ACTION_REGISTRY.get(role_type)


def get_active_role_actions(preset_id: str) -> list[type[RoleAction]]:
    """根据板子预设获取需要加载的角色行动模块列表"""
    from app.domain.roles import get_preset
    try:
        preset = get_preset(preset_id)
        active_roles = preset.active_roles
    except (ValueError, AttributeError):
        # 兼容旧预设：没有 active_roles 时使用所有有夜间行动的角色
        from app.domain.roles import get_night_action_roles
        active_roles = get_night_action_roles()

    result = []
    for role_type in active_roles:
        action = ROLE_ACTION_REGISTRY.get(role_type)
        if action:
            result.append(action)
    return result


# 延迟导入并注册所有角色模块
def _load_role_modules() -> None:
    """加载所有角色模块"""
    from app.roles.wolf import WolfAction
    from app.roles.prophet import ProphetAction
    from app.roles.witch import WitchAction
    from app.roles.guard import GuardAction
    from app.roles.hunter import HunterAction
    from app.roles.idiot import IdiotAction

    register_role_action(RoleType.wolf, WolfAction)
    register_role_action(RoleType.prophet, ProphetAction)
    register_role_action(RoleType.witch, WitchAction)
    register_role_action(RoleType.guard, GuardAction)
    register_role_action(RoleType.hunter, HunterAction)
    register_role_action(RoleType.idiot, IdiotAction)


# 模块加载时自动注册
_load_role_modules()
