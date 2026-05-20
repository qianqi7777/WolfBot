"""
四层对话压缩架构 — AI 狼人杀记忆管理

基于《模型对话压缩.md》的设计：

1. 滑动窗口（最底层）：保留最近 6-12 轮原始发言
2. 分层摘要（中层）：轮次摘要 / 阶段摘要 / 全局摘要
3. 结构化记忆（上层）：玩家状态、关键事件、指控链
4. 私有笔记（顶层）：AI 玩家自省短句

每个 AI 玩家都有独立的 MemoryStore 实例，
在构建 AI prompt 时拼接压缩后的上下文，
大幅减少 token 消耗的同时保留关键信息。
"""

import json
import logging
from dataclasses import dataclass, field
from typing import Any

from app.domain.enums import RoleType

logger = logging.getLogger(__name__)

# ─── 常量 ───────────────────────────────────────────────────────────

MAX_RECENT_TURNS = 8          # 滑动窗口保留最近 8 条原始发言
MAX_ROUND_SUMMARY_TOKENS = 150
MAX_PHASE_SUMMARY_TOKENS = 400
MAX_GLOBAL_SUMMARY_TOKENS = 500
MAX_PRIVATE_NOTES = 20        # 私有笔记上限
MAX_NOTE_LENGTH = 16          # 每条笔记最大字数


# ─── 第一层：滑动窗口 ───────────────────────────────────────────────

@dataclass
class SlidingWindow:
    """保留最近 N 条原始发言记录"""
    max_turns: int = MAX_RECENT_TURNS
    entries: list[dict[str, str]] = field(default_factory=list)  # [{speaker, content}]

    def add(self, speaker: str, content: str) -> None:
        self.entries.append({"speaker": speaker, "content": content})
        if len(self.entries) > self.max_turns:
            self.entries = self.entries[-self.max_turns:]

    def format(self) -> str:
        if not self.entries:
            return ""
        lines = [f"  {e['speaker']}：{e['content']}" for e in self.entries]
        return "【近期发言】\n" + "\n".join(lines)


# ─── 第二层：分层摘要 ───────────────────────────────────────────────

@dataclass
class LayeredSummary:
    """三级摘要：轮次 → 阶段 → 全局"""
    round_summaries: list[str] = field(default_factory=list)    # 每轮一条
    phase_summary: str = ""                                     # 每2-3轮合并
    global_summary: str = ""                                    # 游戏过半时生成

    def add_round_summary(self, summary: str) -> None:
        self.round_summaries.append(summary)

    def format(self) -> str:
        parts: list[str] = []
        if self.round_summaries:
            parts.append("【轮次摘要】\n" + "\n".join(f"  - {s}" for s in self.round_summaries[-5:]))
        if self.phase_summary:
            parts.append(f"【阶段摘要】\n  {self.phase_summary}")
        if self.global_summary:
            parts.append(f"【全局摘要】\n  {self.global_summary}")
        return "\n".join(parts)


# ─── 第三层：结构化记忆 ───────────────────────────────────────────────

@dataclass
class StructuredMemory:
    """key-value 形式的核心事实，token 极低"""
    # player_id -> "活,角色" / "死,角色"
    player_status: dict[str, str] = field(default_factory=dict)
<<<<<<< HEAD
    # 关键事件列表：["N1：刀5号，守卫守5号", "D1：放逐3号(狼)"]
    key_events: list[str] = field(default_factory=list)
    # 指控链：["1号→3号(查杀)", "3号→1号(查杀)"]
    accusation_chain: list[str] = field(default_factory=list)
    # 座位号映射：player_id -> seat_number
    seat_map: dict[str, int] = field(default_factory=dict)
=======
    # 关键事件列表：["N1：刀5，守卫守5", "D1：放逐3(狼)"]
    key_events: list[str] = field(default_factory=list)
    # 指控链：["1→3(查杀)", "3→1(查杀)"]
    accusation_chain: list[str] = field(default_factory=list)
