"""
文章生成器 v2.1.0
处理 LLM 调用和响应解析
支持普通链路（纯LLM）和搜索链路（双LLM调用）
"""

import asyncio
import re
from typing import Any, Optional

from astrbot.api import logger
from astrbot.api.event import AstrMessageEvent
from astrbot.api.star import Context

from .config_manager import ConfigManager
from .prompt_builder import PromptBuilder
from .style_manager import StyleManager
from .search.tieba_crawler import TiebaCrawler
from .search.search_optimizer import SearchOptimizer
from .search.cache_manager import CacheManager



class LLMResponseParser:
    """LLM 响应解析器"""

    @staticmethod
    def parse(response: Any) -> Optional[str]:
        if response is None:
            return None
        if hasattr(response, 'completion_text') and response.completion_text:
            return response.completion_text
        if hasattr(response, 'text') and response.text:
            return response.text
        if hasattr(response, 'content') and response.content:
            return response.content
        if hasattr(response, 'message') and response.message:
            return response.message
        if isinstance(response, dict):
            for key in ['completion_text', 'text', 'content', 'message', 'response']:
                if key in response and response[key]:
                    return str(response[key])
            return str(response) if response else None
        if isinstance(response, str):
            return response if response.strip() else None
        try:
            text = str(response)
            return text if text and text not in ['None', 'null', ''] else None
        except Exception:
            return None


