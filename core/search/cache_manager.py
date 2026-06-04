"""
缓存管理器
事件搜索结果短期缓存 + 角色信息长期缓存
"""
import json
import time
import hashlib
import logging
from pathlib import Path
from typing import Optional

logger = logging.getLogger(__name__)


class CacheManager:
    """搜索结果和角色信息缓存"""

    def __init__(
        self,
        data_dir: Path,
        event_ttl: int = 600,
        character_ttl: int = 604800,
    ):
        """
        Args:
            data_dir: 缓存文件存储目录
            event_ttl: 事件缓存有效期（秒），默认 10 分钟
            character_ttl: 角色缓存有效期（秒），默认 7 天
        """
        self._data_dir = data_dir
        self._data_dir.mkdir(parents=True, exist_ok=True)
        self._event_ttl = event_ttl
        self._character_ttl = character_ttl

        self._event_cache: dict = {}
        self._character_cache: dict = {}

        self._event_file = self._data_dir / "event_cache.json"
        self._character_file = self._data_dir / "character_cache.json"

        self._load()

    # ── 事件缓存 ─────────────────────────────────────────

    def _event_key(self, game: str, event: str) -> str:
        raw = f"{game}|||{event}".lower()
        return hashlib.md5(raw.encode()).hexdigest()

    def get_event(self, game: str, event: str) -> Optional[str]:
        """获取缓存的事件搜索结果"""
        key = self._event_key(game, event)
        entry = self._event_cache.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > self._event_ttl:
            del self._event_cache[key]
            return None
        return entry["data"]

    def set_event(self, game: str, event: str, data: str):
        """缓存事件搜索结果"""
        key = self._event_key(game, event)
        self._event_cache[key] = {"ts": time.time(), "data": data}
        self._save_events()

    # ── 角色缓存 ─────────────────────────────────────────

    def _character_key(self, game: str, character: str) -> str:
        raw = f"{game}|||{character}".lower()
        return hashlib.md5(raw.encode()).hexdigest()

    def get_character(self, game: str, character: str) -> Optional[str]:
        """获取缓存的角色信息"""
        key = self._character_key(game, character)
        entry = self._character_cache.get(key)
        if not entry:
            return None
        if time.time() - entry["ts"] > self._character_ttl:
            del self._character_cache[key]
            return None
        return entry["data"]

    def set_character(self, game: str, character: str, data: str):
        """缓存角色信息"""
        key = self._character_key(game, character)
        self._character_cache[key] = {"ts": time.time(), "data": data}
        self._save_characters()

    # ── 持久化 ───────────────────────────────────────────

    def _save_events(self):
        try:
            self._event_file.write_text(
                json.dumps(self._event_cache, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存事件缓存失败: {e}")

    def _save_characters(self):
        try:
            self._character_file.write_text(
                json.dumps(self._character_cache, ensure_ascii=False),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"保存角色缓存失败: {e}")

    def _load(self):
        # 加载事件缓存
        try:
            if self._event_file.exists():
                self._event_cache = json.loads(
                    self._event_file.read_text(encoding="utf-8")
                )
        except Exception as e:
            logger.warning(f"加载事件缓存失败: {e}")
            self._event_cache = {}

        # 加载角色缓存
        try:
            if self._character_file.exists():
                self._character_cache = json.loads(
                    self._character_file.read_text(encoding="utf-8")
                )
        except Exception as e:
            logger.warning(f"加载角色缓存失败: {e}")
            self._character_cache = {}

    def clear_event_cache(self):
        """清除事件缓存"""
        self._event_cache.clear()
        try:
            self._event_file.unlink(missing_ok=True)
        except Exception:
            pass

    def clear_character_cache(self):
        """清除角色缓存"""
        self._character_cache.clear()
        try:
            self._character_file.unlink(missing_ok=True)
        except Exception:
            pass

    def clear_all(self):
        """清除所有缓存"""
        self.clear_event_cache()
        self.clear_character_cache()

    def get_event_cache_age(self, game: str, event: str) -> Optional[float]:
        """获取事件缓存年龄（秒），没有缓存返回 None"""
        key = self._event_key(game, event)
        entry = self._event_cache.get(key)
        if entry:
            age = time.time() - entry["ts"]
            return age if age < self._event_ttl else None
        return None
