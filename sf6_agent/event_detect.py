"""事件检测与波次切分。

把逐帧的 FrameState 序列切分为「交手波次」（Exchange）：
- 以出现接触（contact != NONE）或出现帧优读数的帧为「事件帧」；
- 相邻事件帧间隔小于 exchange_merge_gap 时合并为同一波次；
- 波次向事件前后各扩展 window 帧，覆盖出招起手与收招硬直。

另提供基于本地 CV 的「事件帧」检测：帧差分（画面剧变）+ 血条突变（掉血），
用于在调用 LLM 读帧优之前，先筛出值得分析的交手时刻。
"""
from __future__ import annotations

from typing import List, Optional, Tuple

from .models import ContactResult, Exchange, FrameState


def detect_frame_changes(
    frame_paths: List[str],
    diff_threshold: float = 20.0,
    sample_width: int = 480,
) -> List[int]:
    """帧差分检测：返回「画面剧变」的帧索引列表（0 起）。

    diff_threshold 为相邻帧灰度差均值阈值，需按录像标定。
    SF6 训练模式画面常态抖动约 11，攻击特效约 20+，故默认 20。
    """
    import cv2  # noqa: WPS433

    events: List[int] = []
    prev = None
    for i, p in enumerate(frame_paths):
        img = cv2.imread(p, cv2.IMREAD_GRAYSCALE)
        if img is None:
            prev = None
            continue
        h, w = img.shape[:2]
        scale = sample_width / w
        img = cv2.resize(img, (sample_width, int(h * scale)), interpolation=cv2.INTER_AREA)
        if prev is not None:
            diff = float(cv2.absdiff(img, prev).mean())
            if diff > diff_threshold:
                events.append(i)
        prev = img
    return events


def detect_health_drops(frames: List[FrameState], min_drop: float = 5.0) -> List[int]:
    """血条突变检测：返回「掉血」帧的索引列表（相对 frames 下标）。

    min_drop 为相邻帧血量下降阈值；颜色检测存在约 0.1~0.3 的噪声，默认 5.0 过滤。
    """
    events: List[int] = []
    for i in range(1, len(frames)):
        d1 = frames[i - 1].p1_health - frames[i].p1_health
        d2 = frames[i - 1].p2_health - frames[i].p2_health
        if d1 >= min_drop or d2 >= min_drop:
            events.append(i)
    return events


def cluster_indices(indices: List[int], gap: int = 6) -> List[List[int]]:
    """把稀疏索引按间隔聚类，返回每组索引。"""
    if not indices:
        return []
    indices = sorted(set(indices))
    clusters: List[List[int]] = []
    cur = [indices[0]]
    for idx in indices[1:]:
        if idx - cur[-1] <= gap:
            cur.append(idx)
        else:
            clusters.append(cur)
            cur = [idx]
    clusters.append(cur)
    return clusters


def pick_event_frames(frame_paths: List[str], frames: List[FrameState],
                      diff_threshold: float = 20.0, min_drop: float = 5.0) -> List[int]:
    """综合帧差分 + 血条突变，选出需要 LLM 读帧优的事件帧下标。"""
    diff_events = detect_frame_changes(frame_paths, diff_threshold)
    health_events = detect_health_drops(frames, min_drop)
    all_events = sorted(set(diff_events + health_events))
    clusters = cluster_indices(all_events, gap=6)
    # 每个簇取「峰值」帧（簇中点）
    return [cl[len(cl) // 2] for cl in clusters]


def segment_exchanges(
    frames: List[FrameState],
    window_before: int = 30,
    window_after: int = 45,
    merge_gap: int = 20,
) -> List[Exchange]:
    """切分交手波次。frames 需按 frame_index 升序。"""
    frames = sorted(frames, key=lambda f: f.frame_index)
    if not frames:
        return []

    # 1) 找出事件帧
    event_indices = [
        i for i, f in enumerate(frames)
        if f.contact != ContactResult.NONE or f.frame_advantage is not None
    ]
    if not event_indices:
        return []

    # 2) 按帧间隔聚类
    clusters: List[List[int]] = []
    cur = [event_indices[0]]
    for idx in event_indices[1:]:
        if idx - cur[-1] <= merge_gap:
            cur.append(idx)
        else:
            clusters.append(cur)
            cur = [idx]
    clusters.append(cur)

    # 3) 生成 Exchange
    exchanges: List[Exchange] = []
    first_idx = 0
    last_idx = len(frames) - 1
    for eid, cl in enumerate(clusters, start=1):
        center_first, center_last = cl[0], cl[-1]
        start = max(first_idx, center_first - window_before)
        end = min(last_idx, center_last + window_after)

        f_start, f_end = frames[start], frames[end]

        # 帧优（P1 视角）与接触类型：取事件帧上的读数
        fav = None
        contact = ContactResult.NONE
        for i in cl:
            if frames[i].frame_advantage is not None:
                fav = frames[i].frame_advantage
            if frames[i].contact != ContactResult.NONE:
                contact = frames[i].contact

        # 攻击方（出招方）判定：优先 action，否则用帧优符号（负 = 出招方不利）
        attacker = None
        attacker_action = None
        for i in cl:
            if frames[i].p2_action:
                attacker, attacker_action = 2, frames[i].p2_action
                break
            if frames[i].p1_action:
                attacker, attacker_action = 1, frames[i].p1_action
                break
        if attacker is None and fav is not None:
            attacker = 1 if fav < 0 else 2
        if attacker is None:
            attacker = 1  # 兜底

        attacker_advantage = None
        if fav is not None:
            attacker_advantage = fav if attacker == 1 else -fav

        p1_dmg = round(max(0.0, f_start.p1_health - f_end.p1_health), 1)
        p2_dmg = round(max(0.0, f_start.p2_health - f_end.p2_health), 1)

        exchanges.append(Exchange(
            exchange_id=eid,
            round_number=f_start.round_number,
            start_frame=f_start.frame_index,
            end_frame=f_end.frame_index,
            start_time=f_start.timestamp,
            end_time=f_end.timestamp,
            attacker=attacker,
            attacker_action=attacker_action,
            attacker_advantage=attacker_advantage,
            contact=contact,
            p1_damage_taken=p1_dmg,
            p2_damage_taken=p2_dmg,
        ))
    return exchanges
