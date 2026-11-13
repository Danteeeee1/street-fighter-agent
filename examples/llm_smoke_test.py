"""LLM 画面理解冒烟测试。

用已抽的 8 帧样本，验证 DeepSeek 视觉模型能否正确读出帧优（硬直差）、
接触类型、血量。对照参考：t_30s 帧已知为 P1 硬直差 -1 / P2 硬直差 +1。
"""
import glob
import os
import re
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

from sf6_agent.vision import LLMVisionProvider


def main():
    provider = LLMVisionProvider()
    if provider._client is None:
        print("未配置 API key：请设置环境变量 OPENAI_API_KEY")
        print("  Windows PowerShell:  $env:OPENAI_API_KEY='sk-xxx'")
        print("  Windows CMD:         set OPENAI_API_KEY=sk-xxx")
        sys.exit(1)

    frames = sorted(glob.glob(os.path.join(_HERE, "frames", "t_*.png")))
    print(f"共 {len(frames)} 帧，模型 {provider.model}\n")
    for f in frames:
        t = int(re.search(r"t_(\d+)s", f).group(1))
        fs = provider.read(f, t * 60, t)
        print(f"{t:>3}s | 帧优(P1)={str(fs.frame_advantage):>5}")


if __name__ == "__main__":
    main()
