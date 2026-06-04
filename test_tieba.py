"""
尽孝插件 Windows 测试脚本
测试贴吧扫码登录、搜索、帖子抓取功能
运行: python test_tieba.py
"""
import sys
import os
import time
import json

# 确保能导入插件模块
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, SCRIPT_DIR)

from core.search.qrlogin import TiebaQRLogin
from core.search.tieba_crawler import TiebaCrawler


def load_saved_cookies():
    """读取之前保存的 Cookie"""
    cookie_file = os.path.join(SCRIPT_DIR, "test_cookies.json")
    if os.path.exists(cookie_file):
        with open(cookie_file, "r", encoding="utf-8") as f:
            return json.load(f)
    return None


def save_cookies(cookies):
    """保存 Cookie 到文件"""
    cookie_file = os.path.join(SCRIPT_DIR, "test_cookies.json")
    with open(cookie_file, "w", encoding="utf-8") as f:
        json.dump(cookies, f, ensure_ascii=False, indent=2)
    print(f"✅ Cookie 已保存到 {cookie_file}")


def do_qr_login():
    """扫码登录"""
    print("\n" + "=" * 60)
    print("📱 贴吧扫码登录")
    print("=" * 60)

    qr = TiebaQRLogin(timeout=10)
    qr_data = qr.get_qrcode()

    # 保存二维码图片
    qr_path = os.path.join(SCRIPT_DIR, "qr_login.png")
    with open(qr_path, "wb") as f:
        f.write(qr_data["img_data"])

    print(f"\n✅ 二维码已保存到: {qr_path}")
    print("📱 请用百度App扫描二维码，然后在手机上点【确认登录】")
    print("⏳ 等待扫码中...")

    sign = qr_data["sign"]
    for i in range(60):
        time.sleep(2)
        try:
            status = qr.poll(sign)
        except Exception as e:
            print(f"  轮询异常: {e}")
            continue

        if status["status"] == "scanned":
            print("   📱 已扫码，请在手机上点【确认登录】...")
        elif status["status"] == "confirmed" and status["bduss"]:
            print("   ✅ 已确认！获取Cookie中...")
            result = qr.login(status["bduss"])

            cookies = {
                "bduss": result["bduss"],
                "stoken": result.get("stoken", ""),
                "baiduid": result.get("baiduid", ""),
                "tiebauid": result.get("tiebauid", ""),
            }
            save_cookies(cookies)

            print(f"\n✅ 登录成功！")
            print(f"   BDUSS:  {cookies['bduss'][:40]}...")
            print(f"   STOKEN: {cookies['stoken'][:40] if cookies['stoken'] else '(无)'}...")
            return cookies

        if i % 5 == 0:
            print(f"   [{i*2}s] 等待扫描...")

    print("⏰ 扫码超时（2分钟）")
    return None


def create_crawler(cookies):
    """根据 Cookie 创建爬虫"""
    return TiebaCrawler(
        bduss=cookies.get("bduss", ""),
        stoken=cookies.get("stoken", ""),
        baiduid=cookies.get("baiduid", ""),
        timeout=15,
    )


def do_search(crawler, keyword):
    """测试搜索"""
    print(f"\n🔍 搜索: {keyword}")
    print("-" * 40)
    results = crawler.search(keyword, 5)

    if not results:
        print("❌ 没有搜索结果")
        return []

    print(f"✅ 找到 {len(results)} 条结果:\n")
    for i, r in enumerate(results, 1):
        title = r['title'][:60] if r['title'] else '(无标题)'
        print(f"  {i}. {title}")
        print(f"     链接: {r['url']}")
        if r.get('snippet'):
            print(f"     摘要: {r['snippet'][:80]}")
        print()

    return results


def do_fetch_post(crawler, tid, title_hint=""):
    """测试帖子抓取"""
    print(f"\n📄 抓取帖子: {title_hint or tid}")
    print("-" * 40)
    post = crawler.get_post(tid)

    if not post:
        print("❌ 获取失败")
        return None

    print(f"✅ 标题: {post['title']}")
    print(f"   楼层: {post['floor_count']}")
    print(f"\n   内容预览:")
    for p in post['posts'][:5]:
        author = f"[{p['author']}]" if p['author'] else ""
        content = p['content'][:120]
        role = p.get('role', f"楼{p['floor']}")
        print(f"   {role} {author} {content}")

    return post


