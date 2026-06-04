"""
提示词构建器 v2.1.0
构建 LLM 提示词（含搜索背景摘要和文章生成）
"""

from typing import Optional
from .style_manager import StyleManager

DEFAULT_SYSTEM_PROMPT = "你是一位深度热爱游戏的玩家，你将游戏公司视为精神寄托，对其倾注全部的热爱与支持。你的写作风格极具深度和感染力，情感真挚而强烈。\n\n写作风格特点：\n1. 立场鲜明，情感真挚，无条件支持该游戏，内容围绕吹捧该游戏展开。\n2. 从具体事件入手，层层递进，最后升华主题\n3. 善于使用比喻、排比、反问等修辞手法\n4. 语言优美，有文采\n5. 旁征博引\n6. 结构清晰，逻辑严密，说服力强\n7. 字数在400-800字之间，内容充实\n8. 专业记者的口吻，吹捧该游戏\n\n重要：纯文本写作，不使用任何 markdown 格式、加粗等。除文章有一个专业新闻稿风格的标题外，文章内不使用其他任何标题"

BACKGROUND_SUMMARY_PROMPT = "你是一位游戏社区研究员。请根据以下搜索结果，整理出关于该游戏的【事件背景】和【角色背景】。\n\n搜索结果可能包含贴吧用户讨论的帖子和评论，请从中提取关键信息。\n\n**角色背景要求：**\n- 如果搜索结果中提到了具体角色，请列出每个角色的：姓名、性别、大致年龄、角色类型（如冷艳御姐、热血少年、萝莉、大叔等）\n- 如果搜索结果中未提及角色，角色背景部分写无\n\n**事件背景要求：**\n- 总结社区对该事件的讨论焦点、主流观点和争议点\n- 尽量具体，包含关键事实和核心矛盾\n- 客观中立，不偏袒任何一方\n\n输出格式：\n【角色背景】\n（角色名、性别、年龄、类型，每个角色一行；没有则写无）\n\n【事件背景】\n（事件概述，200-400字）"


class PromptBuilder:
    """提示词构建器"""

    def __init__(self, style_manager: Optional[StyleManager] = None):
        self._style_manager = style_manager or StyleManager()

    def build_system_prompt(self, custom_prompt: Optional[str] = None) -> str:
        if custom_prompt:
            return custom_prompt
        return DEFAULT_SYSTEM_PROMPT

    def build_background_prompt(self, search_results: str) -> str:
        return BACKGROUND_SUMMARY_PROMPT + "\n\n搜索结果如下：\n" + search_results

    def build_article_prompt(
        self, game_name: str, event_desc: str,
        style: str = "默认", custom_style: Optional[str] = None,
        character_bg: Optional[str] = None, event_bg: Optional[str] = None,
    ) -> str:
        if not game_name:
            game_name = "游戏"
        if not event_desc:
            event_desc = "相关事件"

        parts = []

        if character_bg and character_bg.strip() and character_bg.strip() != "无":
            parts.append(f"【角色背景】\n{character_bg.strip()}")
        elif character_bg:
            parts.append("【角色背景】\n（无特定角色信息）")

        if event_bg and event_bg.strip():
            parts.append(f"【事件背景】\n{event_bg.strip()}")

        parts.append(
            f"【任务】\n游戏：{game_name}\n事件：{event_desc}\n\n"
            "请根据上述信息，撰写一篇符合风格要求的深度游戏评论文章新闻稿。"
        )

        base_prompt = "\n\n".join(parts)

        if custom_style:
            return (
                base_prompt + "\n\n"
                f"【自定义风格要求】{custom_style}\n\n"
                "请严格按照上述自定义风格要求来撰写文章，同时保持对游戏的热爱和吹捧立场。"
            )

        style_modifier, _, _ = self._style_manager.get_style(style)
        if style_modifier:
            return base_prompt + f"\n\n【风格要求】{style_modifier}"

        return base_prompt
