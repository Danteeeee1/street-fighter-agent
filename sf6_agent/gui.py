"""SF6 街霸录像分析 agent —— tkinter 本地图形界面。

运行：python -m sf6_agent.gui

功能：选录像 → 配角色（中文名下拉）→ 开始分析 → 实时进度 → 结论摘要 → 打开报告。
"""
from __future__ import annotations

import json
import os
import threading
import webbrowser
from pathlib import Path

from .frame_data import FrameDataLibrary
from .pipeline import analyze_sf6_video

_BASE = Path(__file__).parent
_OUTPUT = _BASE / "output"
_OUTPUT.mkdir(exist_ok=True)
_CONFIG = _OUTPUT / "gui_config.json"

_STAGE_LABELS = {
    "prepare": "准备中",
    "health": "读取血条",
    "events": "检测交手事件",
    "advantage": "读取帧优（LLM）",
    "analyze": "生成报告",
    "done": "完成",
}
_SEV_LABELS = {"high": "高", "medium": "中", "low": "低"}


class SF6AnalyzerApp:
    def __init__(self, root):
        self.root = root
        self.root.title("街霸6 录像分析 Agent")
        self.root.geometry("740x680")
        self.root.minsize(660, 600)

        self._char_map = {}  # 显示名 -> 英文名
        self._last_report = None

        self.video_var = None
        self.data_dir_var = None
        self.p1_var = None
        self.p2_var = None
        self.api_key_var = None
        self.fps_var = None
        self.diff_var = None
        self.drop_var = None
        self.duration_var = None
        self.p1_combo = None
        self.p2_combo = None
        self.start_btn = None
        self.open_btn = None
        self.progress = None
        self.stage_lbl = None
        self.count_lbl = None
        self.char_count_lbl = None
        self.log_text = None

        self._build_ui()
        self._load_defaults()

    # ---------- UI ----------
    def _build_ui(self):
        import tkinter as tk
        from tkinter import ttk, scrolledtext

        self.tk = tk
        self.ttk = ttk

        root = self.root
        root.columnconfigure(0, weight=1)

        header = ttk.Frame(root)
        header.grid(row=0, column=0, sticky="ew", padx=14, pady=(12, 2))
        ttk.Label(header, text="🎮 街霸6 录像分析 Agent",
                  font=("Microsoft YaHei UI", 15, "bold")).pack(anchor="w")
        ttk.Label(header, text="确反 / 立回失误 · 机会点 · 场景解法 · 交互式报告",
                  foreground="#6b7280").pack(anchor="w")

        form = ttk.Frame(root)
        form.grid(row=1, column=0, sticky="ew", padx=14, pady=8)
        form.columnconfigure(1, weight=1)

        # 录像文件
        r = 0
        ttk.Label(form, text="录像文件").grid(row=r, column=0, sticky="w", pady=6)
        self.video_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.video_var).grid(row=r, column=1, sticky="ew", pady=6, padx=6)
        ttk.Button(form, text="浏览…", command=self._browse_video).grid(row=r, column=2, pady=6)
        r += 1

        # 角色
        ttk.Label(form, text="P1 / P2").grid(row=r, column=0, sticky="w", pady=6)
        role_row = ttk.Frame(form)
        role_row.grid(row=r, column=1, columnspan=2, sticky="ew", pady=6, padx=6)
        role_row.columnconfigure(0, weight=1)
        role_row.columnconfigure(1, weight=1)
        self.p1_var = tk.StringVar()
        self.p2_var = tk.StringVar()
        self.p1_combo = ttk.Combobox(role_row, textvariable=self.p1_var, state="readonly")
        self.p2_combo = ttk.Combobox(role_row, textvariable=self.p2_var, state="readonly")
        self.p1_combo.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self.p2_combo.grid(row=0, column=1, sticky="ew", padx=(5, 0))
        r += 1

        # 帧数据目录 + 刷新
        ttk.Label(form, text="帧数据目录").grid(row=r, column=0, sticky="w", pady=6)
        self.data_dir_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.data_dir_var).grid(row=r, column=1, sticky="ew", pady=6, padx=6)
        dir_row = ttk.Frame(form)
        dir_row.grid(row=r, column=2, pady=6)
        ttk.Button(dir_row, text="浏览…", command=self._browse_data_dir).pack(side="left")
        ttk.Button(dir_row, text="刷新", command=self._reload_characters).pack(side="left", padx=(4, 0))
        r += 1
        self.char_count_lbl = ttk.Label(form, text="", foreground="#9ca3af", font=("", 8))
        self.char_count_lbl.grid(row=r, column=1, sticky="w", padx=6)
        r += 1

        # API key
        ttk.Label(form, text="API Key").grid(row=r, column=0, sticky="w", pady=6)
        self.api_key_var = tk.StringVar()
        ttk.Entry(form, textvariable=self.api_key_var, show="•").grid(
            row=r, column=1, columnspan=2, sticky="ew", pady=6, padx=6)
        r += 1

        # 高级参数
        adv = ttk.LabelFrame(form, text=" 高级参数 ")
        adv.grid(row=r, column=0, columnspan=3, sticky="ew", pady=8)
        adv.columnconfigure((0, 1, 2, 3), weight=1)
        self.fps_var = tk.StringVar(value="15")
        self.diff_var = tk.StringVar(value="20")
        self.drop_var = tk.StringVar(value="5")
        self.duration_var = tk.StringVar(value="")
        self._param(adv, 0, "采样 fps", self.fps_var)
        self._param(adv, 1, "帧差分阈值", self.diff_var)
        self._param(adv, 2, "掉血阈值", self.drop_var)
        self._param(adv, 3, "只分析前N秒", self.duration_var)
        r += 1

        # 开始按钮
        self.start_btn = ttk.Button(root, text="🚀 开始分析", command=self._start)
        self.start_btn.grid(row=2, column=0, sticky="ew", padx=14, pady=(2, 8))

        # 进度
        prog = ttk.Frame(root)
        prog.grid(row=3, column=0, sticky="ew", padx=14)
        prog.columnconfigure(0, weight=1)
        self.progress = ttk.Progressbar(prog, mode="determinate", maximum=100)
        self.progress.grid(row=0, column=0, sticky="ew")
        status_row = ttk.Frame(prog)
        status_row.grid(row=1, column=0, sticky="ew", pady=(4, 0))
        status_row.columnconfigure(0, weight=1)
        self.stage_lbl = ttk.Label(status_row, text="就绪", foreground="#6b7280")
        self.stage_lbl.grid(row=0, column=0, sticky="w")
        self.count_lbl = ttk.Label(status_row, text="", foreground="#9ca3af")
        self.count_lbl.grid(row=0, column=1, sticky="e")

        # 日志
        log_frame = ttk.LabelFrame(root, text=" 日志 ")
        log_frame.grid(row=4, column=0, sticky="nsew", padx=14, pady=8)
        root.rowconfigure(4, weight=1)
        log_frame.columnconfigure(0, weight=1)
        log_frame.rowconfigure(0, weight=1)
        self.log_text = scrolledtext.ScrolledText(
            log_frame, height=10, state="disabled", font=("Consolas", 9))
        self.log_text.grid(row=0, column=0, sticky="nsew", padx=4, pady=4)

        # 底部
        bottom = ttk.Frame(root)
        bottom.grid(row=5, column=0, sticky="ew", padx=14, pady=(0, 12))
        self.open_btn = ttk.Button(bottom, text="查看最近报告", command=self._open_report,
                                   state="disabled")
        self.open_btn.pack(side="right")

    def _param(self, parent, col, label, var):
        self.ttk.Label(parent, text=label, foreground="#6b7280").grid(
            row=0, column=col, sticky="w", padx=6, pady=(2, 0))
        self.ttk.Entry(parent, textvariable=var, width=10).grid(
            row=1, column=col, sticky="ew", padx=6, pady=(0, 6))

    # ---------- 默认值 / 配置 ----------
    def _load_defaults(self):
        cfg = {}
        if _CONFIG.exists():
            try:
                cfg = json.loads(_CONFIG.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                cfg = {}

        self.data_dir_var.set(cfg.get("data_dir", str(_BASE / "data")))
        self.video_var.set(cfg.get("video", ""))
        self.api_key_var.set(cfg.get("api_key", os.getenv("OPENAI_API_KEY", "")))
        self.fps_var.set(str(cfg.get("fps", 15)))
        self.diff_var.set(str(cfg.get("diff", 20)))
        self.drop_var.set(str(cfg.get("drop", 5)))
        self.duration_var.set(str(cfg.get("duration", "")))

        self._reload_characters()
        # 恢复上次选择的角色
        if cfg.get("p1"):
            self._set_combo_by_en(self.p1_combo, cfg["p1"])
        if cfg.get("p2"):
            self._set_combo_by_en(self.p2_combo, cfg["p2"])

    def _reload_characters(self):
        data_dir = self.data_dir_var.get().strip() or str(_BASE / "data")
        lib = FrameDataLibrary.load_dir(data_dir)
        items = []
        self._char_map = {}
        for en in sorted(lib.characters.keys()):
            cfd = lib.characters[en]
            label = f"{cfd.cn} ({en})" if cfd.cn and cfd.cn != en else en
            items.append(label)
            self._char_map[label] = en
        for combo, default_en in ((self.p1_combo, "Ryu"), (self.p2_combo, "Ken")):
            combo["values"] = items
            self._set_combo_by_en(combo, default_en)
        if self.char_count_lbl:
            self.char_count_lbl.config(text=f"已加载 {len(items)} 个角色")

    def _set_combo_by_en(self, combo, en):
        for label, _en in self._char_map.items():
            if _en == en:
                combo.set(label)
                return
        if combo["values"]:
            combo.set(combo["values"][0])

    def _resolve_char(self, display):
        return self._char_map.get(display, display)

    def _save_config(self):
        try:
            _CONFIG.write_text(json.dumps({
                "video": self.video_var.get().strip(),
                "data_dir": self.data_dir_var.get().strip(),
                "p1": self._resolve_char(self.p1_var.get()),
                "p2": self._resolve_char(self.p2_var.get()),
                "api_key": self.api_key_var.get().strip(),
                "fps": self.fps_var.get(),
                "diff": self.diff_var.get(),
                "drop": self.drop_var.get(),
                "duration": self.duration_var.get(),
            }, ensure_ascii=False, indent=2), encoding="utf-8")
        except Exception:  # noqa: BLE001
            pass

    # ---------- 事件 ----------
    def _browse_video(self):
        from tkinter import filedialog

        p = filedialog.askopenfilename(
            title="选择录像文件",
            filetypes=[("视频文件", "*.mp4 *.mkv *.avi *.mov *.webm"), ("所有文件", "*.*")])
        if p:
            self.video_var.set(p)

    def _browse_data_dir(self):
        from tkinter import filedialog

        p = filedialog.askdirectory(title="选择帧数据表目录")
        if p:
            self.data_dir_var.set(p)
            self._reload_characters()

    def _start(self):
        video = self.video_var.get().strip()
        if not video or not Path(video).exists():
            self._log("✗ 录像文件不存在：%s" % video)
            self.stage_lbl.config(text="录像文件不存在")
            return
        p1 = self._resolve_char(self.p1_var.get().strip()) or "P1"
        p2 = self._resolve_char(self.p2_var.get().strip()) or "P2"

        # API key 校验
        api_key = self.api_key_var.get().strip()
        if api_key:
            if not api_key.startswith("sk-"):
                self._log("✗ API Key 格式错误（应以 sk- 开头）：%s…" % api_key[:12])
                self.stage_lbl.config(text="API Key 格式错误")
                return
            os.environ["OPENAI_API_KEY"] = api_key
        elif not os.getenv("OPENAI_API_KEY"):
            self._log("✗ 未填写 API Key（用于读取帧优，DeepSeek 密钥 sk- 开头）")
            self._log("  请在「API Key」输入框填入密钥后重试")
            self.stage_lbl.config(text="请先填写 API Key")
            return

        try:
            fps = int(self.fps_var.get() or 15)
            diff = float(self.diff_var.get() or 20)
            drop = float(self.drop_var.get() or 5)
            duration = float(self.duration_var.get()) if self.duration_var.get().strip() else None
        except ValueError:
            self._log("✗ 高级参数格式错误，请检查数值")
            return
        if not (5 <= fps <= 30):
            self._log("⚠ 采样 fps=%d 异常，已自动改回 15" % fps)
            self.fps_var.set("15")
            fps = 15

        self._save_config()
        self.start_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self.progress["value"] = 0
        self._clear_log()
        self._log("▶ 开始分析：%s vs %s" % (p1, p2))
        self._log("  录像：%s" % video)

        report_path = str(_OUTPUT / "report_latest.html")

        def _run():
            try:
                result = analyze_sf6_video(
                    video, report_path, p1, p2, self.data_dir_var.get().strip(),
                    fps=fps, diff_threshold=diff, min_drop=drop, duration=duration,
                    progress=False, progress_callback=self._on_progress,
                )
                self.root.after(0, lambda: self._on_done(report_path, result))
            except Exception as e:  # noqa: BLE001
                self.root.after(0, lambda: self._on_error(str(e)))

        threading.Thread(target=_run, daemon=True).start()

    def _on_progress(self, stage, done, total, message):
        def update():
            label = _STAGE_LABELS.get(stage, stage)
            weights = {"prepare": 2, "health": 8, "events": 12,
                       "advantage": 88, "analyze": 97, "done": 100}
            base = weights.get(stage, 0)
            if stage == "advantage" and total > 0:
                pct = base + done / total * (weights["analyze"] - base)
            else:
                pct = 100 if stage == "done" else base
            self.progress["value"] = min(100, pct)
            self.stage_lbl.config(text=message or label)
            self.count_lbl.config(text=f"{done}/{total}" if total > 1 else "")
            self._log("▸ " + (message or label))

        self.root.after(0, update)

    def _on_done(self, report_path, result):
        exchanges, findings = result
        self._last_report = report_path
        self.progress["value"] = 100
        self.stage_lbl.config(text="分析完成 ✓")
        self.count_lbl.config(text="")
        self.start_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self._log("✓ 分析完成：%d 个波次，%d 条结论" % (len(exchanges), len(findings)))
        for f in findings:
            self._log("  [%s] %s" % (_SEV_LABELS.get(f.severity.value, "?"), f.title))
        if not findings:
            self._log("  （未识别到确反/立回失误，可能原因：")
            self._log("   1. 录像非训练模式，底部无帧数据条「硬直差」显示；")
            self._log("   2. 录像分辨率/布局与标定不一致，帧优读取失败；")
            self._log("   3. 采样 fps 过低导致事件漏检。）")
        self._log("  报告：%s" % report_path)
        webbrowser.open("file://" + report_path)

    def _on_error(self, msg):
        self.start_btn.config(state="normal")
        self.stage_lbl.config(text="分析失败")
        self._log("✗ 分析失败：%s" % msg)

    def _open_report(self):
        if self._last_report and Path(self._last_report).exists():
            webbrowser.open("file://" + self._last_report)
        else:
            self.stage_lbl.config(text="暂无报告")

    def _log(self, msg):
        self.log_text.config(state="normal")
        self.log_text.insert("end", msg + "\n")
        self.log_text.see("end")
        self.log_text.config(state="disabled")

    def _clear_log(self):
        self.log_text.config(state="normal")
        self.log_text.delete("1.0", "end")
        self.log_text.config(state="disabled")


def main():
    import tkinter as tk
    from tkinter import ttk

    root = tk.Tk()
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except Exception:  # noqa: BLE001
        pass
    SF6AnalyzerApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