>>>>>>> d0960c3afea4069bbb61c2a39010d4d7eeeb5f6b

    def update_player(self, player_id: str, alive: bool, role_hint: str = "") -> None:
        status = ("活" if alive else "死") + (f",{role_hint}" if role_hint else "")
        self.player_status[player_id] = status

    def add_event(self, event: str) -> None:
        self.key_events.append(event)

    def add_accusation(self, chain: str) -> None:
        self.accusation_chain.append(chain)

    def format(self) -> str:
        parts: list[str] = []
        if self.player_status:
<<<<<<< HEAD
            # 用座位号显示，如"3号(活,狼(队友))"
            status_lines = []
            for pid, s in self.player_status.items():
                seat = self.seat_map.get(pid, pid)
                status_lines.append(f"  {seat}号({s})")
=======
            status_lines = [f"  {pid}({s})" for pid, s in self.player_status.items()]
>>>>>>> d0960c3afea4069bbb61c2a39010d4d7eeeb5f6b
            parts.append("【玩家状态】\n" + " ".join(status_lines))
        if self.key_events:
            parts.append("【关键事件】\n" + "\n".join(f"  {e}" for e in self.key_events[-10:]))
        if self.accusation_chain:
            parts.append("【指控链】\n" + "\n".join(f"  {c}" for c in self.accusation_chain[-10:]))
        return "\n".join(parts)


# ─── 第四层：私有笔记 ───────────────────────────────────────────────

@dataclass
class PrivateNotes:
    """AI 玩家自省短句（10-20 条，每条 ≤16 字）"""
    notes: list[str] = field(default_factory=list)

    def add_or_update(self, note: str) -> None:
        """添加笔记，如果主题相同则覆盖，否则追加。
        主题判断：提取笔记开头的'X号'（如'3号'），相同则覆盖。"""
        note = note[:MAX_NOTE_LENGTH]
        import re
        m = re.match(r'^(\d+号)', note)
        prefix = m.group(1) if m else note[:3]
        for i, existing in enumerate(self.notes):
            ex_match = re.match(r'^(\d+号)', existing)
            ex_prefix = ex_match.group(1) if ex_match else existing[:3]
            if ex_prefix == prefix:
                self.notes[i] = note
                return
        self.notes.append(note)
        if len(self.notes) > MAX_PRIVATE_NOTES:
            self.notes = self.notes[-MAX_PRIVATE_NOTES:]

    def format(self) -> str:
        if not self.notes:
            return ""
        return "【我的笔记】\n" + " ".join(self.notes)


# ─── 统一 MemoryStore ────────────────────────────────────────────────

@dataclass
class MemoryStore:
    """每个 AI 玩家的完整记忆存储，四层合一"""
    player_id: str
    player_name: str = ""
    role: RoleType = RoleType.unknown
    sliding_window: SlidingWindow = field(default_factory=SlidingWindow)
    layered_summary: LayeredSummary = field(default_factory=LayeredSummary)
    structured_memory: StructuredMemory = field(default_factory=StructuredMemory)
    private_notes: PrivateNotes = field(default_factory=PrivateNotes)

    # ── 写入接口 ──

    def record_speech(self, speaker_name: str, content: str) -> None:
        """记录一条发言到滑动窗口"""
        self.sliding_window.add(speaker_name, content)

    def record_event(self, event: str) -> None:
        """记录关键事件到结构化记忆"""
        self.structured_memory.add_event(event)

    def record_accusation(self, chain: str) -> None:
        """记录指控到结构化记忆"""
        self.structured_memory.add_accusation(chain)

    def update_player_status(self, player_id: str, alive: bool, role_hint: str = "") -> None:
        """更新玩家存活状态"""
        self.structured_memory.update_player(player_id, alive, role_hint)

    def add_private_note(self, note: str) -> None:
        """添加私有笔记"""
        self.private_notes.add_or_update(note)

    def set_round_summary(self, summary: str) -> None:
        """设置本轮摘要"""
        self.layered_summary.add_round_summary(summary)

    def set_phase_summary(self, summary: str) -> None:
        """设置阶段摘要"""
        self.layered_summary.phase_summary = summary

    def set_global_summary(self, summary: str) -> None:
        """设置全局摘要"""
        self.layered_summary.global_summary = summary

    # ── 读取接口 ──

    def build_context(self, max_tokens: int = 2000) -> str:
        """构建压缩后的上下文文本，用于 AI prompt 拼接。

        按"结构化记忆 → 分层摘要 → 滑动窗口 → 私有笔记"的顺序拼接，
        确保最关键的信息在前。
        """
        sections: list[str] = []

        # 结构化记忆（最精炼，优先放）
        structured = self.structured_memory.format()
        if structured:
            sections.append(structured)

        # 分层摘要
        summary = self.layered_summary.format()
        if summary:
            sections.append(summary)

        # 滑动窗口（最近发言）
        window = self.sliding_window.format()
        if window:
            sections.append(window)

        # 私有笔记
        notes = self.private_notes.format()
        if notes:
            sections.append(notes)

        context = "\n\n".join(sections)

        # 简单截断保护（按字符估算，1 token ≈ 1.5 中文字符）
        max_chars = int(max_tokens * 1.5)
        if len(context) > max_chars:
            context = context[:max_chars] + "\n...(上下文已截断)"

        return context


