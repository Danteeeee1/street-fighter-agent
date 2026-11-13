"""交互式网页报告生成。

生成单文件 HTML：包含对战摘要、时间轴（带失误/机会标注点）、
可筛选的结论卡片。全部内联 CSS/JS，无外部依赖，可直接在浏览器打开。
"""
from __future__ import annotations

import html
import json
from pathlib import Path
from typing import Dict, List

from .models import Exchange, Finding

TYPE_LABELS = {
    "missed_punish": "漏确反",
    "unsafe_on_block": "不安全被防",
    "missed_whiff_punish": "漏空振惩罚",
    "opportunity": "机会点",
}
SEV_LABELS = {"high": "高", "medium": "中", "low": "低"}
SEV_COLORS = {"high": "#e5484d", "medium": "#f5a623", "low": "#3b82f6"}
TYPE_COLORS = {
    "missed_punish": "#e5484d",
    "unsafe_on_block": "#d946ef",
    "missed_whiff_punish": "#f5a623",
    "opportunity": "#10b981",
}


def _fmt_time(seconds: float) -> str:
    m, s = divmod(int(seconds), 60)
    return f"{m}:{s:02d}"


def _fmt_frame(frame_index: int, fps: int = 60) -> str:
    sec = (frame_index - 1) / fps
    return f"帧 {frame_index}（{_fmt_time(sec)}）"


def generate_report(
    match: Dict,
    exchanges: List[Exchange],
    findings: List[Finding],
    out_path: str,
) -> str:
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fps = match.get("fps", 60)

    # 摘要统计
    by_sev = {"high": 0, "medium": 0, "low": 0}
    by_type = {}
    for f in findings:
        by_sev[f.severity.value] = by_sev.get(f.severity.value, 0) + 1
        by_type[f.finding_type.value] = by_type.get(f.finding_type.value, 0) + 1

    timeline = _render_timeline(match, findings, fps)
    cards = "\n".join(_render_card(f, match, fps) for f in findings)
    if not cards:
        cards = _empty_state()

    html_doc = _HTML_TEMPLATE.format(
        title=html.escape(match.get("title", "SF6 录像分析报告")),
        game=html.escape(match.get("game", "Street Fighter 6")),
        p1=html.escape(match.get("p1_char", "P1")),
        p2=html.escape(match.get("p2_char", "P2")),
        rounds=match.get("rounds", 1),
        total_frames=match.get("total_frames", 0),
        duration=_fmt_time(match.get("duration", 0)),
        summary_stats=_render_summary(by_sev, by_type),
        timeline=timeline,
        cards=cards,
        data_json=json.dumps([_finding_dict(f, match) for f in findings], ensure_ascii=False),
    )
    out.write_text(html_doc, encoding="utf-8")
    return str(out)


def _render_summary(by_sev, by_type) -> str:
    parts = []
    for sev, label, color in [("high", "高", SEV_COLORS["high"]),
                              ("medium", "中", SEV_COLORS["medium"]),
                              ("low", "低", SEV_COLORS["low"])]:
        if by_sev.get(sev):
            parts.append(
                f'<span class="chip" style="--c:{color}">{label}危 {by_sev[sev]}</span>'
            )
    for t, n in by_type.items():
        parts.append(
            f'<span class="chip" style="--c:{TYPE_COLORS.get(t, "#888")}">'
            f'{TYPE_LABELS.get(t, t)} {n}</span>'
        )
    return "".join(parts) if parts else '<span class="chip" style="--c:#10b981">无结论</span>'


