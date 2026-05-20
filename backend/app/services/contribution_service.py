"""
贡献率计算服务 — 参考网易狼人杀评分规则

评分体系：
  基础分：胜利 +3，失败 -3
  投票分（好人）：
    - 投狼出局 +0.5，投狼未出 +0.25
    - 投好人出局 -0.5，投好人未出 -0.25
    - 弃票 0
  投票分（狼人）：
    - 投好人出局 +0.5，投狼 -0.5
    - 弃票 0
  角色加分：
    - 预言家：验到狼 +1/次
    - 守卫：守住平安夜 +1/次
  MVP：本局最高贡献分玩家（胜方/败方各一个）
"""

from __future__ import annotations

from typing import Any

from app.domain.enums import RoleType
from app.domain.roles import SKILL_REGISTRY
from app.schemas.player import Player


def compute_contributions(
    players: list[Player],
    round_events: list[dict[str, Any]],
    winner_faction: str | None,
) -> list[dict[str, Any]]:
    """计算所有玩家的贡献率和评分。

    返回: [{"playerId": str, "playerName": str, "role": str, "score": float,
            "isAlive": bool, "isAI": bool, "details": list[str]}, ...]
    """
    scores: dict[str, float] = {p.id: 0.0 for p in players}
    details: dict[str, list[str]] = {p.id: [] for p in players}
    player_map = {p.id: p for p in players}
    faction_map = {p.id: SKILL_REGISTRY[p.role].faction for p in players}

    # ── 基础分 ──
    for p in players:
        if winner_faction:
            player_faction = faction_map.get(p.id, "civilian")
            if player_faction == winner_faction or (
                winner_faction == "civilian" and player_faction == "civilian"
            ):
                scores[p.id] += 3.0
                details[p.id].append("胜利 +3")
            else:
                scores[p.id] -= 3.0
                details[p.id].append("失败 -3")

    # ── 遍历每轮事件 ──
    for event in round_events:
        event_type = event.get("type")

        if event_type == "vote":
            _score_vote_event(event, players, player_map, faction_map, scores, details)

        elif event_type == "night":
            _score_night_event(event, players, player_map, scores, details)

    # ── 构建结果 ──
    result = []
    for p in players:
        result.append({
            "playerId": p.id,
            "playerName": f"{p.seat_number}号({p.name})",
            "role": p.role.value,
            "faction": faction_map.get(p.id, "unknown"),
            "score": round(scores[p.id], 2),
            "isAlive": p.is_alive,
            "isAI": p.is_ai,
            "details": details[p.id],
        })

    # 按分数降序排列
    result.sort(key=lambda x: x["score"], reverse=True)
    return result


def _score_vote_event(
    event: dict[str, Any],
    players: list[Player],
    player_map: dict[str, Player],
    faction_map: dict[str, str],
    scores: dict[str, float],
    details: dict[str, list[str]],
) -> None:
    """计算投票事件的得分"""
    votes = event.get("votes", [])
    eliminated_id = event.get("eliminated_id")
    round_no = event.get("round", "?")

    # 被淘汰者的阵营
    eliminated_faction = None
    if eliminated_id:
        eliminated_faction = faction_map.get(str(eliminated_id))

    for vote in votes:
        voter_id = str(vote.get("voterId", ""))
        target_id = str(vote.get("targetId", ""))
        voter = player_map.get(voter_id)
        if not voter:
            continue

        voter_faction = faction_map.get(voter_id, "civilian")

        if target_id == "abstain":
            details[voter_id].append(f"第{round_no}轮弃票 0")
            continue

        target_faction = faction_map.get(target_id, "civilian")
        target_eliminated = (target_id == str(eliminated_id)) if eliminated_id else False

        if voter_faction == "wolf":
            # 狼人投票
            if target_faction == "civilian" and target_eliminated:
                scores[voter_id] += 0.5
                details[voter_id].append(f"第{round_no}轮投好人出局 +0.5")
            elif target_faction == "wolf":
                scores[voter_id] -= 0.5
                details[voter_id].append(f"第{round_no}轮投狼人 -0.5")
        else:
            # 好人投票
            if target_faction == "wolf":
                if target_eliminated:
                    scores[voter_id] += 0.5
                    details[voter_id].append(f"第{round_no}轮投狼出局 +0.5")
                else:
                    scores[voter_id] += 0.25
                    details[voter_id].append(f"第{round_no}轮投狼未出 +0.25")
            else:
                # 投了好人
                if target_eliminated:
                    scores[voter_id] -= 0.5
                    details[voter_id].append(f"第{round_no}轮投好人出局 -0.5")
                else:
                    scores[voter_id] -= 0.25
                    details[voter_id].append(f"第{round_no}轮投好人未出 -0.25")


def _score_night_event(
    event: dict[str, Any],
    players: list[Player],
    player_map: dict[str, Player],
    scores: dict[str, float],
    details: dict[str, list[str]],
) -> None:
    """计算夜间事件的得分"""
    round_no = event.get("round", "?")

    # 预言家验人
    prophet_checks = event.get("prophet_checks", [])
    for check in prophet_checks:
        prophet_id = str(check.get("prophet_id", ""))
        is_wolf = check.get("is_wolf", False)
        if is_wolf:
            scores[prophet_id] += 1.0
            details[prophet_id].append(f"第{round_no}轮验到狼 +1")

    # 守卫守住
    guard_saves = event.get("guard_saves", [])
    for save in guard_saves:
        guard_id = str(save.get("guard_id", ""))
        saved = save.get("saved", False)
        if saved:
            scores[guard_id] += 1.0
            details[guard_id].append(f"第{round_no}轮守住平安夜 +1")


def get_mvp(contributions: list[dict[str, Any]], winner_faction: str | None) -> dict[str, Any] | None:
    """获取 MVP（胜利方最高分）"""
    if not contributions or not winner_faction:
        return None

    # 胜方 MVP
    winner_side = [c for c in contributions if c.get("faction") == winner_faction or
                   (winner_faction == "civilian" and c.get("faction") == "civilian")]
    if winner_side:
        return winner_side[0]  # 已按分数降序排列

    return contributions[0] if contributions else None


def get_svp(contributions: list[dict[str, Any]], winner_faction: str | None) -> dict[str, Any] | None:
    """获取 SVP（失败方最高分）"""
    if not contributions or not winner_faction:
        return None

    loser_faction = "wolf" if winner_faction == "civilian" else "civilian"
    loser_side = [c for c in contributions if c.get("faction") == loser_faction]
    if loser_side:
        return loser_side[0]

    return None
