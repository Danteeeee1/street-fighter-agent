"""示例轨迹：用合成数据端到端演示整条流水线。

演示覆盖四类结论：漏确反、不安全被防、漏空振惩罚、机会点。
"""
from __future__ import annotations

from pathlib import Path
from typing import List, Tuple

from .analyzer import Analyzer
from .event_detect import segment_exchanges
from .frame_data import FrameDataLibrary
from .models import ContactResult, Exchange, Finding, FrameState
from .report import generate_report


def build_demo_frames(total_frames: int = 900, fps: int = 60) -> List[FrameState]:
    """构造一局 15 秒、含 4 次交手的样例帧序列。"""
    frames: List[FrameState] = []
    for i in range(1, total_frames + 1):
        frames.append(FrameState(
            frame_index=i,
            timestamp=round((i - 1) / fps, 4),
            round_number=1,
            timer=round(99.0 - (i - 1) / fps, 1),
        ))

    # 血量变化：帧 315 后 P1 被 Ken 确反掉血；帧 720 后 P2 被 2MK 命中掉血
    for fs in frames:
        if fs.frame_index >= 315:
            fs.p1_health = 70.0
        if fs.frame_index >= 720:
            fs.p2_health = 60.0

    # 事件注入
    events = [
        (120, dict(contact=ContactResult.BLOCK, p2_action="2HK", frame_advantage=12)),   # Ken 扫腿被防 -12
        (300, dict(contact=ContactResult.BLOCK, p1_action="623HP", frame_advantage=-32)),  # Ryu 升龙被防 -32
        (500, dict(contact=ContactResult.WHIFF, p2_action="5HP")),                        # Ken 5HP 挥空
        (700, dict(contact=ContactResult.HIT, p1_action="2MK", frame_advantage=4)),       # Ryu 2MK 命中 +4
    ]
    by_frame = {fs.frame_index: fs for fs in frames}
    for idx, fields in events:
        for k, v in fields.items():
            setattr(by_frame[idx], k, v)
    return frames


def run_demo(out_path: str, data_dir: str) -> Tuple[List[Exchange], List[Finding]]:
    lib = FrameDataLibrary.load_dir(data_dir)
    frames = build_demo_frames()
    exchanges = segment_exchanges(frames)
    analyzer = Analyzer(lib, "Ryu", "Ken")
    findings = analyzer.analyze(exchanges)

    match = {
        "title": "SF6 录像分析报告（演示样例）",
        "game": "Street Fighter 6",
        "p1_char": "Ryu",
        "p2_char": "Ken",
        "rounds": 1,
        "total_frames": len(frames),
        "duration": round((len(frames) - 1) / 60, 2),
        "fps": 60,
    }
    generate_report(match, exchanges, findings, out_path)
    return exchanges, findings