def _render_timeline(match, findings, fps) -> str:
    duration = max(match.get("duration", 1.0), 1.0)
    width, height = 1080, 150
    pad = 60
    usable = width - pad * 2

    ticks = []
    for i in range(0, 13):
        sec = duration * i / 12
        x = pad + usable * i / 12
        ticks.append(
            f'<line x1="{x:.1f}" y1="{height-30}" x2="{x:.1f}" y2="{height-22}" '
            f'stroke="#cbd5e1" stroke-width="1"/>'
            f'<text x="{x:.1f}" y="{height-8}" font-size="11" fill="#64748b" '
            f'text-anchor="middle">{_fmt_time(sec)}</text>'
        )
    axis = (f'<line x1="{pad}" y1="{height-30}" x2="{width-pad}" y2="{height-30}" '
            f'stroke="#e2e8f0" stroke-width="2"/>')

    markers = []
    # 按严重度分层高度，避免重叠
    lane = {"high": height - 60, "medium": height - 80, "low": height - 100}
    for f in findings:
        x = pad + usable * (f.start_frame / fps / duration)
        color = SEV_COLORS[f.severity.value]
        y = lane[f.severity.value]
        markers.append(
            f'<g class="marker" data-finding="{f.finding_id}" '
            f'onclick="focusFinding({f.finding_id})">'
            f'<line x1="{x:.1f}" y1="{height-30}" x2="{x:.1f}" y2="{y}" '
            f'stroke="{color}" stroke-width="1" opacity="0.5"/>'
            f'<circle cx="{x:.1f}" cy="{y}" r="7" fill="{color}" stroke="#fff" stroke-width="2"/>'
            f'<title>{html.escape(f.title)}</title>'
            f'</g>'
        )

    legend = "".join(
        f'<text x="{pad + 20 + i * 110}" y="20" font-size="12" fill="{SEV_COLORS[k]}">'
        f'● {SEV_LABELS[k]}危</text>'
        for i, k in enumerate(["high", "medium", "low"])
    )

    return (f'<svg viewBox="0 0 {width} {height}" width="100%" '
            f'xmlns="http://www.w3.org/2000/svg">'
            f'{legend}{"".join(ticks)}{axis}{"".join(markers)}</svg>')


def _render_card(f: Finding, match, fps) -> str:
    color = TYPE_COLORS.get(f.finding_type.value, "#888")
    sev_color = SEV_COLORS[f.severity.value]
    player_name = match.get("p1_char", "P1") if f.player == 1 else match.get("p2_char", "P2")
    tactic_row = (f'<div class="row tactic"><span class="k">战术</span>'
                  f'<span class="v">{html.escape(f.tactic_tip)}</span></div>') if f.tactic_tip else ""
    return f'''
<article class="card" id="finding-{f.finding_id}"
         data-severity="{f.severity.value}" data-type="{f.finding_type.value}">
  <div class="card-head">
    <span class="badge type" style="--c:{color}">{TYPE_LABELS.get(f.finding_type.value, f.finding_type.value)}</span>
    <span class="badge sev" style="--c:{sev_color}">{SEV_LABELS[f.severity.value]}危</span>
    <span class="who">失误方：{html.escape(player_name)}</span>
    <span class="frame">{_fmt_frame(f.start_frame, fps)} ~ {_fmt_frame(f.end_frame, fps)}</span>
  </div>
  <h3>{html.escape(f.title)}</h3>
  <div class="row"><span class="k">失误分析</span><span class="v">{html.escape(f.description)}</span></div>
  <div class="row"><span class="k">机会点</span><span class="v">{html.escape(f.opportunity)}</span></div>
  <div class="row solution"><span class="k">解法</span><span class="v">{html.escape(f.solution)}</span></div>
  {tactic_row}
</article>'''


def _empty_state() -> str:
    return ('<div class="empty">未发现明显的确反/立回失误。'
            '若录像质量较低或帧优显示缺失，请检查画面识别与帧数据表配置。</div>')


def _finding_dict(f: Finding, match) -> dict:
    return {
        "id": f.finding_id,
        "type": f.finding_type.value,
        "type_label": TYPE_LABELS.get(f.finding_type.value, f.finding_type.value),
        "severity": f.severity.value,
        "player": f.player,
        "player_name": match.get("p1_char", "P1") if f.player == 1 else match.get("p2_char", "P2"),
        "title": f.title,
        "description": f.description,
        "opportunity": f.opportunity,
        "solution": f.solution,
        "start_frame": f.start_frame,
        "end_frame": f.end_frame,
        "frame_advantage": f.frame_advantage,
        "tactic_tip": f.tactic_tip,
    }