class ArticleGenerator:
    """文章生成器——支持普通链路和搜索链路"""

    def __init__(
        self,
        context: Context,
        config_manager: ConfigManager,
        prompt_builder: PromptBuilder,
        crawler: Optional[TiebaCrawler] = None,
        cache_manager: Optional[CacheManager] = None,
    ):
        self._context = context
        self._config = config_manager
        self._prompt_builder = prompt_builder
        self._parser = LLMResponseParser()
        self._crawler = crawler
        self._cache = cache_manager
        self._search_optimizer = SearchOptimizer(self._llm_generate_plain)

    async def _llm_generate_plain(self, prompt: str, umo=None) -> str:
        """不带风格的纯 LLM 调用，用于搜索词优化和背景摘要"""
        try:
            provider_id = self._config.get("provider_id")
            if not provider_id:
                if umo is not None:
                    provider_id = await self._context.get_current_chat_provider_id(umo=umo)
                    if provider_id:
                        self._config.set("provider_id", provider_id)
                if not provider_id:
                    logger.warning("LLM provider_id 未设置，跳过优化")
                    return ""
            llm_resp = await self._context.llm_generate(
                chat_provider_id=provider_id, prompt=prompt,
            )
            return self._parser.parse(llm_resp) or ""
        except Exception as e:
            logger.error(f"LLM 调用失败: {e}")
            return ""

    async def generate(
        self, event: AstrMessageEvent, game_name: str, event_desc: str,
        style: str = "默认", custom_style: Optional[str] = None,
    ) -> tuple:
        """普通链路：纯 LLM 生成（用缓存数据）"""
        character_bg = None
        if self._cache:
            character_bg = self._cache.get_character(game_name, event_desc)
        return await self._generate_article(
            event=event, game_name=game_name, event_desc=event_desc,
            style=style, custom_style=custom_style, character_bg=character_bg,
        )

    async def generate_with_search(
        self, event: AstrMessageEvent, game_name: str, event_desc: str,
        style: str = "默认", custom_style: Optional[str] = None,
    ) -> tuple:
        """搜索链路：实时搜索贴吧 → LLM 加工背景 → LLM 写文章"""
        character_bg = None
        event_bg = None

        cached_event = None
        if self._cache:
            cached_event = self._cache.get_event(game_name, event_desc)

        if cached_event:
            event_bg = cached_event
            logger.info("使用缓存的事件背景")
        elif self._crawler:
            search_mode = self._config.get("search_query_mode", "llm")
            if search_mode == "llm":
                keyword = await self._search_optimizer.optimize(game_name, event_desc, event.unified_msg_origin)
            else:
                keyword = f"{game_name} {event_desc}"
            logger.info(f"搜索关键词: {keyword}")

            search_text = self._crawler.get_hot_posts(
                keyword,
                max_search=self._config.get("search_max_posts", 10),
                max_content=self._config.get("search_max_comments", 5),
            )
            if search_text:
                preview = search_text[:200].replace("\n", " ")
                logger.info(f"爬虫返回 {len(search_text)} 字符: {preview}...")
            else:
                logger.info("爬虫返回: 空结果")

            if search_text:
                bg_prompt = self._prompt_builder.build_background_prompt(search_text)
                bg_summary = await self._llm_generate_plain(bg_prompt, event.unified_msg_origin)

                if bg_summary:
                    char_bg, evt_bg = self._parse_background_summary(bg_summary)
                    character_bg = char_bg
                    event_bg = evt_bg

                    if self._cache:
                        if event_bg:
                            self._cache.set_event(game_name, event_desc, event_bg)
                        if character_bg and character_bg.strip() and character_bg.strip() != "无":
                            self._cache.set_character(game_name, event_desc, character_bg)

        if not character_bg and not event_bg:
            logger.info("搜索未获取到有效信息，降级为纯 LLM")
            if self._cache:
                character_bg = self._cache.get_character(game_name, event_desc)

        success, text = await self._generate_article(
            event=event, game_name=game_name, event_desc=event_desc,
            style=style, custom_style=custom_style,
            character_bg=character_bg, event_bg=event_bg,
        )

        if success and not event_bg and not cached_event:
            text += "\n\n⚠️ 未获取到最新信息"
        return success, text

    async def _generate_article(
        self, event: AstrMessageEvent, game_name: str, event_desc: str,
        style: str = "默认", custom_style: Optional[str] = None,
        character_bg: Optional[str] = None, event_bg: Optional[str] = None,
    ) -> tuple:
        """文章生成核心（第二次 LLM 调用）"""
        try:
            system_prompt = self._prompt_builder.build_system_prompt(
                self._config.get("system_prompt")
            )
            user_prompt = self._prompt_builder.build_article_prompt(
                game_name=game_name, event_desc=event_desc,
                style=style, custom_style=custom_style,
                character_bg=character_bg, event_bg=event_bg,
            )
            full_prompt = f"{system_prompt}\n\n{user_prompt}"

            umo = event.unified_msg_origin
            provider_id = await self._context.get_current_chat_provider_id(umo=umo)
            if not provider_id:
                self._config.set("provider_id", provider_id)
                return False, "❌ 错误：未找到 LLM 提供商"
            self._config.set("provider_id", provider_id)

            llm_resp = await self._context.llm_generate(
                chat_provider_id=provider_id, prompt=full_prompt,
            )
            response_text = self._parser.parse(llm_resp)
            if response_text:
                return True, response_text
            elif llm_resp is None:
                return False, "❌ 生成失败：AI没有返回响应"
            else:
                return False, "❌ 生成失败：无法解析AI响应"
        except asyncio.TimeoutError:
            return False, "⏰ 生成超时，请稍后再试"
        except Exception as e:
            logger.error(f"文章生成错误: {e}", exc_info=True)
            return False, self._format_error_message(e)

    @staticmethod
    def _parse_background_summary(summary: str) -> tuple:
        """解析背景摘要，分离角色背景和事件背景"""
        char_bg = None
        event_bg = None
        char_match = re.search(
            r"【角色背景】\s*\n(.*?)(?=【事件背景】|$)",
            summary, re.DOTALL,
        )
        if char_match:
            char_bg = char_match.group(1).strip()
        event_match = re.search(
            r"【事件背景】\s*\n(.*?)$",
            summary, re.DOTALL,
        )
        if event_match:
            event_bg = event_match.group(1).strip()
        return char_bg, event_bg

    @staticmethod
    def _format_error_message(error: Exception) -> str:
        error_message = str(error).lower()
        if "rate" in error_message or "limit" in error_message:
            return "🚫 API调用频率限制，请稍后再试"
        elif "connect" in error_message or "network" in error_message:
            return "🔌 网络连接失败"
        elif "timeout" in error_message:
            return "⏰ 生成超时"
        elif "auth" in error_message or "key" in error_message:
            return "🔑 API认证失败"
        elif "quota" in error_message or "billing" in error_message:
            return "💳 API额度不足"
        elif "content" in error_message or "policy" in error_message:
            return "🛡️ 内容被安全策略拦截"
        else:
            return "❌ 生成失败，请稍后重试"
