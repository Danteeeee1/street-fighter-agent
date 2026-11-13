"""生成街霸6（SF6）全 32 角色帧数据表。

运行：python tools/generate_roster.py
输出：sf6_agent/data/*.json

说明：帧数据为社区近似值（供演示/测试），招式名称与指令为社区通用记法。
确反分析的准确度取决于帧数据精度，建议后续用官方/权威帧数据源校准。
"""
from __future__ import annotations

import json
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "sf6_agent" / "data"

# ---- 标准普通技（全角色通用近似值） ----
COMMON_NORMALS = [
    {"name": "站轻拳", "notation": "5LP", "startup": 4, "active": 2, "recovery": 7, "on_hit": 4, "on_block": 1, "damage": 30},
    {"name": "站轻脚", "notation": "5LK", "startup": 5, "active": 2, "recovery": 9, "on_hit": 2, "on_block": -1, "damage": 30},
    {"name": "站中拳", "notation": "5MP", "startup": 7, "active": 3, "recovery": 13, "on_hit": 2, "on_block": -2, "damage": 50},
    {"name": "站中脚", "notation": "5MK", "startup": 8, "active": 3, "recovery": 15, "on_hit": 0, "on_block": -4, "damage": 60},
    {"name": "站重拳", "notation": "5HP", "startup": 9, "active": 3, "recovery": 17, "on_hit": 1, "on_block": -3, "damage": 70},
    {"name": "站重脚", "notation": "5HK", "startup": 12, "active": 4, "recovery": 20, "on_hit": 3, "on_block": -7, "damage": 80},
    {"name": "蹲轻拳", "notation": "2LP", "startup": 4, "active": 2, "recovery": 6, "on_hit": 5, "on_block": 2, "damage": 30},
    {"name": "蹲轻脚", "notation": "2LK", "startup": 4, "active": 2, "recovery": 8, "on_hit": 2, "on_block": 0, "damage": 30},
    {"name": "蹲中拳", "notation": "2MP", "startup": 6, "active": 3, "recovery": 12, "on_hit": 3, "on_block": -2, "damage": 50},
    {"name": "蹲中脚", "notation": "2MK", "startup": 7, "active": 2, "recovery": 14, "on_hit": 2, "on_block": -5, "damage": 40},
    {"name": "蹲重拳", "notation": "2HP", "startup": 8, "active": 4, "recovery": 18, "on_hit": 3, "on_block": -4, "damage": 70},
    {"name": "蹲重脚", "notation": "2HK", "startup": 9, "active": 3, "recovery": 26, "on_hit": 3, "on_block": -12, "damage": 80},
    {"name": "普通投", "notation": "LP+LK", "category": "throw", "startup": 5, "active": 3, "recovery": 20, "on_hit": 0, "on_block": 0, "damage": 120},
]

# ---- 必杀技模板 ----
def sp(name, notation, startup, recovery, on_block, damage=80, on_hit=2, active=4):
    return {"name": name, "notation": notation, "category": "special",
            "startup": startup, "active": active, "recovery": recovery,
            "on_hit": on_hit, "on_block": on_block, "damage": damage}