# ─── 全局 Memory 管理器 ──────────────────────────────────────────────

class MemoryManager:
    """管理所有 AI 玩家的 MemoryStore"""

    def __init__(self) -> None:
        # (game_id, player_id) -> MemoryStore
        self._stores: dict[tuple[str, str], MemoryStore] = {}

    def get_or_create(self, game_id: str, player_id: str, player_name: str = "",
                      role: RoleType = RoleType.unknown) -> MemoryStore:
        key = (game_id, player_id)
        if key not in self._stores:
            self._stores[key] = MemoryStore(
                player_id=player_id,
                player_name=player_name,
                role=role,
            )
        return self._stores[key]

    def get(self, game_id: str, player_id: str) -> MemoryStore | None:
        return self._stores.get((game_id, player_id))

    def cleanup_game(self, game_id: str) -> None:
        """游戏结束后清理该局所有记忆"""
        keys_to_remove = [k for k in self._stores if k[0] == game_id]
        for k in keys_to_remove:
            del self._stores[k]


# 全局单例
memory_manager = MemoryManager()


# ─── 轮次摘要生成辅助 ────────────────────────────────────────────────

def build_round_summary_text(
    round_no: int,
    night_killed: str | None,
    guard_blocked: bool,
    speeches: list[dict[str, str]],
    vote_result: str | None,
    eliminated_name: str | None,
) -> str:
    """生成一轮的摘要文本（供存入 LayeredSummary）"""
    parts = [f"第{round_no}轮"]

    # 夜晚
    if night_killed:
        parts.append(f"N{round_no}：{night_killed}被杀")
    elif guard_blocked:
        parts.append(f"N{round_no}：平安夜（守卫守住）")
    else:
        parts.append(f"N{round_no}：平安夜")

    # 发言要点（取关键信息）
    if speeches:
        speech_names = [s.get("speaker", "?") for s in speeches[:3]]
        parts.append(f"发言：{','.join(speech_names)}等")

    # 投票
    if eliminated_name:
        parts.append(f"D{round_no}：放逐{eliminated_name}")
    else:
        parts.append(f"D{round_no}：无人出局")

    return "；".join(parts)


def update_structured_memory_from_game(
    store: MemoryStore,
    players: list[Any],
    game_id: str,
) -> None:
    """从游戏状态同步结构化记忆中的玩家状态"""
    for p in players:
<<<<<<< HEAD
        # 同步座位号映射
        if hasattr(p, 'seat_number') and p.seat_number:
            store.structured_memory.seat_map[p.id] = p.seat_number
=======
>>>>>>> d0960c3afea4069bbb61c2a39010d4d7eeeb5f6b
        # AI 玩家能看到的角色信息取决于自身角色
        role_hint = ""
        if store.role == RoleType.wolf and p.role == RoleType.wolf and p.id != store.player_id:
            role_hint = "狼(队友)"
        store.update_player_status(p.id, p.is_alive, role_hint)
