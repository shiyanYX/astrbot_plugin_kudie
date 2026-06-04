"""
尽孝插件 - AstrBot 游戏评论生成插件 v2.0.0
热爱游戏，把游戏公司当父亲尽孝的人

版本: 2.0.0
作者: NumInvis
仓库: https://github.com/NumInvis/astrbot_plugin_kudie
"""

from ._version import __version__, __plugin_name__, __plugin_desc__, __author__
from .main import KudiePlugin

__all__ = ["KudiePlugin", "__version__", "__plugin_name__", "__plugin_desc__", "__author__"]
