"""战术知识库：从教学视频学到的立回/地面战概念，供分析引擎引用。

知识来源见 data/tactic_knowledge.json，可通过 tools/bilibili_learn.py 从更多
教学视频持续扩充。分析时按「失误类型」映射到对应战术概念，给结论附加概念级指导。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# 失误类型 -> (关联概念, 行动建议)
_TIPS = {
    "missed_punish": {
        "concept": "确反",
        "advice": "对手已进入收招硬直、正是确反窗口，你却未出手。确反是差合的具体形式——对手收招硬直时就是你该出手的时机，别犹豫。",
    },
    "unsafe_on_block": {
        "concept": "牵制",
        "advice": "你出的招被防后大幅不利，属于高风险摸奖。立回原则：摸奖要用「击中收益大、被防代价小」的招，否则改用更安全的牵制（发生快、收招快、距离远）。",
    },
    "missed_whiff_punish": {
        "concept": "差合",
        "advice": "对手空振进入收招硬直，你本可差合。差合要点：先保持在攻击距离之外，再在收招硬直时用足够长、足够快的招反击。",
    },
    "opportunity": {
        "concept": "摸奖",
        "advice": "你处于帧数有利，这是主动进攻（摸奖/压制）的时机。立回原则：有利帧要主动进攻，别浪费优势后撤。",
    },
}


class TacticKnowledge:
    """加载并检索战术知识库。"""

    def __init__(self, path):
        self.path = Path(path)
        self.data = {}
        if self.path.exists():
            self.data = json.loads(self.path.read_text(encoding="utf-8"))
        self._concepts = {c["name"]: c for c in self.data.get("concepts", [])}

    def concept(self, name: str) -> Optional[dict]:
        return self._concepts.get(name)

    def concepts(self) -> list:
        return list(self._concepts.keys())

    def tip_for(self, finding_type: str) -> str:
        """根据失误类型返回一条战术指导（行动建议 + 概念解释）。"""
        t = _TIPS.get(finding_type)
        if not t:
            return ""
        c = self._concepts.get(t["concept"])
        if c:
            return f"{t['advice']}（{t['concept']}：{c['explanation']}）"
        return t["advice"]

    def principles(self) -> list:
        return self.data.get("principles", [])

    def sources(self) -> list:
        return self.data.get("sources", [])


_DEFAULT_PATH = Path(__file__).parent / "data" / "tactic_knowledge.json"
_KNOWLEDGE = TacticKnowledge(_DEFAULT_PATH)


def tip_for(finding_type: str) -> str:
    """便捷入口：按失误类型取战术指导。"""
    return _KNOWLEDGE.tip_for(finding_type)
