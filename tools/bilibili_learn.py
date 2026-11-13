"""从 B 站教学视频提取街霸6(SF6)知识。

流程：解析 B 站链接 → 获取标题/简介/分P → LLM 结构化抽取
（帧数据 / 角色对策 / 连段 / 通用技巧）→ 输出 JSON。

用法：
  python tools/bilibili_learn.py BV1xxxx --out knowledge.json
  python tools/bilibili_learn.py "https://www.bilibili.com/video/BV1xxxx" --out knowledge.json

依赖：openai（OPENAI_API_KEY 环境变量，默认走 DeepSeek）
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from functools import reduce
from pathlib import Path

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"

_MIXIN_TAB = [46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
              33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40, 61,
              26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11, 36,
              20, 34, 44, 52]

EXTRACT_PROMPT = """你是一个街霸6(Street Fighter 6)格斗游戏数据分析助手。
下面是一个 B 站教学视频的【标题】和【简介】，请从中抽取结构化的格斗知识。

只抽取文中明确提到、能确证的内容，不要编造。返回纯 JSON（不要 markdown 代码块），结构：

{{
  "frame_data": [
    {{"character": "角色英文名", "move": "招式中文名", "notation": "指令如2MK/623P",
      "startup": 发生帧数, "recovery": 收招帧数, "on_hit": 命中帧优, "on_block": 被防帧优,
      "damage": 伤害}}
  ],
  "matchups": [
    {{"vs_character": "对手角色", "advice": "对策建议（原文提炼）"}}
  ],
  "combos": [
    {{"character": "角色", "starter": "起手招式", "combo": "连段内容", "notes": "备注"}}
  ],
  "general_tips": ["通用技巧/系统机制要点"]
}}

字段缺省时填空数组 []。数值字段必须是整数；若原文只说"发生很快"这类模糊描述，
不要强行填数字，宁可省略该字段。

【标题】{title}

