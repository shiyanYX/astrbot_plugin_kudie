"""
搜索词优化器
使用 LLM 将用户输入优化为更精准的搜索关键词
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)


class SearchOptimizer:
    """搜索词优化器"""

    OPTIMIZE_PROMPT = """你是一个搜索词优化器。将用户关于游戏事件的描述，优化为适合在贴吧搜索的关键词。

规则：
1. 保留游戏名
2. 提取核心争议点/事件关键词
3. 用空格分隔多个关键词
4. 只输出搜索词，不要任何解释

示例：
输入: 鸣潮 有人黑角色西格莉卡绑男角色仇远所以不抽西格莉卡
输出: 鸣潮 西格莉卡 仇远 绑定 争议

输入: 原神 3.0版本须弥开放
输出: 原神 须弥 3.0 版本更新

输入: {game} {event}
输出:"""

    def __init__(self, llm_generate_func):
        """
        Args:
            llm_generate_func: 异步函数，签名: async def(prompt: str) -> str
        """
        self._generate = llm_generate_func

    async def optimize(self, game_name: str, event_desc: str, umo=None) -> str:
        """
        优化搜索词

        Args:
            game_name: 游戏名
            event_desc: 事件描述
            umo: unified_msg_origin，用于自动获取 LLM provider

        Returns:
            优化后的搜索关键词字符串
        """
        prompt = self.OPTIMIZE_PROMPT.format(game=game_name, event=event_desc)
        try:
            result = await self._generate(prompt, umo) if umo else await self._generate(prompt)
            if result:
                return result.strip()
        except Exception as e:
            logger.warning(f"搜索词优化失败: {e}")
        # 降级：直接拼原始输入
        return f"{game_name} {event_desc}".strip()
