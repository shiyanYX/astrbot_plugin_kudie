"""贴吧爬虫 v2.3.0"""
import re, time, random, logging, ssl, gzip, os
from typing import Optional
from urllib.request import Request, build_opener, HTTPSHandler
from urllib.parse import urlencode, quote, quote_plus, unquote
from urllib.error import HTTPError

logger = logging.getLogger(__name__)
_UA = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 14_0 like Mac OS X) AppleWebKit/605.1.15",
]
def _log(msg): logger.info(msg); print(f"  [LOG] {msg}")

def _fetch(url, headers=None, data=None, cookie_str="", t=15):
    h = dict(headers) if headers else {}
    h.setdefault("User-Agent", random.choice(_UA))
    h.setdefault("Accept","text/html,application/xhtml+xml;q=0.9,*/*;q=0.8")
    h.setdefault("Accept-Language","zh-CN,zh;q=0.9")
    h.setdefault("Accept-Encoding","gzip, deflate")
    if cookie_str: h["Cookie"] = cookie_str
    req = Request(url, data=data, headers=h)
    ctx = ssl.create_default_context()
    ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE; ctx.minimum_version = ssl.TLSVersion.TLSv1_2
    o = build_opener(HTTPSHandler(context=ctx))
    try:
        r = o.open(req, timeout=t)
        raw = r.read()
        if r.headers.get("Content-Encoding") == "gzip": raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="ignore")
    except HTTPError as e:
        if e.code in (403,404,410): _log(f"  HTTP {e.code}"); return ""
        raw = e.read()
        if e.headers.get("Content-Encoding") == "gzip": raw = gzip.decompress(raw)
        return raw.decode("utf-8", errors="ignore")
    except Exception as e:
        _log(f"  fetch: {e}"); return ""

