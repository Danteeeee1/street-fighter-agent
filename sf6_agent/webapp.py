"""SF6 街霸录像分析 agent —— 本地 Web 图形界面。

启动后浏览器打开 http://127.0.0.1:8765 ，即可：
选录像 → 配角色 → 开始分析 → 实时看进度 → 预览报告。

运行：python -m sf6_agent.webapp
"""
from __future__ import annotations

import json
import threading
import uuid
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request, send_file

from .frame_data import FrameDataLibrary
from .pipeline import analyze_sf6_video

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 4 * 1024 * 1024 * 1024  # 4GB

_BASE = Path(__file__).parent
_OUTPUT = _BASE / "output"
_OUTPUT.mkdir(exist_ok=True)

# task_id -> {status, stage, done, total, message, report_path, error, p1, p2}
_tasks: dict = {}
_lock = threading.Lock()


def _list_characters(data_dir: str) -> list:
    lib = FrameDataLibrary.load_dir(data_dir)
    return sorted(lib.characters.keys())


@app.route("/")
def index():
    return render_template_string(INDEX_HTML)


@app.route("/api/characters")
def api_characters():
    data_dir = request.args.get("dir") or str(_BASE / "data")
    return jsonify({"characters": _list_characters(data_dir),
                    "default_dir": str(_BASE / "data")})


@app.route("/api/analyze", methods=["POST"])
def api_analyze():
    import os

    data = request.get_json(force=True)
    video = (data.get("video") or "").strip()
    if not video or not Path(video).exists():
        return jsonify({"error": f"录像文件不存在：{video}"}), 400

    task_id = uuid.uuid4().hex[:12]
    with _lock:
        _tasks[task_id] = {
            "status": "running", "stage": "prepare", "done": 0, "total": 1,
            "message": "准备中…", "report_path": None, "error": None,
            "p1": data.get("p1", "P1"), "p2": data.get("p2", "P2"),
        }

    out_report = str(_OUTPUT / f"{task_id}.html")
    api_key = (data.get("api_key") or "").strip()

    def _run():
        def cb(stage, done, total, message):
            with _lock:
                t = _tasks.get(task_id)
                if t:
                    t.update(stage=stage, done=done, total=total, message=message)

        if api_key:
            os.environ["OPENAI_API_KEY"] = api_key
        try:
            analyze_sf6_video(
                video, out_report,
                data.get("p1", "Ryu"), data.get("p2", "Ken"),
                data.get("data_dir", str(_BASE / "data")),
                fps=int(data.get("fps", 15)),
                diff_threshold=float(data.get("diff", 20.0)),
                min_drop=float(data.get("drop", 5.0)),
                duration=data.get("duration") or None,
                progress=False,
                progress_callback=cb,
            )
            with _lock:
                t = _tasks[task_id]
                t.update(status="done", stage="done", message="分析完成", report_path=out_report)
        except Exception as e:  # noqa: BLE001
            with _lock:
                t = _tasks[task_id]
                t.update(status="error", error=str(e), message=f"分析失败：{e}")

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"task_id": task_id})


@app.route("/api/status/<task_id>")
def api_status(task_id):
    with _lock:
        t = _tasks.get(task_id)
    if not t:
        return jsonify({"error": "任务不存在"}), 404
    return jsonify(t)


@app.route("/api/report/<task_id>")
def api_report(task_id):
    with _lock:
        t = _tasks.get(task_id)
    if not t or not t.get("report_path"):
        return "报告尚未生成", 404
    return send_file(t["report_path"], mimetype="text/html")


@app.route("/api/tasks")
def api_tasks():
    with _lock:
        return jsonify(list(_tasks.values()))


def main():
    import os

    print("=" * 56)
    print("  街霸6 录像分析 Agent · 图形界面")
    print("  浏览器打开  http://127.0.0.1:8765")
    print("=" * 56)
    if not os.getenv("OPENAI_API_KEY"):
        print("  [提示] 未检测到 OPENAI_API_KEY，可在界面里填写 DeepSeek key")
    app.run(host="127.0.0.1", port=8765, debug=False, threaded=True)


