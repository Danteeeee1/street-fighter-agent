"""SF6 真实录像分析入口。

用法：
  python real_analyze.py --dry-run            # 只抽帧+血条+事件检测，不调LLM
  python real_analyze.py --limit 20           # 只分析前20秒
  python real_analyze.py --max-calls 30       # 最多调30次LLM读帧优
"""
import argparse
import os
import sys
import time

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(_HERE))

VIDEO = r"D:/videos/Street Fighter 6/Street Fighter 6 2026.11.13 - 11.34.58.02.mp4"
DATA_DIR = os.path.join(os.path.dirname(_HERE), "sf6_agent", "data")


def dry_run(fps=15, limit=None, diff_threshold=6.0):
    from sf6_agent.frame_extract import extract_frames, frame_number, frame_timestamp
    from sf6_agent.vision import SF6TrainingVisionProvider
    from sf6_agent.event_detect import detect_frame_changes, detect_health_drops, cluster_indices

    import tempfile
    frames_dir = tempfile.mkdtemp(prefix="sf6_diag_")
    paths = extract_frames(VIDEO, frames_dir, fps=fps, duration=limit)
    cv = SF6TrainingVisionProvider()
    frames = []
    for p in paths:
        idx = frame_number(p)
        frames.append(cv.read(str(p), idx, frame_timestamp(idx, fps)))

    diffs = detect_frame_changes([str(p) for p in paths], diff_threshold)
    drops = detect_health_drops(frames)
    print(f"抽帧 {len(paths)} 张 (fps={fps}, limit={limit}s)")
    print(f"帧差分事件(阈值{diff_threshold}): {len(diffs)} 帧")
    print(f"血条突变事件: {len(drops)} 帧")
    print(f"合并后事件簇: {len(cluster_indices(sorted(set(diffs+drops)), 6))} 个")
    return frames, paths, diffs, drops


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--limit", type=float, default=None)
    ap.add_argument("--max-calls", type=int, default=None)
    ap.add_argument("--fps", type=int, default=15)
    ap.add_argument("--diff", type=float, default=20.0)
    ap.add_argument("--drop", type=float, default=5.0)
    ap.add_argument("--out", default=os.path.join(_HERE, "report_real.html"))
    args = ap.parse_args()

    if args.dry_run:
        dry_run(args.fps, args.limit, args.diff)
    else:
        from sf6_agent.pipeline import analyze_sf6_video
        t0 = time.time()
        ex, findings = analyze_sf6_video(
            VIDEO, args.out, "Ryu", "Ken", DATA_DIR,
            fps=args.fps, diff_threshold=args.diff, min_drop=args.drop,
            max_llm_calls=args.max_calls, duration=args.limit,
        )
        print(f"\n完成，耗时 {time.time()-t0:.0f}s")
        print(f"交手波次 {len(ex)} 个，结论 {len(findings)} 条")
        for f in findings:
            print(f"  [{f.severity.value}] {f.title}")
        print(f"报告: {args.out}")
