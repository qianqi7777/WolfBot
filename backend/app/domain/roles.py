"""
角色技能注册表 (Role Skill Registry)

每个角色定义为一个 RoleSkill 对象，包含该角色的全部行为描述：
- 基础信息：ID、中文名、阵营
- 夜间行动：是否有夜间技能、行动类型、AI 自动决策、真人提示
- AI 提示词：角色提示、mock 发言模板
- 验证规则：夜间目标选择限制

场景预设只需声明角色组合即可，扩展 9 人场/12 人场只需新增 preset。
"""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from typing import Callable

from app.domain.enums import RoleType


# ------------------------------------------------------------------
#  数据结构
# ------------------------------------------------------------------

@dataclass(frozen=True)
class RoleSkill:
    """角色技能定义 — 不可变对象"""

    role_id: RoleType                    # 角色枚举值
    name: str                            # 中文名称
    faction: str                         # 阵营：wolf / civilian
    has_night_action: bool               # 是否有夜间行动
    night_action_type: str               # 夜间行动类型：kill / check / guard / "" (无)
    ai_hint: str                         # AI 提示词（描述身份和目标）
    human_hint: str                       # 真人夜间行动提示
    mock_speeches: list[str]             # mock 发言模板
    can_target_self: bool = False        # 夜间能否选自己
    consecutive_target_allowed: bool = True  # 能否连续选同一目标（守卫=否）
    win_faction_label: str = ""          # 胜利时显示的阵营名

    def __post_init__(self):
        if not self.win_faction_label:
            if self.faction == "wolf":
                object.__setattr__(self, "win_faction_label", "狼人阵营")
            else:
                object.__setattr__(self, "win_faction_label", "好人阵营")


@dataclass(frozen=True)
class ScenePreset:
    """场景预设 — 声明角色组合"""
    preset_id: str                       # 预设 ID，如 "six-player-dark"
    name: str                            # 中文名，如 "6人暗牌场"
    description: str                      # 描述
    player_count: int                    # 玩家人数
    role_distribution: dict[RoleType, int]  # 角色分配：{RoleType: 数量}
    is_dark: bool = True                 # 是否暗牌
    has_sheriff: bool = False            # 是否有警长

    @property
    def total_roles(self) -> int:
        return sum(self.role_distribution.values())


# ------------------------------------------------------------------
#  角色技能定义
# ------------------------------------------------------------------

WOLF_SKILL = RoleSkill(
    role_id=RoleType.wolf,
    name="狼人",
    faction="wolf",
    has_night_action=True,
    night_action_type="kill",
    ai_hint="你是狼人阵营。你的目标是伪装成好人，引导投票方向，夜间与同伴协商击杀目标。",
    human_hint="你是狼人，请选择今晚要袭击的目标",
    mock_speeches=[
        "我觉得大家先冷静分析一下，不要急着站队。",
        "我没什么特别的信息，但我感觉有人在带节奏。",
        "我先观察一下，目前没有明确的怀疑对象。",
        "大家注意一下发言逻辑，我觉得有人在故意引导方向。",
    ],
)

CIVILIAN_SKILL = RoleSkill(
    role_id=RoleType.civilian,
    name="平民",
    faction="civilian",
    has_night_action=False,
    night_action_type="",
    ai_hint="你是平民（好人阵营）。你没有特殊技能，但可以通过发言和投票找出狼人。",
    human_hint="",
    mock_speeches=[
        "我是好人，目前还在整理线索，先听听大家的分析。",
        "我没什么特殊信息，但我觉得有些人的发言有矛盾。",
        "大家能不能再说说自己的推理过程？我想参考一下。",
        "我目前比较关注发言比较少的玩家。",
    ],
)

PROPHET_SKILL = RoleSkill(
    role_id=RoleType.prophet,
    name="预言家",
    faction="civilian",
    has_night_action=True,
    night_action_type="check",
    ai_hint="你是预言家（好人阵营）。你每晚可以查验一名玩家的身份，发言时要谨慎，避免过早暴露自己，同时传递查验信息。",
    human_hint="你是预言家，请选择今晚要查验的目标",
    mock_speeches=[
        "我手上有一些信息，但现在不是公开的时候。",
        "我觉得大家的发言可以再深入一点。",
        "我注意到有些发言不太自然，后续我会详细分析。",
        "我需要再观察一轮，目前还不方便给出判断。",
    ],
)

GUARD_SKILL = RoleSkill(
    role_id=RoleType.guard,
    name="守卫",
    faction="civilian",
    has_night_action=True,
    night_action_type="guard",
    ai_hint="你是守卫（好人阵营）。你每晚可以守护一名玩家免受狼人袭击，发言时不要暴露身份，注意保护关键神职。",
    human_hint="你是守卫，请选择今晚要守护的目标（不能连续守同一人）",
    mock_speeches=[
        "我觉得大家不要急于暴露信息，先整理一下思路。",
        "我目前还在观察，有些人的表现值得关注。",
        "我暂时没有特别的判断，先听听大家的意见。",
        "我建议大家注意一下自己的发言方式，不要给狼人太多信息。",
    ],
    consecutive_target_allowed=False,   # 守卫不能连续两晚守同一人
)

# ------------------------------------------------------------------
#  扩展角色（9 人场 / 12 人场预留）
# ------------------------------------------------------------------