class TiebaCrawler:
    BING_RSS = "https://www.bing.com/search?format=rss"
    BING_SEARCH = "https://www.bing.com/search"
    TIEBA_POST = "https://tieba.baidu.com/mo/q/m"

    def __init__(self, bduss="", stoken="", baiduid="", tiebauid="", timeout=15):
        self._bd = bduss; self._st = stoken; self._ba = baiduid; self._ti = tiebauid
        self._t = timeout
        _log(f"Crawler timeout={timeout}s bduss={'Y' if bduss else 'N'}")

    @property
    def _cookie(self):
        p = []
        if self._bd: p.append(f"BDUSS={self._bd}")
        if self._st: p.append(f"STOKEN={self._st}")
        if self._ba: p.append(f"BAIDUID={self._ba}")
        if self._ti: p.append(f"TIEBAUID={self._ti}")
        return "; ".join(p)

    def _ua(self, mobile=False): return _UA[1] if mobile else random.choice(_UA)
    def _h(self, mobile=False): return {"User-Agent": self._ua(mobile=mobile)}
    def _delay(self): time.sleep(random.uniform(0.2, 0.8))

    def search(self, kw, mr=10):
        _log(f"Search: '{kw}'")
        r = self._native(kw, mr)
        if r: return r
        q = f"{kw} 贴吧"
        r = self._bing_rss(q, mr)
        if r: return r
        r = self._bing_html(q, mr)
        if r: return r
        _log("All failed"); return []

    def _native(self, kw, mr):
        p = kw.split()
        g = p[0] if p else kw
        qs = []
        if len(p) > 1:
            c = p[1]; e = ' '.join([x for x in p[2:] if len(x) > 1][:2]) if len(p) > 2 else ''
            if e: qs.append((g, f"{c} {e}"))
            qs.append((g, c))
        qs.append(('all', kw))
        for sc, q in qs:
            kp = quote_plus(g) if sc != 'all' else ''
            url = f"https://tieba.baidu.com/mo/q/search/thread?kw={kp}&word={quote_plus(q)}&rn={mr}"
            _log(f"  [{sc}] {url[:130]}")
            self._delay()
            html = _fetch(url, headers=self._h(mobile=True), cookie_str=self._cookie, t=self._t)
            _log(f"  {len(html)}B")
            if '安全验证' in html or len(html) < 500: continue
            tids = re.findall(r'"tid":"?(\d+)"?', html) + re.findall(r'kz=(\d+)', html)
            tids = list(dict.fromkeys(tids))
            if tids:
                rs = [{"title":"","url":f"https://tieba.baidu.com/p/{t}","snippet":"","tid":t} for t in tids[:mr]]
                for x in rs: _log(f'    post: {x["url"]}')
                return rs
        return []

    def _bing_rss(self, q, mr):
        url = f"{self.BING_RSS}&q={quote(q)}&count={mr+5}"
        self._delay(); html = _fetch(url, headers=self._h(), t=self._t)
        rs = []
        for it in re.findall(r'<item>(.*?)</item>', html, re.DOTALL):
            lm = re.search(r'<link>(.*?)</link>', it)
            link = lm.group(1) if lm else ""
            for tid in re.findall(r'tieba\.baidu\.com/p/(\d+)', link):
                tm = re.search(r'<title>(.*?)</title>', it)
                title = re.sub(r'<[^>]+>', '', tm.group(1)).strip() if tm else ""
                rs.append({"title":title,"url":link,"snippet":"","tid":tid})
                if len(rs) >= mr: break
        if not rs:
            for tid in re.findall(r'tieba\.baidu\.com/p/(\d+)', html):
                rs.append({"title":"","url":f"https://tieba.baidu.com/p/{tid}","snippet":"","tid":tid})
        return rs[:mr]

    def _bing_html(self, q, mr):
        url = f"{self.BING_SEARCH}?q={quote(q)}&count={mr+5}"
        self._delay(); html = _fetch(url, headers=self._h(), t=self._t)
        tids = re.findall(r'tieba\.baidu\.com/p/(\d+)', html)
        if not tids:
            for fm in re.findall(r'tieba\.baidu\.com/f\?kw=([^"\'\s&]+)', html):
                fh = _fetch(f"https://tieba.baidu.com/mo/q/m?kw={fm}", headers=self._h(mobile=True), cookie_str=self._cookie, t=self._t)
                tids += re.findall(r'"tid":"?(\d+)"?', fh) + re.findall(r'kz=(\d+)', fh)
        tids = list(dict.fromkeys(tids))
        return [{"title":"","url":f"https://tieba.baidu.com/p/{t}","snippet":"","tid":t} for t in tids[:mr]]

    def get_post(self, tid, page=1):
        url = f"{self.TIEBA_POST}?kz={tid}&pn={page}"
        _log(f"Post tid={tid}")
        self._delay()
        html = _fetch(url, headers=self._h(mobile=True), cookie_str=self._cookie, t=self._t)
        _log(f"  {len(html)}B")
        r = self._parse(html)
        if r: _log(f"  {r['floor_count']} floors")
        else: _log("  no content")
        return r

    def _parse(self, html):
        title = ""
        tm = re.search(r"<title>(.*?)</title>", html)
        if tm: title = tm.group(1).strip()
        if not title:
            ptm = re.search(r'class="post_title_text"[^>]*>(.*?)</', html, re.DOTALL)
            if ptm: title = re.sub(r'<[^>]+>', '', ptm.group(1)).strip()
        blocks = re.findall(r'<div[^>]*class="content"[^>]*>(.*?)</div>', html, re.DOTALL)
        posts = []
        for i, b in enumerate(blocks):
            c = re.sub(r'<[^>]+>', '', b).strip()
            c = re.sub(r'\s+', ' ', c)
            if not c or len(c) < 3 or '贴吧App' in c or '随时随地' in c:
                continue
            role = "OP" if i == 0 else f"L{i+1}"
            posts.append({"content":c,"author":"","floor":i+1,"role":role})
        return {"title":title,"floor_count":len(posts),"posts":posts} if posts else None

    def get_hot_posts(self, keyword, max_search=10, max_content=5):
        rs = self.search(keyword, max_search)
        if not rs: return ""
        lines = []
        for i, r in enumerate(rs):
            p = self.get_post(r['tid'])
            if not p or not p['posts']: continue
            lines.append(f"--- Post {i+1}: {p['title']} ---")
            lines.append(f"URL: {r['url']}\n")
            for pp in p['posts'][:max_content]:
                a = f"[{pp['author']}] " if pp['author'] else ""
                lines.append(f"{pp.get('role','')} {a}{pp['content']}")
            lines.append("")
        return "\n".join(lines) if lines else ""
