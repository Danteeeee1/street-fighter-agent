"""流水线编排：抽帧 -> 画面识别 -> 波次切分 -> 分析 -> 报告。"""
from __future__ import annotations

import tempfile
from pathlib import Path
from typing import List, Optional, Tuple

from .analyzer import Analyzer
from .event_detect import pick_event_frames, segment_exchanges
from .frame_data import FrameDataLibrary
from .frame_extract import extract_frames, frame_number, frame_timestamp
from .models import Exchange, Finding
from .report import generate_report
from .vision import LLMVisionProvider, SF6TrainingVisionProvider, VisionProvider


def analyze_video(
    video_path: str,
    out_report: str,
    p1_char: str,
    p2_char: str,
    data_dir: str,
    fps: int = 60,
    provider: Optional[VisionProvider] = None,
    keep_frames_dir: Optional[str] = None,
) -> Tuple[List[Exchange], List[Finding]]:
    """分析一段录像，输出交互式网页报告。"""
    frames_dir = keep_frames_dir or tempfile.mkdtemp(prefix="sf6_frames_")
    frame_paths = extract_frames(video_path, frames_dir, fps=fps)

    provider = provider or SF6TrainingVisionProvider()
    frames = []
    for p in frame_paths:
        idx = frame_number(p)
        frames.append(provider.read(str(p), idx, frame_timestamp(idx, fps)))

    return _analyze_and_report(frames, out_report, p1_char, p2_char, data_dir, fps)


def analyze_sf6_video(
    video_path: str,
    out_report: str,
    p1_char: str,
    p2_char: str,
    data_dir: str,
    fps: int = 15,
    llm_provider: Optional[VisionProvider] = None,
    diff_threshold: float = 20.0,
    min_drop: float = 5.0,
    max_llm_calls: Optional[int] = None,
    duration: Optional[float] = None,
    keep_frames_dir: Optional[str] = None,
    progress: bool = True,
    progress_callback=None,
) -> Tuple[List[Exchange], List[Finding]]:
    """SF6 训练模式录像分析（混合：本地 CV 血条 + LLM 帧优）。

    流程：
      1) 按 fps 抽帧；2) 本地 CV 逐帧读血条（快）；
      3) 帧差分 + 血条突变检测「交手事件帧」；
      4) 仅对事件帧调用 LLM 读帧优（裁剪帧数据条，约 2s/帧）；
      5) 切分波次 + 分析 + 生成报告。

    duration: 只分析前 N 秒（用于调试/验证）。
    progress_callback(stage, done, total, message):
      阶段 stage ∈ {prepare, health, events, advantage, analyze, done}，
      done/total 为当前阶段进度，message 为描述文本。
    """

    def _report(stage, done, total, message=""):
        if progress_callback:
            try:
                progress_callback(stage, done, total, message)
            except Exception:  # noqa: BLE001
                pass
        if progress and message:
            print(message)

    _report("prepare", 0, 1, "正在抽帧…")
    frames_dir = keep_frames_dir or tempfile.mkdtemp(prefix="sf6_frames_")
    frame_paths = extract_frames(video_path, frames_dir, fps=fps, duration=duration)

    _report("health", 0, len(frame_paths), f"读取血条 0/{len(frame_paths)}")
    cv = SF6TrainingVisionProvider()
    frames = []
    for n, p in enumerate(frame_paths, start=1):
        idx = frame_number(p)
        frames.append(cv.read(str(p), idx, frame_timestamp(idx, fps)))
        if n % 100 == 0 or n == len(frame_paths):
            _report("health", n, len(frame_paths), f"读取血条 {n}/{len(frame_paths)}")

    # 事件帧检测（画面剧变 + 血条突变）
    _report("events", 0, 1, "检测交手事件帧…")
    event_idxs = pick_event_frames(
        [str(p) for p in frame_paths], frames, diff_threshold, min_drop
    )
    if max_llm_calls is not None:
        event_idxs = event_idxs[:max_llm_calls]
    _report("events", 1, 1, f"检测到 {len(event_idxs)} 个交手事件帧")

    # LLM 读帧优
    llm = llm_provider or LLMVisionProvider()
    for n, i in enumerate(event_idxs, start=1):
        _report("advantage", n - 1, len(event_idxs), f"读取帧优 {n}/{len(event_idxs)}")
        fs = frames[i]
        try:
            adv_fs = llm.read(str(frame_paths[i]), fs.frame_index, fs.timestamp)
            fs.frame_advantage = adv_fs.frame_advantage
        except Exception as e:  # noqa: BLE001
            if progress:
                print(f"  [warn] 事件帧 {i} 帧优读取失败: {e}")
    _report("advantage", len(event_idxs), len(event_idxs), "帧优读取完成")

    _report("analyze", 0, 1, "切分波次并生成分析结论…")
    result = _analyze_and_report(frames, out_report, p1_char, p2_char, data_dir, fps,
                                 title=f"{p1_char} vs {p2_char} 录像分析")
    _report("done", 1, 1, f"分析完成：{len(result[0])} 个波次，{len(result[1])} 条结论")
    return result


def analyze_frames(
    frames,
    out_report: str,
    p1_char: str,
    p2_char: str,
    data_dir: str,
    fps: int = 60,
    title: str = "SF6 录像分析报告",
    game: str = "Street Fighter 6",
) -> Tuple[List[Exchange], List[Finding]]:
    """直接对已有的 FrameState 列表做分析（供自定义 VisionProvider 使用）。"""
    return _analyze_and_report(frames, out_report, p1_char, p2_char, data_dir, fps,
                               title=title, game=game)


def _analyze_and_report(frames, out_report, p1_char, p2_char, data_dir, fps,
                        title="SF6 录像分析报告", game="Street Fighter 6"):
    lib = FrameDataLibrary.load_dir(data_dir)
    exchanges = segment_exchanges(frames)
    analyzer = Analyzer(lib, p1_char, p2_char)
    findings = analyzer.analyze(exchanges)

    rounds = max((f.round_number for f in frames), default=1)
    match = {
        "title": title,
        "game": game,
        "p1_char": p1_char,
        "p2_char": p2_char,
        "rounds": rounds,
        "total_frames": len(frames),
        "duration": round((len(frames) - 1) / fps, 2) if frames else 0,
        "fps": fps,
    }
    generate_report(match, exchanges, findings, out_report)
    return exchanges, findings