HUNTER_SKILL = RoleSkill(
    role_id=RoleType.hunter,
    name="猎人",
    faction="civilian",
    has_night_action=False,
    night_action_type="",
    ai_hint="你是猎人（好人阵营）。你被投票出局或被狼人杀害时可以开枪带走一人，注意不要误伤好人。",
    human_hint="",
    mock_speeches=[
        "我觉得大家不要太冲动，让我先把情况理清楚。",
        "我手上没什么特别的信息，但我在认真听大家发言。",
        "如果有人想对我动手，我也不会坐以待毙。",
        "大家理性分析，别被狼人带偏了。",
    ],
    can_target_self=False,
)

WITCH_SKILL = RoleSkill(
    role_id=RoleType.witch,
    name="女巫",
    faction="civilian",
    has_night_action=True,
    night_action_type="witch",
    ai_hint="你是女巫（好人阵营）。你有一瓶解药和一瓶毒药，各只能使用一次，谨慎使用。",
    human_hint="你是女巫，是否使用解药救人或毒药杀人",
    mock_speeches=[
        "我手上有些信息需要确认，先不急着表态。",
        "大家发言要负责任，有些话说了就收不回来。",
        "我在仔细听，有些发言让我有了一些想法。",
        "我暂时选择保守，先观察一轮。",
    ],
)


# ------------------------------------------------------------------
#  注册表
# ------------------------------------------------------------------

# 所有角色技能注册到字典
SKILL_REGISTRY: dict[RoleType, RoleSkill] = {
    RoleType.wolf: WOLF_SKILL,
    RoleType.civilian: CIVILIAN_SKILL,
    RoleType.prophet: PROPHET_SKILL,
    RoleType.guard: GUARD_SKILL,
    RoleType.hunter: HUNTER_SKILL,
    RoleType.witch: WITCH_SKILL,
    RoleType.unknown: RoleSkill(
        role_id=RoleType.unknown,
        name="未知",
        faction="civilian",
        has_night_action=False,
        night_action_type="",
        ai_hint="你的身份未知，请按正常玩家语气发言。",
        human_hint="",
        mock_speeches=["我先听听大家的意见，再做判断。"],
    ),
}


def get_skill(role: RoleType) -> RoleSkill:
    """获取角色技能定义"""
    return SKILL_REGISTRY[role]


def get_night_action_roles() -> list[RoleType]:
    """获取所有有夜间行动的角色（按行动顺序排列）"""
    # 标准夜间行动顺序：狼人 → 预言家 → 女巫 → 守卫
    order = [RoleType.wolf, RoleType.prophet, RoleType.witch, RoleType.guard]
    return [r for r in order if r in SKILL_REGISTRY and SKILL_REGISTRY[r].has_night_action]


def get_mock_speech(role: RoleType, round_no: int = 1) -> str:
    """获取角色的 mock 发言"""
    skill = get_skill(role)
    options = skill.mock_speeches
    return random.choice(options) if options else "..."

# ------------------------------------------------------------------
#  场景预设注册表
# ------------------------------------------------------------------

SCENE_PRESETS: dict[str, ScenePreset] = {
    "six-player-dark": ScenePreset(
        preset_id="six-player-dark",
        name="6人暗牌场",
        description="2狼4好人，神职为预言家和守卫，暗牌局，无警长，节奏快。",
        player_count=6,
        role_distribution={
            RoleType.wolf: 2,
            RoleType.prophet: 1,
            RoleType.guard: 1,
            RoleType.civilian: 2,
        },
        is_dark=True,
        has_sheriff=False,
    ),
    "nine-player-dark": ScenePreset(
        preset_id="nine-player-dark",
        name="9人暗牌场",
        description="3狼6好人，神职为预言家、守卫、猎人，暗牌局，无警长。",
        player_count=9,
        role_distribution={
            RoleType.wolf: 3,
            RoleType.prophet: 1,
            RoleType.guard: 1,
            RoleType.hunter: 1,
            RoleType.civilian: 3,
        },
        is_dark=True,
        has_sheriff=False,
    ),
    "twelve-player-dark": ScenePreset(
        preset_id="twelve-player-dark",
        name="12人暗牌场",
        description="4狼8好人，神职为预言家、守卫、女巫、猎人，暗牌局，有警长。",
        player_count=12,
        role_distribution={
            RoleType.wolf: 4,
            RoleType.prophet: 1,
            RoleType.guard: 1,
            RoleType.witch: 1,
            RoleType.hunter: 1,
            RoleType.civilian: 4,
        },
        is_dark=True,
        has_sheriff=True,
    ),
}


def get_preset(preset_id: str) -> ScenePreset:
    """获取场景预设"""
    if preset_id not in SCENE_PRESETS:
        raise ValueError(f"未知场景预设: {preset_id}，可选: {list(SCENE_PRESETS.keys())}")
    return SCENE_PRESETS[preset_id]


def build_role_list(preset_id: str) -> list[RoleType]:
    """根据预设构建角色列表（已洗牌）"""
    preset = get_preset(preset_id)
    roles: list[RoleType] = []
    for role_type, count in preset.role_distribution.items():
        roles.extend([role_type] * count)
    random.shuffle(roles)
    return roles
