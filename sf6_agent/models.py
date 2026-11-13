"""核心数据模型。

SF6 以 60fps 运行，1 帧 = 1/60 秒 ≈ 16.67ms。
帧优（frame advantage）约定：本模块统一用「P1 视角」存储，
即 frame_advantage > 0 表示 P1 有利、< 0 表示 P1 不利。
切分成交手波次后，再转换为「进攻方视角」的 attacker_advantage。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class ContactResult(str, Enum):
    """一次交手的结果类型。"""
    HIT = "hit"                    # 命中
    BLOCK = "block"                # 被防
    WHIFF = "whiff"                # 空振
    COUNTER = "counter"            # 打康
    PUNISH_COUNTER = "punish_counter"  # 惩罚反击
    THROW = "throw"                # 投
    NONE = "none"


@dataclass
class Move:
    """单个招式的帧数据。"""
    name: str                      # 中文名，如「升龙拳」
    notation: str                  # 指令，如 "623HP" / "2MK"
    category: str = "normal"       # normal / special / super / throw
    startup: int = 0               # 发生帧
    active: int = 0                # 持续帧
    recovery: int = 0              # 收招帧
    on_hit: int = 0                # 命中后帧优
    on_block: int = 0              # 被防后帧优（负数=不利）
    damage: int = 0                # 基础伤害
    notes: str = ""

    @property
    def total_frames(self) -> int:
        return self.startup + self.active + self.recovery


@dataclass
class FrameState:
    """单帧画面状态（由 VisionProvider 产出）。"""
    frame_index: int
    timestamp: float               # 秒
    round_number: int = 1
    timer: float = 99.0
    p1_health: float = 100.0
    p2_health: float = 100.0
    p1_drive: int = 6              # 驱动槽剩余段数
    p2_drive: int = 6
    p1_super: int = 0
    p2_super: int = 0
    frame_advantage: Optional[int] = None   # P1 视角帧优
    contact: ContactResult = ContactResult.NONE
    p1_action: Optional[str] = None         # 该帧 P1 使用的招式指令
    p2_action: Optional[str] = None         # 该帧 P2 使用的招式指令


class FindingType(str, Enum):
    MISSED_PUNISH = "missed_punish"          # 漏确反
    UNSAFE_ON_BLOCK = "unsafe_on_block"      # 不安全被防
    MISSED_WHIFF_PUNISH = "missed_whiff_punish"  # 漏空振惩罚
    OPPORTUNITY = "opportunity"              # 机会点


class Severity(str, Enum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass
class Exchange:
    """一次交手波次：从出招到恢复中立的连续片段。"""
    exchange_id: int
    round_number: int
    start_frame: int
    end_frame: int
    start_time: float
    end_time: float
    attacker: int = 1               # 发起进攻的一方：1 或 2
    attacker_action: Optional[str] = None
    defender_action: Optional[str] = None
    attacker_advantage: Optional[int] = None   # 进攻方视角帧优
    contact: ContactResult = ContactResult.NONE
    p1_damage_taken: float = 0.0    # 该波次内 P1 承受的伤害
    p2_damage_taken: float = 0.0    # 该波次内 P2 承受的伤害
    summary: str = ""

    def damage_taken_by(self, player: int) -> float:
        return self.p1_damage_taken if player == 1 else self.p2_damage_taken

    @property
    def duration_frames(self) -> int:
        return self.end_frame - self.start_frame


@dataclass
class Finding:
    """一条分析结论：某个失误或机会点。"""
    finding_id: int
    exchange_id: int
    finding_type: FindingType
    severity: Severity
    start_frame: int
    end_frame: int
    player: int                    # 犯失误/拥有机会的一方：1 或 2
    title: str
    description: str
    opportunity: str
    solution: str
    frame_advantage: Optional[int] = None
