"""CLI 入口。

用法：
  # 用样例轨迹演示（无需视频）
  python -m sf6_agent.main demo --out report_demo.html

  # 分析真实录像
  python -m sf6_agent.main analyze --video path/to/match.mp4 \
      --p1 Ryu --p2 Ken --data sf6_agent/data --out report.html
"""
from __future__ import annotations

import argparse
from pathlib import Path

from .demo import run_demo
from .pipeline import analyze_video


def _default_data() -> str:
    return str(Path(__file__).parent / "data")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="sf6-agent", description="SF6 街霸录像分析 agent")
    sub = ap.add_subparsers(dest="cmd")

    d = sub.add_parser("demo", help="用样例轨迹演示全流程")
    d.add_argument("--out", default="report_demo.html")
    d.add_argument("--data", default=_default_data())

    a = sub.add_parser("analyze", help="分析真实录像")
    a.add_argument("--video", required=True, help="录像文件路径")
    a.add_argument("--p1", required=True, help="P1 角色名（对应帧数据表文件名）")
    a.add_argument("--p2", required=True, help="P2 角色名")
    a.add_argument("--data", default=_default_data(), help="帧数据表目录")
    a.add_argument("--out", default="report.html")
    a.add_argument("--fps", type=int, default=60)
    a.add_argument("--provider", default="sf6", choices=["sf6", "heuristic", "llm", "mock"],
                   help="画面识别方式：sf6(训练模式CV) / heuristic(通用CV) / llm(视觉大模型)")
    a.add_argument("--keep-frames", default=None, help="保留抽帧目录以便调试")

    args = ap.parse_args(argv)
    if args.cmd == "demo":
        ex, findings = run_demo(args.out, args.data)
        _print_summary(ex, findings, args.out)
    elif args.cmd == "analyze":
        provider = _make_provider(args.provider)
        ex, findings = analyze_video(
            args.video, args.out, args.p1, args.p2, args.data,
            fps=args.fps, provider=provider, keep_frames_dir=args.keep_frames,
        )
        _print_summary(ex, findings, args.out)
    else:
        ap.print_help()


def _make_provider(name):
    from .vision import HeuristicVisionProvider, LLMVisionProvider, SF6TrainingVisionProvider

    if name == "sf6":
        return SF6TrainingVisionProvider(use_ocr=False)
    if name == "heuristic":
        return HeuristicVisionProvider()
    if name == "llm":
        return LLMVisionProvider()
    return None


def _print_summary(exchanges, findings, out):
    print(f"交手波次: {len(exchanges)} 个，分析结论: {len(findings)} 条")
    for f in findings:
        print(f"  [{f.severity.value}] {f.title}")
    print(f"报告已生成: {out}")


if __name__ == "__main__":
    main()
