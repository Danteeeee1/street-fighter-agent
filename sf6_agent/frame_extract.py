"""视频抽帧。

用 ffmpeg 按固定 fps（SF6 为 60）抽帧，帧号与时间戳一一对应：
    frame_index 从 1 开始，timestamp = (frame_index - 1) / fps
"""
from __future__ import annotations

import subprocess
from pathlib import Path
from typing import List, Optional


def extract_frames(
    video_path: str,
    out_dir: str,
    fps: int = 60,
    start: Optional[float] = None,
    duration: Optional[float] = None,
) -> List[Path]:
    """抽帧，返回按帧号升序的图片路径列表。"""
    video = Path(video_path)
    if not video.exists():
        raise FileNotFoundError(f"找不到录像文件: {video_path}")
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)

    cmd = ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error"]
    if start is not None:
        cmd += ["-ss", str(start)]
    cmd += ["-i", str(video)]
    if duration is not None:
        cmd += ["-t", str(duration)]
    cmd += ["-vf", f"fps={fps}", "-qscale:v", "2", str(out / "frame_%06d.jpg")]

    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg 抽帧失败: {proc.stderr.strip()[:800]}")

    frames = sorted(out.glob("frame_*.jpg"))
    if not frames:
        raise RuntimeError("未抽到任何帧，请检查视频路径、时长与 ffmpeg 是否可用")
    return frames


def frame_number(path: Path) -> int:
    """从文件名 frame_000123.jpg 解析帧号（1 起）。"""
    return int(path.stem.split("_")[-1])


def frame_timestamp(frame_index: int, fps: int = 60) -> float:
    """帧号 -> 秒。"""
    return (frame_index - 1) / fps