INDEX_HTML = r"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>街霸6 录像分析 Agent</title>
<style>
  :root {
    --bg: #f4f5f7; --card: #fff; --line: #e5e7eb; --text: #1f2937;
    --muted: #6b7280; --accent: #e5484d; --accent2: #b91c1c; --ok: #10b981;
  }
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
    background: var(--bg); color: var(--text); min-height: 100vh;
  }
  header {
    background: linear-gradient(135deg, #1f2937, #374151); color: #fff;
    padding: 20px 28px; display: flex; align-items: center; gap: 12px;
  }
  header .logo { font-size: 26px; }
  header h1 { font-size: 20px; font-weight: 700; }
  header .sub { color: #cbd5e1; font-size: 13px; }
  .wrap { max-width: 1240px; margin: 0 auto; padding: 24px 20px 60px; display: grid;
          grid-template-columns: 360px 1fr; gap: 20px; align-items: start; }
  @media (max-width: 900px) { .wrap { grid-template-columns: 1fr; } }

  .panel { background: var(--card); border: 1px solid var(--line); border-radius: 14px;
           padding: 20px; box-shadow: 0 1px 2px rgba(0,0,0,.04); }
  .panel h2 { font-size: 15px; margin-bottom: 16px; display: flex; align-items: center; gap: 8px; }
  .panel h2 .num { background: var(--accent); color: #fff; width: 22px; height: 22px;
                   border-radius: 50%; display: inline-flex; align-items: center;
                   justify-content: center; font-size: 13px; }

  .field { margin-bottom: 14px; }
  .field label { display: block; font-size: 13px; color: var(--muted); margin-bottom: 5px; font-weight: 600; }
  .field input, .field select {
    width: 100%; padding: 9px 11px; border: 1px solid var(--line); border-radius: 8px;
    font-size: 14px; font-family: inherit; background: #fff; color: var(--text);
    transition: border-color .15s, box-shadow .15s;
  }
  .field input:focus, .field select:focus {
    outline: none; border-color: var(--accent); box-shadow: 0 0 0 3px rgba(229,72,77,.12);
  }
  .field .hint { font-size: 11px; color: #9ca3af; margin-top: 3px; }
  .row2 { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; }
  .row3 { display: grid; grid-template-columns: 1fr 1fr 1fr; gap: 12px; }
  details.adv { margin: 6px 0 14px; border: 1px solid var(--line); border-radius: 8px; padding: 8px 12px; }
  details.adv summary { cursor: pointer; font-size: 13px; color: var(--muted); font-weight: 600; }

  .btn {
    width: 100%; padding: 12px; border: none; border-radius: 10px; font-size: 15px;
    font-weight: 700; cursor: pointer; color: #fff; background: linear-gradient(135deg, #e5484d, #c53030);
    transition: transform .1s, opacity .15s;
  }
  .btn:hover { transform: translateY(-1px); }
  .btn:disabled { opacity: .5; cursor: not-allowed; transform: none; }

  .progress { margin-top: 18px; display: none; }
  .progress .bar { height: 10px; background: #eceef1; border-radius: 999px; overflow: hidden; }
  .progress .bar > div { height: 100%; width: 0; background: linear-gradient(90deg, #e5484d, #f59e0b);
                         border-radius: 999px; transition: width .3s; }
  .progress .status { font-size: 13px; color: var(--muted); margin-top: 8px; display: flex; justify-content: space-between; }
  .progress .log { font-family: ui-monospace, Consolas, monospace; font-size: 12px; color: #475569;
                   margin-top: 8px; max-height: 120px; overflow-y: auto; background: #f8fafc;
                   border-radius: 8px; padding: 8px 10px; }
  .badge { display: inline-block; padding: 2px 8px; border-radius: 5px; font-size: 11px; color: #fff; }
  .badge.run { background: #f59e0b; } .badge.done { background: var(--ok); } .badge.err { background: var(--accent); }

  .report-panel { min-height: 500px; display: flex; flex-direction: column; }
  .report-panel iframe { width: 100%; flex: 1; min-height: 560px; border: 1px solid var(--line);
                         border-radius: 10px; background: #fff; }
  .empty { flex: 1; display: flex; flex-direction: column; align-items: center; justify-content: center;
           color: #9ca3af; gap: 12px; min-height: 400px; text-align: center; }
  .empty .big { font-size: 44px; }
  .toast { position: fixed; bottom: 24px; left: 50%; transform: translateX(-50%);
           background: #1f2937; color: #fff; padding: 10px 18px; border-radius: 8px;
           font-size: 14px; display: none; z-index: 99; }
</style>
</head>
<body>
<header>
  <span class="logo">🎮</span>
  <div>
    <h1>街霸6 录像分析 Agent</h1>
    <div class="sub">确反 / 立回失误 · 机会点 · 场景解法 · 交互式报告</div>
  </div>
</header>

<div class="wrap">
  <div class="panel">
    <h2><span class="num">1</span> 分析设置</h2>

    <div class="field">
      <label>录像文件路径</label>
      <input id="video" placeholder="如 D:/videos/Street Fighter 6/xxx.mp4">
      <div class="hint">训练模式录屏（1920×1080，需带底部帧数据条）</div>
    </div>

    <div class="row2">
      <div class="field">
        <label>P1 角色</label>
        <select id="p1"></select>
      </div>
      <div class="field">
        <label>P2 角色</label>
        <select id="p2"></select>
      </div>
    </div>

    <div class="field">
      <label>帧数据表目录</label>
      <input id="data_dir" value="" onchange="onDataDirChange()">
      <div class="hint">每个角色一个 JSON 文件，角色名=文件名</div>
    </div>

    <div class="field">
      <label>DeepSeek API Key（可留空，读环境变量 OPENAI_API_KEY）</label>
      <input id="api_key" type="password" placeholder="sk-...">
    </div>

    <details class="adv">
      <summary>高级参数</summary>
      <div class="row3" style="margin-top:10px">
        <div class="field"><label>采样 fps</label><input id="fps" type="number" value="15"></div>
        <div class="field"><label>帧差分阈值</label><input id="diff" type="number" value="20"></div>
        <div class="field"><label>掉血阈值</label><input id="drop" type="number" value="5"></div>
      </div>
      <div class="field"><label>只分析前 N 秒（留空=全部）</label><input id="duration" type="number" value=""></div>
    </details>

    <button class="btn" id="start" onclick="startAnalyze()">🚀 开始分析</button>

    <div class="progress" id="progress">
      <div class="bar"><div id="barfill"></div></div>
      <div class="status"><span id="stage"></span><span id="count"></span></div>
      <div class="log" id="log"></div>
    </div>
  </div>

  <div class="panel report-panel">
    <h2><span class="num">2</span> 分析报告 <span id="rbadge"></span></h2>
    <div class="empty" id="empty">
      <span class="big">🥊</span>
      <div>配置左侧参数后点击「开始分析」<br>报告会在这里实时生成</div>
    </div>
    <iframe id="report" style="display:none"></iframe>
  </div>
</div>

<div class="toast" id="toast"></div>

<script>
let taskId = null, pollTimer = null;

function $ (id) { return document.getElementById(id); }

function toast (msg) {
  const t = $("toast"); t.textContent = msg; t.style.display = "block";
  clearTimeout(t._t); t._t = setTimeout(() => t.style.display = "none", 3000);
}

async function loadCharacters () {
  const dir = $("data_dir").value.trim();
  try {
    const url = dir ? "/api/characters?dir=" + encodeURIComponent(dir) : "/api/characters";
    const r = await fetch(url);
    const d = await r.json();
    if (!dir && d.default_dir) $("data_dir").value = d.default_dir;
    const chars = d.characters || [];
    const fill = (sel, def) => {
      sel.innerHTML = chars.map(c => `<option value="${c}">${c}</option>`).join("")
                     || `<option value="">（无帧数据）</option>`;
      if (def && chars.includes(def)) sel.value = def;
    };
    fill($("p1"), "Ryu");
    fill($("p2"), "Ken");
  } catch (e) { toast("读取角色列表失败"); }
}

function onDataDirChange () { loadCharacters(); }

async function startAnalyze () {
  const video = $("video").value.trim();
  if (!video) { toast("请填写录像文件路径"); return; }
  const apiKey = $("api_key").value.trim();
  const body = {
    video, p1: $("p1").value, p2: $("p2").value,
    data_dir: $("data_dir").value.trim(),
    fps: +$("fps").value, diff: +$("diff").value, drop: +$("drop").value,
    duration: $("duration").value ? +$("duration").value : null,
  };
  if (apiKey) body.api_key = apiKey;

  $("start").disabled = true;
  $("empty").style.display = "none";
  $("report").style.display = "none";
  $("progress").style.display = "block";
  $("log").innerHTML = "";
  $("rbadge").innerHTML = '<span class="badge run">分析中</span>';

  try {
    const r = await fetch("/api/analyze", {
      method: "POST", headers: {"Content-Type": "application/json"},
      body: JSON.stringify(body),
    });
    const d = await r.json();
    if (d.error) { toast(d.error); resetStart(); return; }
    taskId = d.task_id;
    pollTimer = setInterval(pollStatus, 1000);
  } catch (e) { toast("请求失败：" + e); resetStart(); }
}

async function pollStatus () {
  if (!taskId) return;
  const r = await fetch("/api/status/" + taskId);
  const t = await r.json();
  if (t.error) { clearInterval(pollTimer); resetStart(); return; }

  const pct = t.total > 0 ? Math.round(t.done / t.total * 100) : 0;
  // 阶段权重：advantage 是主要耗时
  const stageWeight = {prepare:3, health:7, events:10, advantage:80, analyze:95, done:100};
  const overall = Math.min(99, stageWeight[t.stage] || 0);
  $("barfill").style.width = (t.stage === "done" ? 100 : overall) + "%";
  $("stage").textContent = stageLabel(t.stage) + " · " + (t.message || "");
  $("count").textContent = t.total > 1 ? `${t.done}/${t.total}` : "";

  if (t.message && t.message !== $("log").lastChild?.textContent) {
    const line = document.createElement("div");
    line.textContent = "▸ " + t.message;
    $("log").appendChild(line);
    $("log").scrollTop = $("log").scrollHeight;
  }

  if (t.status === "done") {
    clearInterval(pollTimer);
    $("barfill").style.width = "100%";
    $("rbadge").innerHTML = '<span class="badge done">完成</span>';
    $("report").src = "/api/report/" + taskId;
    $("report").style.display = "block";
    resetStart();
  } else if (t.status === "error") {
    clearInterval(pollTimer);
    $("rbadge").innerHTML = '<span class="badge err">失败</span>';
    toast(t.error || "分析失败");
    resetStart();
  }
}

function stageLabel (s) {
  return {prepare:"准备", health:"读取血条", events:"检测交手", advantage:"读取帧优",
          analyze:"生成报告", done:"完成"}[s] || s;
}

function resetStart () { $("start").disabled = false; }

loadCharacters();
</script>
</body>
</html>
"""


if __name__ == "__main__":
    main()
