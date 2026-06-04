"""
Wiki 角色搜索爬虫
来源: 萌娘百科(moegirl.org.cn) / B站Wiki(wiki.biligame.com) / 自动选择
提取角色基本信息: 性别、年龄、角色类型
"""
import re, time, random, logging, ssl, gzip
from urllib.request import Request, build_opener, HTTPSHandler
from urllib.parse import quote_plus, unquote
from urllib.error import HTTPError

logger = logging.getLogger(__name__)

_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36"

# 游戏 → B站Wiki 子域名映射（已验证上线）
_GAME_WIKI_MAP = {
    "鸣潮": "wutheringwaves",
    "原神": "ys",
    "崩坏星穹铁道": "sr",
    "星穹铁道": "sr",
    "崩坏3": "bh3",
    "崩坏3rd": "bh3",
    "绝区零": "zzz",
    "明日方舟": "arknights",
    "碧蓝航线": "blhx",
    "卡拉彼丘": "klbq",
    "无限暖暖": "infinitynikkigf",
    "王者荣耀": "pvp",
    "第五人格": "id5",
    "FGO": "fgo",
    "战双帕弥什": "pgr",
    "重返未来1999": "reverse1999",
    "少女前线": "gfwiki",
    "蔚蓝档案": "ba",
    "幻塔": "ht",
    "尘白禁区": "cbjq",
    "无期迷途": "wqmt",
}

def _log(msg, debug=False):
    if not debug: return
    logger.debug(msg)
    print(f"  [WIKI] {msg}")

def _fetch(url, t=10):
    req = Request(url, headers={
        "User-Agent": _UA,
        "Accept": "text/html,application/xhtml+xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-CN,zh;q=0.9",
    })
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
    ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    o = build_opener(HTTPSHandler(context=ctx))
    try:
        r = o.open(req, timeout=t)
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip": raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="ignore")
    except Exception as e:
        _log(f"fetch: {e}")
        return ""


class WikiCrawler:
    """角色百科爬虫"""

    def __init__(self, wiki_source="auto", timeout=10):
        self._source = wiki_source
        self._t = timeout

    def _get_wiki(self, game: str) -> str:
        """获取游戏对应的 B站Wiki 子域名"""
        for g, code in _GAME_WIKI_MAP.items():
            if g in game or game in g:
                return code
        # 回退: 用游戏名拼音
        _log(f"  未找到 {game} 的Wiki映射，尝试直接搜索")
        return game

    def search_character(self, game: str, character: str) -> str:
        """搜索角色基本信息 (B站Wiki)"""
        wiki_code = self._get_wiki(game)
        _log(f"搜索: {game}/{character} -> wiki.biligame.com/{wiki_code}")
        return self._search_bwiki(wiki_code, character)

    def _search_bwiki(self, wiki_code: str, character: str) -> str:
        """B站Wiki搜索角色信息"""
        url = f"https://wiki.biligame.com/{wiki_code}/{quote_plus(character)}"
        _log(f"  {url}")
        html = _fetch(url, t=self._t)
        if not html or len(html) < 500:
            return ""

        info_parts = []

        # 信息框提取
        for label, key in [
            (r"性别", "性别"),
            (r"年龄", "年龄"),
            (r"身高", "身高"),
            (r"称号", "称号"),
            (r"武器", "武器"),
            (r"所属", "所属"),
            (r"生日", "生日"),
            (r"种族", "种族"),
        ]:
            pat = re.compile(rf'{label}[：:]\s*([^<>\n]{{1,50}})', re.IGNORECASE)
            m = pat.search(html)
            if m:
                val = m.group(1).strip()
                # 清理B站Wiki模板语法
                val = re.sub(r'\{\{[^}]*\}\}', '', val).strip()
                if val:
                    info_parts.append(f"{key}: {val}")

        # 简介
        intro = ""
        for pat in [r'<p>(.{50,300}?)</p>', r'<div[^>]*class="[^"]*desc[^"]*"[^>]*>(.{50,300}?)</div>']:
            im = re.search(pat, html, re.DOTALL)
            if im:
                intro = re.sub(r'<[^>]+>', '', im.group(1)).strip()
                intro = re.sub(r'\s+', ' ', intro)
                if len(intro) > 30: break

        if info_parts or intro:
            result = f"{character}:\n"
            if info_parts:
                result += "  " + ", ".join(info_parts) + "\n"
            if intro:
                result += "  " + intro[:200]
            return result.strip()
        return ""


if __name__ == "__main__":
    # 快速自测
    w = WikiCrawler()
    for g, c in [("卡拉彼丘", "令"), ("原神", "钟离"), ("鸣潮", "漂泊者")]:
        print(f"\n{'='*40}")
        r = w.search_character(g, c)
