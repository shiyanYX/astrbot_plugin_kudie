"""
尽孝插件 Windows 测试脚本 v2
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
    print(f"Cookie saved: {cookie_file}")


def do_qr_login():
    print("\n" + "=" * 60)
    print("Tieba QR Login")
    print("=" * 60)
    qr = TiebaQRLogin(timeout=10)
    qr_data = qr.get_qrcode()
    qr_path = os.path.join(SCRIPT_DIR, "qr_login.png")
    with open(qr_path, "wb") as f:
        f.write(qr_data["img_data"])
    print(f"\nQR saved: {qr_path}")
    print("Scan with Baidu App, then confirm on phone")
    print("Waiting for scan...")
    sign = qr_data["sign"]
    for i in range(60):
        time.sleep(2)
        try:
            status = qr.poll(sign)
        except Exception as e:
            print(f"  poll error: {e}")
            continue
        if status["status"] == "scanned":
            print("   Scanned! Confirm on phone...")
        elif status["status"] == "confirmed" and status["bduss"]:
            print("   Confirmed! Getting cookies...")
            result = qr.login(status["bduss"])
            cookies = {
                "bduss": result["bduss"],
                "stoken": result.get("stoken", ""),
                "baiduid": result.get("baiduid", ""),
            }
            save_cookies(cookies)
            print(f"Login OK! BDUSS={cookies['bduss'][:40]}...")
            return cookies
        if i % 5 == 0:
            print(f"   [{i*2}s] waiting...")
    print("Timeout (2min)")
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
    print(f"\nSearch: {keyword}")
    print("-" * 40)
    results = crawler.search(keyword, 10)
    if not results:
        print("No results")
        return []
    print(f"Found {len(results)} posts:\n")
    for i, r in enumerate(results, 1):
        title = r['title'][:80] if r['title'] else '(no title)'
        print(f"  {i}. [{r['tid']}] {title}")
    print()
    return results


def do_fetch_post(crawler, tid):
    print(f"\nFetch post: {tid}")
    print("-" * 40)
    post = crawler.get_post(tid)
    if not post:
        print("Failed")
        return None
    print(f"Title: {post['title']}")
    print(f"Floors: {post['floor_count']}")
    print(f"\nContent:")
    for p in post['posts'][:10]:
        role = p.get('role', f"#{p['floor']}")
        content = p['content'][:200]
        print(f"  {role}: {content}")
    print()
    return post


def do_hot_posts(crawler, keyword):
    print(f"\nHot posts search: {keyword}")
    print("-" * 40)
    text = crawler.get_hot_posts(keyword, max_search=10, max_content=5)
    if not text:
        print("No content")
        return
    print(f"Got {len(text)} chars")
    print("\n--- Preview (800 chars) ---")
    print(text[:800])
    print("---")


def menu():
    cookies = load_saved_cookies()
    if cookies:
        print(f"\nLoaded cookies: BDUSS={cookies.get('bduss','')[:40]}...")
        crawler = create_crawler(cookies)
    else:
        print("\nNo saved cookies (Bing search still works without login)")
        crawler = create_crawler({})

    while True:
        print("\n" + "=" * 50)
        print("Test Menu")
        print("=" * 50)
        print("1. QR login (get cookies)")
        print("2. Search posts")
        print("3. Fetch post by tid")
        print("4. Hot posts (search + fetch)")
        print("5. Clear cookies")
        print("0. Exit")
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
            kw = input("Keyword: ").strip()
            if kw:
                do_search(crawler, kw)
        elif choice == "3":
            tid = input("tid: ").strip()
            if tid:
                do_fetch_post(crawler, tid)
        elif choice == "4":
            kw = input("Keyword: ").strip()
            if kw:
                do_hot_posts(crawler, kw)
        elif choice == "5":
            cf = os.path.join(SCRIPT_DIR, "test_cookies.json")
            if os.path.exists(cf):
                os.remove(cf)
                print("Cookies cleared")
            cookies = None
            crawler = create_crawler({})
        elif choice == "0":
            print("Bye!")
            break
        else:
            print("Invalid")


if __name__ == "__main__":
    print("=" * 50)
    print("  Test: Tieba Crawler")
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
            print("Usage: python test_tieba.py [search|hot|post|login] [args]")
    else:
        menu()
