"""
尽孝插件主逻辑
v2.1.0 — 新增搜索链路（贴吧爬虫 + 双LLM调用 + 扫码登录）
"""

import asyncio
import re
from pathlib import Path
from typing import Optional

from astrbot.api import logger
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register

from ._version import __version__, __plugin_name__, __plugin_desc__, __author__
from .core.config_manager import ConfigManager
from .core.style_manager import StyleManager
from .core.prompt_builder import PromptBuilder
from .core.article_generator import ArticleGenerator
from .core.history_manager import HistoryManager
from .core.search.tieba_crawler import TiebaCrawler
from .core.search.cache_manager import CacheManager
from .core.search.qrlogin import TiebaQRLogin


@register(__plugin_name__, __author__, __plugin_desc__, __version__)
class WwkudiePlugin(Star):
    """尽孝插件主类"""

    def __init__(self, context: Context):
        super().__init__(context)
        data_dir = Path(__file__).parent / "data"
        self._config = ConfigManager(context)
        self._style_manager = StyleManager()
        self._prompt_builder = PromptBuilder(self._style_manager)
        self._cache = CacheManager(
            data_dir=data_dir,
            event_ttl=self._config.get("cache_event_ttl", 600),
            character_ttl=self._config.get("cache_character_ttl", 604800),
        )
        self._crawler = TiebaCrawler(
            bduss=self._config.get("tieba_bduss", ""),
            stoken=self._config.get("tieba_stoken", ""),
            baiduid=self._config.get("tieba_baiduid", ""),
            search_engine=self._config.get("search_engine", "baidu"),
            timeout=self._config.get("search_timeout", 15),
            max_retries=3,
        )
        self._generator = ArticleGenerator(
            context=context,
            config_manager=self._config,
            prompt_builder=self._prompt_builder,
            crawler=self._crawler,
            cache_manager=self._cache,
        )
        self._history = HistoryManager(
            data_dir=data_dir,
            max_history_per_user=self._config.get("max_history_per_user", 10),
        )
        logger.info(f"尽孝插件 v{__version__} 已初始化（搜索+扫码登录模块已加载）")

    def _parse_article_args(self, content: str) -> tuple:
        """解析文章生成命令参数"""
        if not content:
            return "", "", self._config.get("default_style", "默认"), ""
        parts = content.split()
        if len(parts) < 2:
            return "", "", self._config.get("default_style", "默认"), ""
        game_name = parts[0]
        diy_index = None
        for i, part in enumerate(parts):
            if part.lower() == "diy":
                diy_index = i
                break
        if diy_index is not None and diy_index >= 2:
            event_desc = " ".join(parts[1:diy_index])
            custom_style = " ".join(parts[diy_index + 1:]) if diy_index + 1 < len(parts) else ""
            return game_name, event_desc, "diy", custom_style
        potential_style = parts[-1]
        is_known_style = self._style_manager.is_valid_style(potential_style)
        if is_known_style and len(parts) >= 3:
            event_desc = " ".join(parts[1:-1])
            style = potential_style
        else:
            event_desc = " ".join(parts[1:])
            style = self._config.get("default_style", "默认")
        return game_name, event_desc, style, ""

    # ==================== 命令处理 ====================

    @filter.command("尽孝")
    async def wwkudie_command(self, event: AstrMessageEvent):
        """尽孝命令 - 普通链路"""
        user_id = event.get_sender_id()
        content = event.message_str.strip()
        if not content:
            yield event.plain_result(
                "请提供游戏名和事件描述！\n"
                "使用方式：/尽孝 游戏名 事件描述 [风格/diy 自定义风格]\n\n"
                "可用风格：/尽孝风格"
            )
            return
        game_name, event_desc, style, custom_style = self._parse_article_args(content)
        if not game_name or not event_desc:
            yield event.plain_result(
                "请提供游戏名和事件描述！\n"
                "使用方式：/尽孝 游戏名 事件描述 [风格/diy 自定义风格]\n\n"
                "可用风格：/尽孝风格"
            )
            return
        if style == "diy":
            style_display = f"DIY:{custom_style[:20]}..." if len(custom_style) > 20 else f"DIY:{custom_style}"
        else:
            _, _, icon = self._style_manager.get_style(style)
            style_display = f"{icon} {style}" if style != "默认" else "默认风格"
        yield event.plain_result(f"🖊 正在尽孝... [{style_display}]")
        success, result = await self._generator.generate(
            event=event, game_name=game_name, event_desc=event_desc,
            style=style, custom_style=custom_style if style == "diy" else None,
        )
        if success:
            if self._config.get("enable_history", True):
                self._history.add_record(
                    user_id=user_id, game_name=game_name, event_desc=event_desc,
                    style=style if style != "diy" else f"diy:{custom_style}", article=result,
                )
            yield event.plain_result(result)
        else:
            yield event.plain_result(result)

    @filter.command("尽孝搜索")
    async def wwkudie_search(self, event: AstrMessageEvent):
        """尽孝搜索 - 搜索链路"""
        user_id = event.get_sender_id()
        content = event.message_str.strip()
        if not content:
            yield event.plain_result(
                "请提供游戏名和事件描述！\n"
                "使用方式：/尽孝搜索 游戏名 事件描述 [风格/diy 自定义风格]"
            )
            return
        game_name, event_desc, style, custom_style = self._parse_article_args(content)
        if not game_name or not event_desc:
            yield event.plain_result(
                "请提供游戏名和事件描述！\n"
                "使用方式：/尽孝搜索 游戏名 事件描述 [风格/diy 自定义风格]"
            )
            return
        if style == "diy":
            style_display = f"DIY:{custom_style[:20]}..." if len(custom_style) > 20 else f"DIY:{custom_style}"
        else:
            _, _, icon = self._style_manager.get_style(style)
            style_display = f"{icon} {style}" if style != "默认" else "默认风格"
        yield event.plain_result(f"🔍 正在搜索最新信息... [{style_display}]")
        success, result = await self._generator.generate_with_search(
            event=event, game_name=game_name, event_desc=event_desc,
            style=style, custom_style=custom_style if style == "diy" else None,
        )
        if success:
            if self._config.get("enable_history", True):
                self._history.add_record(
                    user_id=user_id, game_name=game_name, event_desc=event_desc,
                    style=style if style != "diy" else f"diy:{custom_style}", article=result,
                )
            yield event.plain_result(result)
        else:
            yield event.plain_result(result)

    @filter.command("尽孝风格")
    async def wwkudie_styles(self, event: AstrMessageEvent):
        """显示所有可用风格"""
        styles = self._style_manager.get_all_styles()
        lines = ["🎨 尽孝插件 - 可用风格列表\n"]
        for i, style in enumerate(styles, 1):
            name = style["name"]
            desc = style["description"]
            alias = ", ".join(style["alias"])
            icon = style.get("icon", "✨")
            lines.append(f"{i}. {icon} 【{name}】{desc}")
            lines.append(f"   别名: {alias}\n")
        lines.extend([
            "\n🎨 DIY自定义风格：", "使用 diy 关键字+你的风格描述",
            "\n💡 使用方式：",
            "/尽孝 游戏名 事件描述 [风格]",
            "/尽孝 游戏名 事件 diy 你的风格要求",
            "\n示例：",
            "/尽孝 鸣潮 新角色上线 激烈反问",
            "/尽孝 原神 版本更新 diy 用鲁迅的口吻写",
        ])
        yield event.plain_result("\n".join(lines))

    @filter.command("尽孝历史")
    async def wwkudie_history(self, event: AstrMessageEvent):
        """查看历史记录"""
        if not self._config.get("enable_history", True):
            yield event.plain_result("❌ 历史记录功能未启用")
            return
        user_id = event.get_sender_id()
        records = self._history.get_history(user_id, limit=5)
        if not records:
            yield event.plain_result("📭 您还没有生成过尽孝文章")
            return
        lines = ["📜 您的尽孝历史记录\n"]
        for i, record in enumerate(records, 1):
            from datetime import datetime
            timestamp = datetime.fromtimestamp(record["timestamp"]).strftime("%m-%d %H:%M")
            game = record["game_name"]
            style = record["style"]
            event_desc = record["event_desc"]
            lines.append(f"{i}. [{timestamp}] {game}")
            lines.append(f"   风格: {style}")
            lines.append(f"   事件: {event_desc[:30]}...\n")
        lines.append(f"\n共 {len(records)} 条记录（最多保留 {self._config.get('max_history_per_user', 10)} 条）")
        yield event.plain_result("\n".join(lines))

    @filter.command("尽孝清除")
    async def wwkudie_clear(self, event: AstrMessageEvent):
        """清除历史记录"""
        if not self._config.get("enable_history", True):
            yield event.plain_result("❌ 历史记录功能未启用")
            return
        user_id = event.get_sender_id()
        success = self._history.clear_history(user_id)
        yield event.plain_result("✅ 已清除您的尽孝历史记录" if success else "📭 您还没有历史记录需要清除")

    @filter.command("尽孝状态")
    async def wwkudie_status(self, event: AstrMessageEvent):
        """查看插件状态"""
        lines = ["📊 尽孝插件状态", f"\n版本: v{__version__}", f"作者: {__author__}"]
        if self._config.get("enable_history", True):
            hs = self._history.get_stats()
            lines.extend(["\n历史记录:", f"📝 总记录数: {hs['total_records']}", f"👤 总用户数: {hs['total_users']}"])
        lines.append(f"\n🎨 可用风格数: {self._style_manager.get_style_count()}")
        yield event.plain_result("\n".join(lines))

    @filter.command("尽孝帮助")
    async def wwkudie_help(self, event: AstrMessageEvent):
        """显示帮助信息"""
        help_text = (
            "🎮 尽孝插件 v2.1.0 使用帮助\n\n"
            "📖 基础命令：\n"
            "/尽孝 游戏名 事件描述 [风格/diy 自定义风格]\n\n"
            "🔍 搜索命令：\n"
            "/尽孝搜索 游戏名 事件描述 [风格/diy 自定义风格]\n\n"
            "🔧 工具命令：\n"
            "/尽孝扫码 - 手机扫码登录贴吧（推荐）\n"
            "/尽孝登录 BDUSS=xxx - 手动配置贴吧Cookie\n"
            "/尽孝风格 - 查看所有可用风格\n"
            "/尽孝历史 - 查看生成历史\n"
            "/尽孝缓存 - 管理搜索缓存\n"
            "/尽孝状态 - 查看插件状态"
        )
        yield event.plain_result(help_text)


    @filter.command("尽孝扫码")
    async def wwkudie_qrlogin(self, event: AstrMessageEvent):
        """贴吧扫码登录"""
        try:
            qr = TiebaQRLogin(timeout=10)
            qr_data = qr.get_qrcode()
            yield event.plain_result("📱 请用百度App扫描下方二维码登录贴吧（2分钟内有效）：")
            from astrbot.api.message_components import Image
            yield event.chain_result([Image(file=qr_data["img_data"])])
            sign = qr_data["sign"]
            for _ in range(60):
                await asyncio.sleep(2)
                try:
                    status = qr.poll(sign)
                except Exception:
                    continue
                if status["status"] == "scanned":
                    yield event.plain_result("📱 已扫码，请在手机上确认登录...")
                elif status["status"] == "confirmed" and status["bduss"]:
                    yield event.plain_result("✅ 已确认！正在获取Cookie...")
                    result = qr.login(status["bduss"])
                    bduss = result["bduss"]
                    stoken = result.get("stoken", "")
                    baiduid = result.get("baiduid", "")
                    self._config.set("tieba_bduss", bduss)
                    if stoken:
                        self._config.set("tieba_stoken", stoken)
                    if baiduid:
                        self._config.set("tieba_baiduid", baiduid)
                    self._crawler = TiebaCrawler(
                        bduss=bduss, stoken=stoken, baiduid=baiduid,
                        search_engine=self._config.get("search_engine", "baidu"),
                        timeout=self._config.get("search_timeout", 15),
                    )
                    self._generator._crawler = self._crawler
                    yield event.plain_result("🎉 贴吧扫码登录成功！现在可以使用 /尽孝搜索 了")
                    return
            yield event.plain_result("⏰ 扫码超时，请重新使用 /尽孝扫码")
        except Exception as e:
            logger.error(f"扫码登录失败: {e}")
            yield event.plain_result(f"❌ 扫码登录失败: {e}")

    @filter.command("尽孝登录")
    async def wwkudie_login(self, event: AstrMessageEvent):
        """手动设置贴吧 Cookie"""
        content = event.message_str.strip()
        if not content:
            yield event.plain_result(
                "🔑 /尽孝登录 BDUSS=xxx STOKEN=xxx\n"
                "💡 推荐 /尽孝扫码 一键登录！"
            )
            return
        bduss = ""
        stoken = ""
        m = re.search(r'BDUSS=([^\s;]+)', content)
        if m:
            bduss = m.group(1)
        m = re.search(r'STOKEN=([^\s;]+)', content)
        if m:
            stoken = m.group(1)
        if bduss:
            self._config.set("tieba_bduss", bduss)
            if stoken:
                self._config.set("tieba_stoken", stoken)
            self._crawler = TiebaCrawler(
                bduss=bduss, stoken=stoken,
                search_engine=self._config.get("search_engine", "baidu"),
                timeout=self._config.get("search_timeout", 15),
            )
            self._generator._crawler = self._crawler
            yield event.plain_result("✅ 贴吧Cookie已保存！")
        else:
            yield event.plain_result("❌ 未找到BDUSS值")

    @filter.command("尽孝缓存")
    async def wwkudie_cache(self, event: AstrMessageEvent):
        """缓存管理"""
        content = event.message_str.strip()
        if content == "清除":
            self._cache.clear_all()
            yield event.plain_result("✅ 所有搜索缓存已清除")
        elif content == "事件":
            self._cache.clear_event_cache()
            yield event.plain_result("✅ 事件搜索缓存已清除")
        elif content == "角色":
            self._cache.clear_character_cache()
            yield event.plain_result("✅ 角色信息缓存已清除")
        else:
            yield event.plain_result(
                "📦 /尽孝缓存 清除/事件/角色"
            )