def do_hot_posts(crawler, keyword):
    """测试完整热帖流程"""
    print(f"\n🔥 完整热帖搜索: {keyword}")
    print("-" * 40)
    text = crawler.get_hot_posts(keyword, max_search=10, max_content=5)

    if not text:
        print("❌ 未获取到内容")
        return

    print(f"✅ 获取到 {len(text)} 字符")
    print("\n--- 结果预览（前500字）---")
    print(text[:500])
    print("---")


def menu():
    """主菜单"""
    cookies = load_saved_cookies()

    if cookies:
        print(f"\n📋 已加载保存的 Cookie:")
        print(f"   BDUSS:  {cookies.get('bduss', '')[:40]}...")
        print(f"   STOKEN: {cookies.get('stoken', '')[:40] if cookies.get('stoken') else '(无)'}...")
        crawler = create_crawler(cookies)
    else:
        print("\n📋 未找到保存的 Cookie")
        crawler = None

    while True:
        print("\n" + "=" * 60)
        print("尽孝插件 - 测试菜单")
        print("=" * 60)
        print("1. 📱 扫码登录（获取新Cookie）")
        print("2. 🔍 搜索贴吧帖子")
        print("3. 📄 抓取帖子内容（输入帖子ID）")
        print("4. 🔥 完整热帖搜索流程")
        print("5. 🗑️  清除保存的Cookie")
        print("0. 退出")
        print("-" * 60)

        try:
            choice = input("选择: ").strip()
        except (EOFError, KeyboardInterrupt):
            break

        if choice == "1":
            new_cookies = do_qr_login()
            if new_cookies:
                cookies = new_cookies
                crawler = create_crawler(cookies)

        elif choice == "2":
            if not crawler:
                print("❌ 请先登录（选项1）")
                continue
            keyword = input("搜索关键词: ").strip()
            if keyword:
                do_search(crawler, keyword)

        elif choice == "3":
            if not crawler:
                print("❌ 请先登录（选项1）")
                continue
            tid = input("帖子ID（tieba.baidu.com/p/后面的数字）: ").strip()
            if tid:
                do_fetch_post(crawler, tid)

        elif choice == "4":
            if not crawler:
                print("❌ 请先登录（选项1）")
                continue
            keyword = input("搜索关键词: ").strip()
            if keyword:
                do_hot_posts(crawler, keyword)

        elif choice == "5":
            cookie_file = os.path.join(SCRIPT_DIR, "test_cookies.json")
            if os.path.exists(cookie_file):
                os.remove(cookie_file)
                print("✅ Cookie 已清除")
            else:
                print("没有保存的Cookie")
            cookies = None
            crawler = None

        elif choice == "0":
            print("👋 再见!")
            break

        else:
            print("无效选项")


if __name__ == "__main__":
    print("=" * 60)
    print("  尽孝插件 v2.1.0 - Windows 测试脚本")
    print("  测试贴吧扫码登录、搜索、帖子抓取")
    print("=" * 60)

    # 如果有命令行参数，直接运行快速测试
    if len(sys.argv) > 1:
        cmd = sys.argv[1]
        cookies = load_saved_cookies()
        if not cookies:
            print("❌ 请先用菜单模式登录（python test_tieba.py）")
            sys.exit(1)

        crawler = create_crawler(cookies)

        if cmd == "search" and len(sys.argv) > 2:
            keyword = " ".join(sys.argv[2:])
            do_search(crawler, keyword)
        elif cmd == "post" and len(sys.argv) > 2:
            do_fetch_post(crawler, sys.argv[2])
        elif cmd == "hot" and len(sys.argv) > 2:
            keyword = " ".join(sys.argv[2:])
            do_hot_posts(crawler, keyword)
        elif cmd == "login":
            do_qr_login()
        else:
            print(f"用法: python test_tieba.py [search|post|hot|login] [参数]")
    else:
        menu()
