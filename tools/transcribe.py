"""B 站教学视频音频转文字（faster-whisper）。

用法：python tools/transcribe.py <音频文件> [模型]
模型：tiny/base/small/medium（默认 small，中文够用）
输出：同目录 transcript.txt
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")


def main():
    audio = sys.argv[1] if len(sys.argv) > 1 else "tools/tmp/audio.wav"
    model_size = sys.argv[2] if len(sys.argv) > 2 else "small"

    from faster_whisper import WhisperModel

    print(f"加载模型 {model_size}（首次会自动下载）…")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    # 用 wave+numpy 直接读 wav，绕过 PyAV 解码的版本兼容问题
    import wave
    import numpy as np

    with wave.open(audio, "rb") as w:
        sr = w.getframerate()
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        samples = samples.astype(np.float32) / 32768.0
    print(f"音频采样率 {sr}Hz，长度 {len(samples)/sr:.1f}s，开始转写…")
    segments, info = model.transcribe(samples, language="zh", vad_filter=True)

    lines = []
    for seg in segments:
        line = f"[{seg.start:7.1f}-{seg.end:7.1f}] {seg.text.strip()}"
        lines.append(line)
        print(line, flush=True)

    out = os.path.splitext(audio)[0] + "_transcript.txt"
    with open(out, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))
    print(f"\n完成：{len(lines)} 段，已保存 {out}")


if __name__ == "__main__":
    main()
