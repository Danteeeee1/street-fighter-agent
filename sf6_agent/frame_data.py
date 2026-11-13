"""帧数据表加载与查询。

支持用户提供的角色帧数据表（JSON 格式）。每个角色一个 JSON 文件，
放在 data/ 目录下；也可以直接调用 load_characters 传入路径列表。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional

from .models import Move


class CharacterFrameData:
    """单个角色的帧数据。"""

    def __init__(self, character: str, moves: List[Move], cn: str = ""):
        self.character = character
        self.cn = cn or character
        self.moves = moves
        self._by_notation: Dict[str, Move] = {}
        self._by_name: Dict[str, Move] = {}
        for m in moves:
            if m.notation:
                self._by_notation[m.notation.upper()] = m
            if m.name:
                self._by_name[m.name] = m

    def get(self, key: str) -> Optional[Move]:
        """按指令或中文名查询招式，不区分大小写。"""
        if not key:
            return None
        k = key.upper()
        return self._by_notation.get(k) or self._by_name.get(k)

    def fastest_startup(self, category: Optional[str] = None) -> Optional[Move]:
        """最快的起手招式（可限定 category）。"""
        pool = [m for m in self.moves if category is None or m.category == category]
        if not pool:
            return None
        return min(pool, key=lambda m: m.startup)

    def punishable_on_block(self, worst: int = -1) -> List[Move]:
        """被防后至少 -abs(worst) 帧、存在被确反风险的招式。"""
        return [m for m in self.moves if m.on_block <= worst]


class FrameDataLibrary:
    """角色帧数据集合。"""

    def __init__(self):
        self.characters: Dict[str, CharacterFrameData] = {}

    def add(self, cfd: CharacterFrameData) -> None:
        self.characters[cfd.character] = cfd

    def get(self, character: str) -> Optional[CharacterFrameData]:
        if not character:
            return None
        return self.characters.get(character) or self.characters.get(character.title())

    @classmethod
    def load_dir(cls, data_dir) -> "FrameDataLibrary":
        data_dir = Path(data_dir)
        lib = cls()
        if not data_dir.exists():
            return lib
        for p in sorted(data_dir.glob("*.json")):
            try:
                lib.add(cls._load_file(p))
            except Exception as e:  # noqa: BLE001
                print(f"[warn] 跳过帧数据文件 {p.name}: {e}")
        return lib

    @staticmethod
    def _load_file(path: Path) -> CharacterFrameData:
        raw = json.loads(path.read_text(encoding="utf-8"))
        character = raw.get("character") or path.stem
        cn = raw.get("cn", character)
        moves = [Move(**{k: v for k, v in m.items() if k in Move.__dataclass_fields__})
                 for m in raw.get("moves", [])]
        return CharacterFrameData(character, moves, cn)
