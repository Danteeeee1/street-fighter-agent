"""确反/立回分析引擎。

核心判定规则（进攻方视角 attacker_advantage）：
- 被防（BLOCK）且 attacker_advantage <= -最快起手：
    可确反。若进攻方随后挨打 -> 不安全被防（进攻方失误）；
    若防守方没反打 -> 漏确反（防守方错失机会）。
- 空振（WHIFF）且防守方未惩罚 -> 漏空振惩罚（防守方错失机会）。
- attacker_advantage > 0（命中/被防有利）-> 机会点（进攻方有利，供参考）。
"""
from __future__ import annotations

from typing import List, Optional

from .frame_data import CharacterFrameData, FrameDataLibrary
from .knowledge import render
from .models import ContactResult, Exchange, Finding, FindingType, Severity


class Analyzer:
    def __init__(self, lib: FrameDataLibrary, p1_char: str, p2_char: str):
        self.lib = lib
        self.p1_char = p1_char
        self.p2_char = p2_char

    def _char(self, player: int) -> str:
        return self.p1_char if player == 1 else self.p2_char

    def _frame_data(self, player: int) -> Optional[CharacterFrameData]:
        return self.lib.get(self._char(player))

    def analyze(self, exchanges: List[Exchange]) -> List[Finding]:
        findings: List[Finding] = []
        for ex in exchanges:
            findings.extend(self._analyze_exchange(ex))
        # 重新编号
        for i, f in enumerate(findings, start=1):
            f.finding_id = i
        return findings

    def _analyze_exchange(self, ex: Exchange) -> List[Finding]:
        attacker, defender = ex.attacker, 3 - ex.attacker
        defender_fd = self._frame_data(defender)
        attacker_fd = self._frame_data(attacker)
        fav = ex.attacker_advantage
        out: List[Finding] = []

        # 负帧优：出招方（attacker）处于不利硬直（被防/命中后），
        # 无论接触类型是否已知，都进入确反判定；用血条变化判断是否被确反。
        if fav is not None and fav < 0:
            out.extend(self._block_rules(ex, attacker, defender, -fav,
                                         attacker_fd, defender_fd))
        elif ex.contact == ContactResult.WHIFF:
            out.extend(self._whiff_rules(ex, attacker, defender, attacker_fd, defender_fd))
        elif fav is not None and fav > 0:
            out.extend(self._opportunity(ex, attacker, fav))

        return out

    def _block_rules(self, ex, attacker, defender, punish_window,
                     attacker_fd, defender_fd) -> List[Finding]:
        out: List[Finding] = []
        fastest = defender_fd.fastest_startup() if defender_fd else None
        fastest_startup = fastest.startup if fastest else 5
        punishable = punish_window >= fastest_startup
        if not punishable:
            return out

        attacker_move = self._resolve_move(attacker_fd, ex.attacker_action)
        punish_move = self._resolve_move(defender_fd, None) or (fastest or None)
        punish_name = punish_move.name if punish_move else "最快起手"
        punish_startup = punish_move.startup if punish_move else fastest_startup
        move_name = attacker_move.name if attacker_move else (ex.attacker_action or "该招式")

        attacker_took_damage = ex.damage_taken_by(attacker) > 0

        if attacker_took_damage:
            # 不安全被防：进攻方被确反
            safe = self._safer_move(attacker_fd, attacker_move)
            safe_name = safe.name if safe else "更安全的招式"
            safe_adv = safe.on_block if safe else 0
            out.append(Finding(
                finding_id=0, exchange_id=ex.exchange_id,
                finding_type=FindingType.UNSAFE_ON_BLOCK, severity=Severity.HIGH,
                start_frame=ex.start_frame, end_frame=ex.end_frame, player=attacker,
                title=f"不安全被防：{move_name} 被确反",
                description=render("unsafe_on_block", move=move_name, adv=punish_window,
                                   safe=safe_name, safe_adv=safe_adv),
                opportunity=f"你被防 -{punish_window} 帧，被对方 {punish_name} 确反。",
                solution=render("unsafe_on_block", move=move_name, adv=punish_window,
                                safe=safe_name, safe_adv=safe_adv),
                frame_advantage=-punish_window,
            ))
        else:
            # 漏确反：防守方没反打
            out.append(Finding(
                finding_id=0, exchange_id=ex.exchange_id,
                finding_type=FindingType.MISSED_PUNISH, severity=Severity.HIGH,
                start_frame=ex.start_frame, end_frame=ex.end_frame, player=defender,
                title=f"漏确反：对手 {move_name} -{punish_window} 帧未惩罚",
                description=render("missed_punish", move=move_name, adv=punish_window,
                                   punish=punish_name, startup=punish_startup),
                opportunity=f"对手招式被防 -{punish_window} 帧，你的 {punish_name}（发生 {punish_startup} 帧）可确反。",
                solution=render("missed_punish_opportunity", move=move_name, adv=punish_window,
                                punish=punish_name, startup=punish_startup,
                                combo=self._combo_for(defender_fd, punish_move)),
                frame_advantage=-punish_window,
            ))
        return out

    def _whiff_rules(self, ex, attacker, defender, attacker_fd, defender_fd) -> List[Finding]:
        out: List[Finding] = []
        attacker_move = self._resolve_move(attacker_fd, ex.attacker_action)
        move_name = attacker_move.name if attacker_move else (ex.attacker_action or "该招式")
        recovery = attacker_move.recovery if attacker_move else 0

        fastest = defender_fd.fastest_startup() if defender_fd else None
        punish_move = self._resolve_move(defender_fd, None) or (fastest or None)
        punish_name = punish_move.name if punish_move else "最快起手"
        punish_startup = punish_move.startup if punish_move else 5

        if ex.damage_taken_by(attacker) == 0:
            out.append(Finding(
                finding_id=0, exchange_id=ex.exchange_id,
                finding_type=FindingType.MISSED_WHIFF_PUNISH, severity=Severity.MEDIUM,
                start_frame=ex.start_frame, end_frame=ex.end_frame, player=defender,
                title=f"漏空振惩罚：对手 {move_name} 挥空未惩罚",
                description=render("missed_whiff_punish", move=move_name, recovery=recovery,
                                   punish=punish_name, startup=punish_startup),
                opportunity=f"对手空振，收招 {recovery} 帧，可用 {punish_name}（发生 {punish_startup} 帧）确反。",
                solution=render("missed_whiff_punish", move=move_name, recovery=recovery,
                                punish=punish_name, startup=punish_startup),
                frame_advantage=None,
            ))
        return out

    def _opportunity(self, ex, attacker, fav) -> List[Finding]:
        out = [Finding(
            finding_id=0, exchange_id=ex.exchange_id,
            finding_type=FindingType.OPPORTUNITY, severity=Severity.LOW,
            start_frame=ex.start_frame, end_frame=ex.end_frame, player=attacker,
            title=f"机会点：+{fav} 帧有利",
            description=render("opportunity", adv=fav),
            opportunity=f"该波次你处于 +{fav} 帧有利。",
            solution=render("opportunity", adv=fav),
            frame_advantage=fav,
        )]
        return out

    # ---- 辅助 ----
    def _resolve_move(self, fd, notation):
        if not fd:
            return None
        if notation:
            m = fd.get(notation)
            if m:
                return m
        return None

    def _safer_move(self, fd, current):
        """找一个被防帧优更安全、发生帧相近的替代招式。"""
        if not fd:
            return None
        cur_adv = current.on_block if current else -99
        cur_startup = current.startup if current else 99
        candidates = [m for m in fd.moves
                      if m.on_block > cur_adv and abs(m.startup - cur_startup) <= 6]
        if not candidates:
            return None
        return max(candidates, key=lambda m: m.on_block)

    def _combo_for(self, fd, opener):
        """给一个简化的确反连段建议（起手后接主力技）。"""
        if not fd or not opener:
            return f"{opener.name if opener else '最快起手'} → 主力取消技"
        specials = [m for m in fd.moves if m.category in ("special", "super")]
        if specials:
            follow = min(specials, key=lambda m: m.startup)
            return f"{opener.name} → {follow.name}"
        return f"{opener.name} → 简单收尾连段"