# ---- 角色：英文名 -> (中文名, [必杀技]) ----
ROSTER = {
    "Ryu": ("隆", [
        sp("波动拳", "236P", 14, 22, -7, 60),
        sp("升龙拳", "623P", 5, 30, -32, 120, on_hit=20),
        sp("旋风腿", "214K", 11, 16, -8, 70),
    ]),
    "Ken": ("肯", [
        sp("波动拳", "236P", 14, 21, -6, 60),
        sp("升龙拳", "623P", 5, 28, -28, 120, on_hit=20),
        sp("旋风腿", "214K", 11, 15, -8, 70),
    ]),
    "Chun-Li": ("春丽", [
        sp("气功拳", "236P", 13, 20, -5, 55),
        sp("百裂脚", "214K", 9, 18, -5, 60),
        sp("鹤脚蹴", "623K", 5, 28, -30, 100, on_hit=18),
    ]),
    "Guile": ("古烈", [
        sp("音速手刀", "[4]6P", 13, 22, -6, 55),
        sp("音速脚刀", "[2]8K", 5, 28, -30, 100, on_hit=18),
    ]),
    "Luke": ("卢克", [
        sp("沙暴弹", "236P", 13, 20, -5, 55),
        sp("升龙拳", "623P", 5, 28, -30, 110, on_hit=18),
    ]),
    "Jamie": ("杰米", [
        sp("醉步突进", "236K", 10, 18, -5, 60),
        sp("醉拳连打", "214P", 8, 16, -4, 55),
    ]),
    "Kimberly": ("金伯利", [
        sp("冲刺突进", "236K", 9, 18, -6, 60),
        sp("空中投掷", "214K", 7, 15, -4, 55),
    ]),
    "Juri": ("朱莉", [
        sp("风切脚", "236K", 8, 16, -4, 55),
        sp("疾风脚", "623K", 5, 26, -26, 100, on_hit=18),
    ]),
    "E. Honda": ("本田", [
        sp("百裂张手", "214P", 7, 16, -3, 55),
        sp("头槌", "[4]6P", 12, 24, -8, 70),
        sp("超级百贯落", "[2]8K", 6, 28, -28, 110, on_hit=18),
    ]),
    "Dhalsim": ("达尔锡", [
        sp("瑜伽火焰", "236P", 13, 20, -6, 55),
        sp("瑜伽传送", "623P", 18, 14, -10, 0, on_hit=0),
    ]),
    "Blanka": ("布兰卡", [
        sp("电击", "214P", 8, 18, -5, 55),
        sp("滚动攻击", "[4]6P", 11, 20, -10, 70),
    ]),
    "Manon": ("曼侬", [
        sp("曼侬旋转", "236K", 12, 18, -6, 60),
        sp("指令投", "236P", 6, 22, 0, 120, on_hit=0),
    ]),
    "Marisa": ("玛丽莎", [
        sp("重拳突进", "236P", 12, 22, -8, 80),
        sp("蓄力重击", "214P", 14, 26, -10, 90),
    ]),
    "Lily": ("莉莉", [
        sp("风旋击", "236K", 12, 20, -7, 60),
        sp("风刃", "236P", 14, 22, -6, 55),
    ]),
    "JP": ("JP", [
        sp("次元刺", "236P", 12, 20, -5, 55),
        sp("次元门", "214K", 15, 18, -8, 60),
    ]),
    "Dee Jay": ("迪杰", [
        sp("气刃", "[4]6P", 13, 22, -6, 55),
        sp("上升气刃", "[2]8K", 6, 28, -28, 100, on_hit=18),
    ]),
    "Cammy": ("嘉米", [
        sp("螺旋箭", "236K", 12, 20, -8, 70),
        sp("加农钉", "623K", 5, 26, -26, 100, on_hit=18),
    ]),
    "Zangief": ("桑吉尔夫", [
        sp("螺旋打桩", "360P", 5, 30, 0, 160, on_hit=0),
        sp("西伯利亚快车", "236K", 12, 22, -8, 70),
    ]),
    "Rashid": ("拉希德", [
        sp("旋风弹", "236P", 13, 20, -5, 55),
        sp("鹰踢", "236K", 10, 18, -6, 60),
    ]),
    "A.K.I.": ("阿鬼", [
        sp("毒刺", "236P", 12, 20, -5, 50),
        sp("毒爪", "214K", 9, 18, -6, 55),
    ]),
    "Ed": ("爱德", [
        sp("心理拳", "236P", 12, 20, -5, 55),
        sp("连打突进", "236K", 10, 18, -6, 60),
    ]),
    "Akuma": ("豪鬼", [
        sp("豪波动拳", "236P", 14, 22, -7, 60),
        sp("豪升龙拳", "623P", 4, 30, -32, 120, on_hit=20),
        sp("豪鬼旋风腿", "214K", 11, 16, -8, 70),
    ]),
    "M. Bison": ("维加", [
        sp("精神力拳", "236P", 13, 20, -6, 60),
        sp("双膝踢", "623K", 8, 22, -10, 80),
    ]),
    "Terry": ("特瑞", [
        sp("能量波", "236P", 14, 22, -7, 60),
        sp("燃烧指节", "623P", 6, 28, -28, 110, on_hit=18),
    ]),
    "Mai": ("舞", [
        sp("花蝶扇", "236P", 13, 20, -6, 55),
        sp("空中旋转", "214K", 10, 18, -5, 60),
    ]),
    "Elena": ("艾莲娜", [
        sp("回旋踢", "236K", 11, 20, -7, 60),
        sp("治愈", "214P", 20, 30, 0, 0, on_hit=0),
    ]),
    "Sagat": ("沙加特", [
        sp("虎波拳", "236P", 13, 22, -6, 60),
        sp("虎膝踢", "623K", 8, 24, -8, 80),
    ]),
    "C. Viper": ("毒蛇", [
        sp("雷脚", "236K", 9, 18, -6, 60),
        sp("火拳", "236P", 13, 22, -7, 70),
    ]),
    "Alex": ("阿历克斯", [
        sp("强力投", "236P", 6, 24, 0, 130, on_hit=0),
        sp("滑铲突进", "236K", 11, 20, -8, 70),
    ]),
    "Ingrid": ("英格丽德", [
        sp("光弹", "236P", 13, 20, -5, 55),
        sp("光刃突进", "236K", 10, 18, -6, 60),
    ]),
    "Yasmine": ("雅斯敏", [
        sp("必杀技A", "236P", 13, 20, -6, 60),
        sp("必杀技B", "236K", 10, 18, -5, 60),
    ]),
    "Arjun": ("阿俊", [
        sp("必杀技A", "236P", 13, 20, -6, 60),
        sp("必杀技B", "623K", 6, 26, -26, 100, on_hit=18),
    ]),
}


def _slug(name: str) -> str:
    return name.replace(".", "").replace(" ", "_").lower()


def build_character(name: str, cn: str, specials: list) -> dict:
    moves = [dict(m, category="normal") for m in COMMON_NORMALS]
    for s in specials:
        moves.append(s)
    return {
        "character": name,
        "cn": cn,
        "note": "近似帧数据（演示用），建议用官方/权威帧数据校准",
        "moves": moves,
    }


def main():
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    count = 0
    for name, (cn, specials) in ROSTER.items():
        data = build_character(name, cn, specials)
        path = DATA_DIR / f"frame_data_{_slug(name)}.json"
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        count += 1
        print(f"  ✓ {name} ({cn}) -> {path.name}")
    print(f"\n共生成 {count} 个角色帧数据文件")


if __name__ == "__main__":
    main()
