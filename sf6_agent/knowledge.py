"""解法知识库：不同失误/机会场景对应的建议模板。

占位符会在生成 Finding 时动态填充，例如：
    {adv} 帧优、{move} 招式名、{startup} 发生帧、{recovery} 收招帧、
    {combo} 推荐连段、{safe} 更安全的替代招、{safe_adv} 其被防帧优。
"""
from __future__ import annotations

SOLUTIONS = {
    "missed_punish": (
        "对手「{move}」被防后 -{adv} 帧，你的最快起手「{punish}」发生 {startup} 帧（≤ {adv}），"
        "存在确反窗口但你未出手。"
    ),
    "missed_punish_opportunity": (
        "这是「可确反却没确反」的窗口：立即用「{punish}」起手确反，"
        "推荐连段：{combo}。训练法：训练模式把对手设置为重复该招，练习「防御→确反」直至稳定。"
    ),
    "unsafe_on_block": (
        "你出「{move}」被防 -{adv} 帧，属于高风险招式，被对方确反。"
        "建议：改用更安全的「{safe}」（被防 {safe_adv} 帧）做立回牵制，"
        "或仅在确认命中后再取消必杀/超必，避免裸出被防。"
    ),
    "missed_whiff_punish": (
        "对手「{move}」空振，收招 {recovery} 帧，你处于可确反距离却未出手。"
        "可用「{punish}」（发生 {startup} 帧）空振确反，或前走/Dash 取消拉近后确反。"
        "要点：看到空振瞬间立即出手，提前量 = 收招帧 - 你的发生帧。"
    ),
    "opportunity": (
        "此处你处于 +{adv} 帧有利，掌握进攻主动权。可选：1) 近身打投择（投/打择）；"
        "2) 继续用帧数有利的招式压制；3) 观察对手习惯后择一次大的。避免浪费有利帧后撤。"
    ),
}


def render(key: str, **kw) -> str:
    template = SOLUTIONS[key]
    try:
        return template.format(**kw)
    except KeyError:
        return template