_HTML_TEMPLATE = """<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{title}</title>
<style>
  :root {{
    --bg: #f6f7f9; --card: #ffffff; --line: #e5e7eb; --text: #1f2937; --muted: #6b7280;
    --accent: #e5484d;
  }}
  * {{ box-sizing: border-box; }}
  body {{ margin: 0; font-family: -apple-system, "Segoe UI", "PingFang SC", "Microsoft YaHei", sans-serif;
         background: var(--bg); color: var(--text); line-height: 1.6; }}
  header {{ background: linear-gradient(135deg, #1f2937, #374151); color: #fff; padding: 28px 32px; }}
  header h1 {{ margin: 0 0 6px; font-size: 22px; }}
  header .sub {{ color: #cbd5e1; font-size: 14px; }}
  .wrap {{ max-width: 1180px; margin: 0 auto; padding: 24px 20px 60px; }}
  .summary {{ display: flex; flex-wrap: wrap; gap: 8px; margin: 0 0 18px; }}
  .chip {{ background: #fff; border: 1px solid var(--line); border-left: 4px solid var(--c, #888);
          padding: 4px 12px; border-radius: 6px; font-size: 13px; color: var(--text); }}
  .panel {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px;
           padding: 18px 20px; margin-bottom: 20px; box-shadow: 0 1px 2px rgba(0,0,0,.03); }}
  .panel h2 {{ margin: 0 0 10px; font-size: 16px; }}
  .filters {{ display: flex; flex-wrap: wrap; gap: 8px; margin-bottom: 16px; }}
  .fbtn {{ cursor: pointer; border: 1px solid var(--line); background: #fff; padding: 5px 14px;
          border-radius: 20px; font-size: 13px; color: var(--muted); }}
  .fbtn.active {{ background: #1f2937; color: #fff; border-color: #1f2937; }}
  .marker {{ cursor: pointer; }}
  .cards {{ display: flex; flex-direction: column; gap: 14px; }}
  .card {{ background: var(--card); border: 1px solid var(--line); border-radius: 12px; padding: 16px 18px; }}
  .card-head {{ display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 8px; }}
  .badge {{ color: #fff; border-radius: 5px; padding: 2px 9px; font-size: 12px; background: var(--c, #888); }}
  .who, .frame {{ color: var(--muted); font-size: 13px; }}
  .frame {{ margin-left: auto; font-variant-numeric: tabular-nums; }}
  .card h3 {{ margin: 0 0 10px; font-size: 16px; }}
  .row {{ display: grid; grid-template-columns: 72px 1fr; gap: 10px; padding: 4px 0; font-size: 14px; }}
  .row .k {{ color: var(--muted); font-weight: 600; }}
  .row.solution {{ background: #fef2f2; border-radius: 8px; padding: 10px 12px; margin-top: 6px; }}
  .row.solution .k {{ color: #b91c1c; }}
  .row.tactic {{ background: #eef4ff; border-radius: 8px; padding: 10px 12px; margin-top: 6px; }}
  .row.tactic .k {{ color: #1d4ed8; }}
  .empty {{ text-align: center; color: var(--muted); padding: 40px; }}
  .highlight {{ animation: pulse 1.6s ease-out; }}
  @keyframes pulse {{ 0% {{ box-shadow: 0 0 0 4px rgba(229,72,77,.35); }} 100% {{ box-shadow: 0 0 0 0 rgba(229,72,77,0); }} }}
</style>
</head>
<body>
<header>
  <h1>{title}</h1>
  <div class="sub">{game} · {p1} vs {p2} · 共 {rounds} 局 · 时长 {duration} · {total_frames} 帧</div>
</header>
<div class="wrap">
  <div class="summary">{summary_stats}</div>

  <div class="panel">
    <h2>时间轴（点击标注点跳转到结论）</h2>
    {timeline}
  </div>

  <div class="filters">
    <button class="fbtn active" data-filter="all" onclick="setFilter('all', this)">全部</button>
    <button class="fbtn" data-filter="high" onclick="setFilter('high', this)">高严重度</button>
    <button class="fbtn" data-filter="medium" onclick="setFilter('medium', this)">中严重度</button>
    <button class="fbtn" data-filter="low" onclick="setFilter('low', this)">低严重度</button>
    <button class="fbtn" data-filter="missed_punish" onclick="setFilter('missed_punish', this)">漏确反</button>
    <button class="fbtn" data-filter="unsafe_on_block" onclick="setFilter('unsafe_on_block', this)">不安全被防</button>
    <button class="fbtn" data-filter="missed_whiff_punish" onclick="setFilter('missed_whiff_punish', this)">漏空振惩罚</button>
    <button class="fbtn" data-filter="opportunity" onclick="setFilter('opportunity', this)">机会点</button>
  </div>

  <div class="cards">
{cards}
  </div>
</div>

<script>
  let activeFilter = "all";
  function setFilter(f, btn) {{
    activeFilter = f;
    document.querySelectorAll(".fbtn").forEach(b => b.classList.remove("active"));
    btn.classList.add("active");
    applyFilter();
  }}
  function applyFilter() {{
    document.querySelectorAll(".card").forEach(card => {{
      const ok = activeFilter === "all" || card.dataset.severity === activeFilter || card.dataset.type === activeFilter;
      card.style.display = ok ? "" : "none";
    }});
  }}
  function focusFinding(id) {{
    const card = document.getElementById("finding-" + id);
    if (!card) return;
    card.scrollIntoView({{ behavior: "smooth", block: "center" }});
    card.classList.remove("highlight");
    void card.offsetWidth;
    card.classList.add("highlight");
  }}
</script>
</body>
</html>
"""
