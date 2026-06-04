"""测试 Wiki 角色搜索 - 全部已配置游戏"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from core.search.wiki_crawler import WikiCrawler

w = WikiCrawler()

# 各游戏常见角色
tests = [
    ("鸣潮", "漂泊者"),
    ("原神", "钟离"),
    ("崩坏星穹铁道", "景元"),
    ("绝区零", "安比"),
    ("明日方舟", "阿米娅"),
    ("碧蓝航线", "企业"),
    ("卡拉彼丘", "令"),
    ("王者荣耀", "李白"),
    ("第五人格", "园丁"),
    ("FGO", "阿尔托莉雅"),
    ("战双帕弥什", "露西亚"),
    ("蔚蓝档案", "白子"),
    ("幻塔", "莎莉"),
]

for game, char in tests:
    print(f"\n{'='*40}")
    print(f"{game} / {char}")
    print('='*40)
    r = w.search_character(game, char)
    if r:
        print(r)
    else:
        print("  ⚠️ 未找到角色信息（页面可能不存在或网络不通）")

input("\n按回车退出...")