【简介】
{desc}
"""


def parse_bvid(text: str) -> str:
    m = re.search(r"(BV[0-9A-Za-z]{10})", text or "")
    if not m:
        raise ValueError(f"未识别到 BV 号：{text}")
    return m.group(1)


def fetch_video(bvid: str) -> dict:
    url = f"https://api.bilibili.com/x/web-interface/view?bvid={bvid}"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com"})
    with urllib.request.urlopen(req, timeout=15) as resp:
        data = json.loads(resp.read().decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"B站接口错误：{data.get('message')}")
    d = data["data"]
    return {
        "bvid": d["bvid"],
        "aid": d["aid"],
        "title": d.get("title", ""),
        "desc": d.get("desc", ""),
        "duration": d.get("duration", 0),
        "pages": [
            {"cid": p["cid"], "part": p.get("part", ""), "duration": p.get("duration", 0)}
            for p in d.get("pages", [])
        ],
    }


def _get_wbi_keys() -> tuple:
    url = "https://api.bilibili.com/x/web-interface/nav"
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com"})
    with urllib.request.urlopen(req, timeout=10) as resp:
        wbi = json.loads(resp.read().decode("utf-8"))["data"]["wbi_img"]
    img_key = wbi["img_url"].split("/")[-1].split(".")[0]
    sub_key = wbi["sub_url"].split("/")[-1].split(".")[0]
    return img_key, sub_key


def _sign_wbi(params: dict) -> dict:
    img_key, sub_key = _get_wbi_keys()
    raw = img_key + sub_key
    mixin_key = reduce(lambda s, i: s + raw[i], _MIXIN_TAB, "")[:32]
    params["wts"] = int(time.time())
    params = dict(sorted(params.items()))
    params = {k: "".join(c for c in str(v) if c not in "!'()*") for k, v in params.items()}
    query = urllib.parse.urlencode(params)
    params["w_rid"] = hashlib.md5((query + mixin_key).encode()).hexdigest()
    return params


def _http_get(url: str) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://www.bilibili.com"})
    with urllib.request.urlopen(req, timeout=60) as resp:
        return resp.read()


def download_audio(bvid: str, cid: int, out_dir: str = "tools/tmp") -> str:
    """下载视频音频并转 16kHz 单声道 wav，返回 wav 路径。"""
    params = _sign_wbi({"bvid": bvid, "cid": str(cid), "fnval": "16"})
    url = "https://api.bilibili.com/x/player/playurl?" + urllib.parse.urlencode(params)
    data = json.loads(_http_get(url).decode("utf-8"))
    if data.get("code") != 0:
        raise RuntimeError(f"音频接口错误：{data.get('message')}")
    audio_list = (data.get("data") or {}).get("dash", {}).get("audio", [])
    if not audio_list:
        raise RuntimeError("未获取到音频流（可能需要登录态）")
    audio = min(audio_list, key=lambda a: a.get("bandwidth", 10**9))
    raw = _http_get(audio["baseUrl"])

    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    m4s = out_dir / f"{bvid}_audio.m4s"
    wav = out_dir / f"{bvid}_audio.wav"
    m4s.write_bytes(raw)
    subprocess.run(
        ["ffmpeg", "-y", "-hide_banner", "-loglevel", "error",
         "-i", str(m4s), "-ar", "16000", "-ac", "1", "-c:a", "pcm_s16le", str(wav)],
        check=True,
    )
    print(f"音频已下载并转码：{wav}（{wav.stat().st_size // 1024} KB）")
    return str(wav)


def transcribe_audio(wav_path: str, model_size: str = "small") -> str:
    """用 faster-whisper 转文字，返回全文（含时间戳）。"""
    os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
    from faster_whisper import WhisperModel

    import wave
    import numpy as np

    model = WhisperModel(model_size, device="cpu", compute_type="int8")
    with wave.open(wav_path, "rb") as w:
        samples = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16)
        samples = samples.astype(np.float32) / 32768.0
    segments, _ = model.transcribe(samples, language="zh", vad_filter=True)
    lines = [f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}" for s in segments]
    return "\n".join(lines)


def call_llm(prompt: str, api_key: str = None, model: str = "deepseek-chat") -> str:
    from openai import OpenAI

    client = OpenAI(
        base_url=os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com",
        api_key=api_key or os.getenv("OPENAI_API_KEY"),
    )
    resp = client.chat.completions.create(
        model=model,
        messages=[{"role": "user", "content": prompt}],
        temperature=0,
    )
    return resp.choices[0].message.content


def parse_json(text: str) -> dict:
    text = (text or "").strip()
    text = re.sub(r"^```(?:json)?\s*|\s*```$", "", text)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        m = re.search(r"\{.*\}", text, re.S)
        if m:
            return json.loads(m.group(0))
        raise


def learn(bvid: str, api_key: str = None, model: str = "deepseek-chat",
          use_asr: bool = True, asr_model: str = "small") -> dict:
    video = fetch_video(bvid)
    print(f"视频：{video['title']}")
    print(f"时长：{video['duration']}s，分P：{len(video['pages'])}，简介：{len(video['desc'])} 字")

    text = video["desc"]
    source = "简介"
    if not text or text == "-":
        if not use_asr:
            print("[提示] 简介为空且未启用语音转写，无法提取知识。")
            return {"video": video, "knowledge": {}, "source": "none"}
        cid = video["pages"][0]["cid"]
        print("简介为空，下载音频并语音转文字（首次需下载模型，约几分钟）…")
        wav = download_audio(bvid, cid)
        text = transcribe_audio(wav, asr_model)
        source = "语音转写"
        print(f"转写完成，共 {len(text)} 字符")

    prompt = EXTRACT_PROMPT.format(title=video["title"], desc=text[:8000])
    print("调用 LLM 抽取知识…")
    raw = call_llm(prompt, api_key, model)
    knowledge = parse_json(raw)
    return {"video": video, "source": source, "knowledge": knowledge}


def main():
    ap = argparse.ArgumentParser(description="从 B 站教学视频提取街霸6知识")
    ap.add_argument("url_or_bvid", help="B站链接或 BV 号")
    ap.add_argument("--out", default="knowledge.json", help="输出 JSON 路径")
    ap.add_argument("--model", default="deepseek-chat")
    ap.add_argument("--asr-model", default="small", help="语音转写模型 small/medium")
    ap.add_argument("--no-asr", action="store_true", help="简介为空时不启用语音转写")
    args = ap.parse_args()

    try:
        bvid = parse_bvid(args.url_or_bvid)
        result = learn(bvid, model=args.model,
                       use_asr=not args.no_asr, asr_model=args.asr_model)
    except Exception as e:  # noqa: BLE001
        print(f"✗ 失败：{e}")
        sys.exit(1)

    out = args.out
    with open(out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    k = result["knowledge"]
    print(f"\n=== 抽取结果（来源：{result.get('source')}）===")
    print(f"帧数据 {len(k.get('frame_data', []))} 条，"
          f"对策 {len(k.get('matchups', []))} 条，"
          f"连段 {len(k.get('combos', []))} 条，"
          f"技巧 {len(k.get('general_tips', []))} 条")
    for fd in k.get("frame_data", []):
        print(f"  [帧数据] {fd.get('character')} {fd.get('move')} "
              f"发生{fd.get('startup','?')} 被防{fd.get('on_block','?')}")
    print(f"\n已保存：{out}")


if __name__ == "__main__":
    main()
