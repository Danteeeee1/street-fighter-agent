"""画面识别（可插拔）。

VisionProvider 把单帧图片读取为 FrameState。提供三种实现：
- MockVisionProvider：从样例轨迹回放，用于演示/测试整条流水线；
- HeuristicVisionProvider：基于 OpenCV 的颜色/阈值启发式，读取血条等（需按录屏标定区域）；
- LLMVisionProvider：把单帧交给多模态大模型理解（更准，需自行接入 SDK / WorkBuddy 云端大模型）。
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Dict, List, Optional

from .models import ContactResult, FrameState


class VisionProvider(ABC):
    """画面识别接口。"""

    @abstractmethod
    def read(self, frame_path: str, frame_index: int, timestamp: float) -> FrameState:
        """读取单帧，返回该帧状态。"""


class MockVisionProvider(VisionProvider):
    """从预生成的轨迹回放，用于演示与测试。"""

    def __init__(self, trace: List[FrameState]):
        self.trace: Dict[int, FrameState] = {fs.frame_index: fs for fs in trace}

    def read(self, frame_path, frame_index, timestamp):
        return self.trace.get(
            frame_index, FrameState(frame_index=frame_index, timestamp=timestamp)
        )


class HeuristicVisionProvider(VisionProvider):
    """启发式 CV：血条颜色占比 -> 血量；计时器/帧优可扩展 OCR。

    注意：SF6 各模式 UI 布局、录屏分辨率与录屏范围不同，region 需按
    config.yaml 中标定；本实现是「可用的起点」，建议结合 LLMVisionProvider
    或自行训练的检测模型获得更稳的效果。
    """

    def __init__(self, regions: Optional[Dict[str, list]] = None):
        self.regions = regions or {
            "p1_health_region": [0.02, 0.02, 0.40, 0.05],
            "p2_health_region": [0.58, 0.02, 0.40, 0.05],
        }

    def read(self, frame_path: str, frame_index: int, timestamp: float) -> FrameState:
        fs = FrameState(frame_index=frame_index, timestamp=timestamp)
        try:
            import cv2  # noqa: WPS433
            import numpy as np  # noqa: WPS433
        except ImportError:
            return fs  # 未安装 opencv 时跳过画面读取

        img = cv2.imread(frame_path)
        if img is None:
            return fs
        h, w = img.shape[:2]
        fs.p1_health = self._health_pct(img, w, h, "p1_health_region")
        fs.p2_health = self._health_pct(img, w, h, "p2_health_region")
        return fs

    def _health_pct(self, img, w, h, region_key) -> float:
        x, y, rw, rh = self.regions[region_key]
        x1, y1 = int(x * w), int(y * h)
        x2, y2 = int((x + rw) * w), int((y + rh) * h)
        roi = img[y1:y2, x1:x2]
        if roi.size == 0:
            return 100.0
        import cv2 as _cv2  # noqa: WPS433
        import numpy as np  # noqa: WPS433

        # SF6 血条为黄/橙系，统计该色系像素占比作为剩余血量（近似）
        hsv = _cv2.cvtColor(roi, _cv2.COLOR_BGR2HSV)
        mask = _cv2.inRange(hsv, (15, 80, 120), (40, 255, 255))
        filled = np.count_nonzero(mask)
        total = mask.shape[0] * mask.shape[1]
        return round(100.0 * filled / max(total, 1), 1)


class SF6TrainingVisionProvider(VisionProvider):
    """SF6 训练模式（1920x1080）专用画面识别。

    已标定 UI 布局（基于真实录像）：
    - 血条：P1 左上红色，P2 右上蓝色（颜色检测，可靠）；
    - 帧数据条「硬直差」：画面底部两行文字（OCR 尽力而为，建议由 LLM 增强）；
    - 计时器：顶部中央（OCR 尽力而为）。

    注意：帧优数字 / 命中 / 防御 / 空振 判定，本地 OCR/CV 精度有限，
    推荐用 LLMVisionProvider（多模态大模型）作为主识别，本类用于血条等
    确定性读数与画面变化检测。
    """

    DEFAULT_REGIONS = {
        # 血条区域（归一化 [x, y, w, h]）
        "p1_health": [0.15, 0.05, 0.28, 0.04],
        "p2_health": [0.57, 0.05, 0.28, 0.04],
        # 帧数据条文字区（像素坐标，针对 1920x1080）
        "frame_row1": [340, 770, 640, 840],
        "frame_row2": [340, 856, 640, 926],
        # 计时器区域（像素坐标）
        "timer": [870, 20, 1060, 130],
    }

    def __init__(self, regions=None, use_ocr=False):
        self.regions = regions or dict(self.DEFAULT_REGIONS)
        self._ocr = None
        if use_ocr:
            try:
                from rapidocr_onnxruntime import RapidOCR  # noqa: WPS433
                self._ocr = RapidOCR()
            except Exception:  # noqa: BLE001
                self._ocr = None

    def read(self, frame_path, frame_index, timestamp):
        fs = FrameState(frame_index=frame_index, timestamp=timestamp)
        try:
            import cv2  # noqa: WPS433
            import numpy as np  # noqa: WPS433
        except ImportError:
            return fs
        img = cv2.imread(frame_path)
        if img is None:
            return fs
        h, w = img.shape[:2]
        fs.p1_health = self._health_ratio(img, w, h, "p1_health", "red")
        fs.p2_health = self._health_ratio(img, w, h, "p2_health", "blue")
        if self._ocr is not None:
            adv1, adv2 = self._read_frame_advantage(img)
            if adv1 is not None or adv2 is not None:
                fs.frame_advantage = adv1 if adv1 is not None else (-adv2 if adv2 is not None else None)
        return fs

    def _health_ratio(self, img, w, h, key, color):
        x, y, rw, rh = self.regions[key]
        roi = img[int(y * h):int((y + rh) * h), int(x * w):int((x + rw) * w)]
        if roi.size == 0:
            return 100.0
        import cv2 as _cv2  # noqa: WPS433
        import numpy as np  # noqa: WPS433
        hsv = _cv2.cvtColor(roi, _cv2.COLOR_BGR2HSV)
        if color == "red":
            m1 = _cv2.inRange(hsv, (0, 40, 40), (12, 255, 255))
            m2 = _cv2.inRange(hsv, (168, 40, 40), (180, 255, 255))
            mask = _cv2.bitwise_or(m1, m2)
        else:
            mask = _cv2.inRange(hsv, (100, 60, 40), (135, 255, 255))
        return round(100.0 * np.count_nonzero(mask) / max(roi.shape[0] * roi.shape[1], 1), 1)

    def _read_frame_advantage(self, img):
        """读底部帧数据条的「硬直差」数字，返回 (p1_adv, p2_adv)。OCR 尽力而为。"""
        import cv2  # noqa: WPS433
        results = []
        for key in ("frame_row1", "frame_row2"):
            x1, y1, x2, y2 = self.regions[key]
            crop = img[y1:y2, x1:x2]
            crop = cv2.resize(crop, None, fx=4, fy=4, interpolation=cv2.INTER_CUBIC)
            gray = cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY)
            _, binary = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            import numpy as np  # noqa: WPS433
            if np.mean(binary) < 128:
                binary = cv2.bitwise_not(binary)
            res, _ = self._ocr(binary)
            text = " ".join(t for _, t, _ in res) if res else ""
            results.append(self._parse_advantage(text))
        return results[0], results[1]

    @staticmethod
    def _parse_advantage(text):
        import re
        m = re.search(r"硬直差?\s*([+-]?\d+)", text.replace(" ", ""))
        if m:
            try:
                return int(m.group(1))
            except ValueError:
                return None
        return None


class LLMVisionProvider(VisionProvider):
    """多模态大模型帧优读取（DeepSeek deepseek-flash，OpenAI 兼容）。

    只裁剪画面底部「帧数据条」区域（y≈68.5%~100%）交给模型，读两行「硬直差」帧优。
    实测：整帧约 172s/帧 → 裁剪后约 1.8s/帧，准确率与人工一致。

    血条请用本地 CV（SF6TrainingVisionProvider）读取；本类只负责帧优。
    如需「命中/防御/空振」判定，可另裁剪画面中部区域扩展（见 CROP_REGION 思路）。

    配置（环境变量或构造参数）：
        OPENAI_BASE_URL   默认 https://api.deepseek.com
        OPENAI_API_KEY    DeepSeek key（platform.deepseek.com）
        SF6_VISION_MODEL  默认 deepseek-flash
    """

    CROP_Y_RATIO = (0.685, 1.0)  # 帧数据条纵向范围（占画面高度比例）

    PROMPT = (
        "这是街霸6(Street Fighter 6)训练模式画面底部的帧数据条区域。"
        "画面中有上下两行帧数据文字：上方那行标注 PLAYER1，下方那行标注 PLAYER2。"
        "每行格式均为「発生X帧 / 总计Y帧 / 硬直差Z帧」。"
        '请仅返回一个 JSON：{"p1_adv": 整数, "p2_adv": 整数}，'
        "其中 p1_adv 是【上方 PLAYER1 行】的硬直差 Z 值，"
        "p2_adv 是【下方 PLAYER2 行】的硬直差 Z 值。"
        "硬直差显示为 -- 时填 0。不要输出任何解释文字。"
    )

    def __init__(self, base_url=None, api_key=None, model=None):
        import os

        self.base_url = base_url or os.getenv("OPENAI_BASE_URL") or "https://api.deepseek.com"
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("SF6_VISION_MODEL", "deepseek-flash")
        self._client = None
        if self.api_key:
            try:
                from openai import OpenAI  # noqa: WPS433

                self._client = OpenAI(base_url=self.base_url, api_key=self.api_key)
            except ImportError:
                self._client = None

    def read(self, frame_path: str, frame_index: int, timestamp: float) -> FrameState:
        """读取单帧的帧优（P1 视角）。血条不在此读取。"""
        fs = FrameState(frame_index=frame_index, timestamp=timestamp)
        if self._client is None:
            raise RuntimeError(
                "LLMVisionProvider 未配置：请设置 OPENAI_API_KEY（可选 OPENAI_BASE_URL、"
                "SF6_VISION_MODEL），或先 pip install openai"
            )
        data = self._call(frame_path)
        if not data:
            return fs
        adv1 = data.get("p1_adv")
        adv2 = data.get("p2_adv")
        if isinstance(adv1, int) and adv1 != 0:
            fs.frame_advantage = adv1
        elif isinstance(adv2, int) and adv2 != 0:
            fs.frame_advantage = -adv2
        return fs

    def _call(self, frame_path):
        import base64

        import cv2  # noqa: WPS433

        img = cv2.imread(frame_path)
        if img is None:
            return None
        h, w = img.shape[:2]
        y1 = int(self.CROP_Y_RATIO[0] * h)
        y2 = int(self.CROP_Y_RATIO[1] * h)
        crop = img[y1:y2, :]
        if crop.shape[1] > 1280:
            scale = 1280 / crop.shape[1]
            crop = cv2.resize(crop, None, fx=scale, fy=scale,
                              interpolation=cv2.INTER_AREA)
        ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 88])
        if not ok:
            return None
        b64 = base64.b64encode(buf.tobytes()).decode()

        resp = self._client.chat.completions.create(
            model=self.model,
            messages=[{
                "role": "user",
                "content": [
                    {"type": "text", "text": self.PROMPT},
                    {"type": "image_url",
                     "image_url": {"url": f"data:image/jpeg;base64,{b64}"}},
                ],
            }],
            temperature=0,
        )
        return self._parse_json(resp.choices[0].message.content)

    @staticmethod
    def _parse_json(text):
        import json
        import re

        text = (text or "").strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            m = re.search(r"\{.*\}", text, re.S)
            if m:
                try:
                    return json.loads(m.group(0))
                except json.JSONDecodeError:
                    return None
        return None
