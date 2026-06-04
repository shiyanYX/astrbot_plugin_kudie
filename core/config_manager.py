"""
配置管理器
处理 AstrBot 配置系统的读取和缓存
"""

from typing import Any
from astrbot.api import logger


class ConfigManager:
    """AstrBot 配置管理器"""

    DEFAULTS = {
        "default_style": "默认",
        "system_prompt": None,
        "enable_debug": False,
        "enable_history": True,
        "max_history_per_user": 10,
        "search_query_mode": "llm",
        "search_engine": "baidu",
        "search_timeout": 15,
        "search_max_posts": 10,
        "search_max_comments": 5,
        "cache_event_ttl": 600,
        "cache_character_ttl": 604800,
        "enable_wiki_search": True,
        "wiki_sources": "auto",
        "tieba_bduss": "",
        "tieba_stoken": "",
        "tieba_baiduid": "",
        "provider_id": None,
    }

    def __init__(self, context: Any):
        self._context = context
        self._cache = {}
        self._cache_valid = False
        self._plugin_name = "astrbot_plugin_kudie"
        self._runtime = {}

    def _load_config(self):
        try:
            config = {}
            if hasattr(self._context, "config") and isinstance(self._context.config, dict):
                plugin_config = self._context.config.get(self._plugin_name, {})
                if plugin_config:
                    config.update(plugin_config)
            return config
        except Exception as e:
            logger.warning(f"加载配置失败: {e}")
            return {}

    def get(self, key, default=None):
        if self._cache_valid and key in self._cache:
            return self._cache[key]
        config = self._load_config()
        if key in config:
            self._cache[key] = config[key]
            return config[key]
        return self.DEFAULTS.get(key, default)

    def get_all(self):
        config = self._load_config()
        result = dict(self.DEFAULTS)
        result.update(config)
        return result

    def set(self, key, value):
        self._cache[key] = value
        self._runtime[key] = value

    def save(self):
        """持久化配置到 AstrBot"""
        try:
            if hasattr(self._context, "config") and isinstance(self._context.config, dict):
                if self._plugin_name not in self._context.config:
                    self._context.config[self._plugin_name] = {}
                self._context.config[self._plugin_name].update(self._runtime)
            # 同时写入 runtime 到 _cache，确保 get() 能读到最新值
            self._cache.update(self._runtime)
            self._cache_valid = True
            logger.info("配置已持久化")
        except Exception as e:
            logger.warning(f"持久化配置失败: {e}")

    def invalidate_cache(self):
        self._cache_valid = False
        self._cache.clear()

    def reload(self):
        self.invalidate_cache()
        config = self._load_config()
        self._cache = dict(self.DEFAULTS)
        self._cache.update(config)
        self._cache_valid = True
        logger.info("配置已重新加载")
