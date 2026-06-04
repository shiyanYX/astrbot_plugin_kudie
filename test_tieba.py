"""
尽孝插件测试脚本 v2
测试贴吧搜索、帖子抓取功能
运行: python test_tieba.py
     python test_tieba.py search <关键词>
     python test_tieba.py hot <关键词>
"""
import sys
import os
import time
import json
import logging

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")

from core.search.qrlogin import TiebaQRLogin
from core.search.tieba_crawler import TiebaCrawler


def load_saved_cookies():
    cookie_file = os.path.join(SCRIPT_DIR, "test_cookies.json")
    if os.path.exists(cookie_file):
        with open(cookie_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_cookies(cookies):
    cookie_file = os.path.join(SCRIPT_DIR, "test_cookies.json")
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"Cookie 已保存: {cookie_file}")


def do_qr_login():
    print("\n" + "=" * 60)
    print("贴吧扫码登录")
    print("=" * 60)
    qr = TiebaQRLogin(timeout=10)
    qr_data = qr.get_qrcode()
    qr_path = os.path.join(SCRIPT_DIR, "qr_login.png")
    with open(qr_path, "wb") as f:
        f.write(qr_data["img_data"])
    print(f"\n二维码已保存: {qr_path}")
    print("请用百度App扫描二维码，然后在手机上点【确认登录】")
    print("等待扫码中...")
    sign = qr_data["sign"]
    for i in range(60):
        time.sleep(2)
        try:
            status = qr.poll(sign)
        except Exception as e:
            print(f"  轮询异常: {e}")
            continue
        if status["status"] == "scanned":
            print("   已扫码，请在手机上点【确认登录】...")
        elif status["status"] == "confirmed" and status["bduss"]:
            print("   已确认！获取Cookie中...")
            result = qr.login(status["bduss"])
            cookies = {
                "bduss": result["bduss"],
                "stoken": result.get("stoken", ""),
                "baiduid": result.get("baiduid", ""),
            }
            save_cookies(cookies)
            print(f"登录成功！BDUSS={cookies['bduss'][:40]}...")
            return cookies
        if i % 5 == 0:
            print(f"   [{i*2}s] 等待扫描...")
    print("扫码超时（2分钟）")
    return None


def create_crawler(cookies, debug=True):
    c = cookies or {}
    return TiebaCrawler(
        bduss=c.get("bduss", ""),
        stoken=c.get("stoken", ""),
        baiduid=c.get("baiduid", ""),
        timeout=15,
        debug=debug,
    )


def do_search(crawler, keyword):
    print(f"\n搜索: {keyword}")
    print("-" * 40)
    results = crawler.search(keyword, 10)
    if not results:
        print("无结果")
        return []
    print(f"找到 {len(results)} 条:\n")
    for i, r in enumerate(results, 1):
        title = r['title'][:80] if r['title'] else '(无标题)'
        print(f"  {i}. [{r['tid']}] {title}")
    print()
    return results


def do_fetch_post(crawler, tid):
    print(f"\n抓取帖子: {tid}")
    print("-" * 40)
    post = crawler.get_post(tid)
    if not post:
        print("获取失败")
        return None
    print(f"标题: {post['title']}")
    print(f"楼层: {post['floor_count']}")
    print(f"\n内容:")
    for p in post['posts'][:10]:
        role = p.get('role', f"#{p['floor']}")
        content = p['content'][:200]
        print(f"  {role}: {content}")
    print()
    return post


def do_hot_posts(crawler, keyword):
    print(f"\n完整搜索: {keyword}")
    print("-" * 40)
    text = crawler.get_hot_posts(keyword, max_search=10, max_content=5)
    if not text:
        print("未获取到内容")
        return
    print(f"获取到 {len(text)} 字符")
    print("\n--- 预览（前800字）---")
    print(text[:800])
    print("---")


def menu():
    cookies = load_saved_cookies()
    if cookies:
        print(f"\n已加载 Cookie: BDUSS={cookies.get('bduss','')[:40]}...")
        crawler = create_crawler(cookies)
    else:
        print("\n未找到 Cookie（无登录也可用 Bing 搜索）")
        crawler = create_crawler({})

    while True:
        print("\n" + "=" * 50)
        print("测试菜单")
        print("=" * 50)
        print("1. 扫码登录")
        print("2. 搜索帖子")
        print("3. 抓取指定帖子")
        print("4. 完整搜索（搜索+抓取内容）")
        print("5. 清除 Cookie")
        print("0. 退出")
        print("-" * 50)
        try:
            choice = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            new_cookies = do_qr_login()
            if new_cookies:
                cookies = new_cookies
                crawler = create_crawler(cookies)
        elif choice == "2":
            kw = input("搜索关键词: ").strip()
            if kw:
                do_search(crawler, kw)
        elif choice == "3":
            tid = input("帖子tid: ").strip()
            if tid:
                do_fetch_post(crawler, tid)
        elif choice == "4":
            kw = input("搜索关键词: ").strip()
            if kw:
                do_hot_posts(crawler, kw)
        elif choice == "5":
            cf = os.path.join(SCRIPT_DIR, "test_cookies.json")
            if os.path.exists(cf):
                os.remove(cf)
                print("Cookie 已清除")
            cookies = None
            crawler = create_crawler({})
        elif choice == "0":
            print("再见!")
            break
        else:
            print("无效选项")


if __name__ == "__main__":
    print("=" * 50)
    print("  尽孝插件 - 搜索测试")
    print("=" * 50)
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        cookies = load_saved_cookies()
        crawler = create_crawler(cookies or {}, debug=True)
        if cmd == "search" and len(sys.argv) > 2:
            do_search(crawler, " ".join(sys.argv[2:]))
        elif cmd == "hot" and len(sys.argv) > 2:
            do_hot_posts(crawler, " ".join(sys.argv[2:]))
        elif cmd == "post" and len(sys.argv) > 2:
            do_fetch_post(crawler, sys.argv[2])
        elif cmd == "login":
            do_qr_login()
        else:
            print("用法: python test_tieba.py [search|hot|post|login] [参数]")
    else:
        menu()
