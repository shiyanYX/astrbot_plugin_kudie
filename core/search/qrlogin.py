"""
百度贴吧扫码登录模块
流程: getqrcode → 展示二维码 → unicast轮询扫码 → qrbdusslogin获取Cookie
"""
import json
import logging
import time
from typing import Optional

import requests

logger = logging.getLogger(__name__)

# ─── API 端点 ─────────────────────────────────────────────

QRCODE_URL = "https://passport.baidu.com/v2/api/getqrcode"
POLL_URL = "https://passport.baidu.com/channel/unicast"
LOGIN_URL = "https://passport.baidu.com/v3/login/main/qrbdusslogin"


class QRLoginError(Exception):
    """扫码登录异常"""
    pass


class TiebaQRLogin:
    """贴吧二维码扫码登录"""

    def __init__(self, timeout: int = 10):
        self._timeout = timeout
        self._session = requests.Session()
        self._session.headers.update({
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
        })

    # ─── 步骤 1: 获取二维码 ──────────────────────────────────

    def get_qrcode(self) -> dict:
        """
        获取登录二维码

        Returns:
            {
                "sign": str,          # 会话标识，用于轮询
                "imgurl": str,        # 二维码图片 URL
                "img_data": bytes,    # 二维码图片二进制数据
            }
        """
        resp = self._session.get(
            QRCODE_URL,
            params={"lp": "pc"},
            timeout=self._timeout,
        )
        data = resp.json()
        if data.get("errno") != 0:
            raise QRLoginError(f"获取二维码失败: {data}")

        sign = data["sign"]
        img_url = data["imgurl"]
        if not img_url.startswith("http"):
            img_url = "https://" + img_url

        # 下载二维码图片
        img_resp = self._session.get(img_url, timeout=self._timeout)
        img_data = img_resp.content

        return {
            "sign": sign,
            "imgurl": img_url,
            "img_data": img_data,
        }

    # ─── 步骤 2: 轮询扫码状态 ────────────────────────────────

    def poll(self, sign: str) -> dict:
        """
        检查扫码状态

        Args:
            sign: 步骤1返回的会话标识

        Returns:
            {
                "status": "waiting" | "scanned" | "confirmed",
                "bduss": Optional[str],      # 确认后才有
            }
        """
        resp = self._session.get(
            POLL_URL,
            params={"channel_id": sign, "callback": ""},
            timeout=self._timeout,
        )
        text = resp.text.strip()

        # 移除 JSONP 包装
        if text.startswith("{") and text.endswith("}"):
            data = json.loads(text)
        else:
            # 可能被 JSONP 包裹: callback({...})
            start = text.find("{")
            end = text.rfind("}") + 1
            if start >= 0 and end > start:
                data = json.loads(text[start:end])
            else:
                raise QRLoginError(f"无法解析轮询响应: {text[:200]}")

        errno = data.get("errno", -1)

        if errno == 1:
            return {"status": "waiting", "bduss": None}

        if errno == 0:
            # channel_v 是嵌套 JSON 字符串: {"status":0,"v":"bduss_value","u":""}
            channel_v_raw = data.get("channel_v", "")
            if channel_v_raw:
                try:
                    inner = json.loads(channel_v_raw)
                except (json.JSONDecodeError, TypeError):
                    inner = {}
                bduss = inner.get("v", "")
                if bduss and inner.get("status") == 0:
                    return {"status": "confirmed", "bduss": bduss}
                if inner.get("status") == 1:
                    return {"status": "scanned", "bduss": None}

            # 兼容旧格式: channel.v 直接存在
            channel_v = data.get("channel", {}).get("v", "")
            if channel_v:
                return {"status": "confirmed", "bduss": channel_v}

        logger.warning(f"未知轮询状态: {json.dumps(data, ensure_ascii=False)[:500]}")
        return {"status": "waiting", "bduss": None}

    # ─── 步骤 3: 用 BDUSS 换完整 Cookie ──────────────────────

    def login(self, bduss: str) -> dict:
        """
        用 BDUSS 换取完整 Cookie（含 STOKEN 等）

        Args:
            bduss: 扫码确认后获取的 BDUSS

        Returns:
            {
                "bduss": str,
                "stoken": str,
                "baiduid": str,
                "tiebauid": str,
                "cookies": dict,       # 完整 cookie 字典
            }
        """
        resp = self._session.get(
            LOGIN_URL,
            params={"bduss": bduss, "u": "https://tieba.baidu.com/"},
            timeout=self._timeout,
            allow_redirects=True,
        )

        cookies = {}
        raw = self._session.cookies.get_dict()

        for name in ["BDUSS", "STOKEN", "BAIDUID", "TIEBAUID"]:
            cookies[name.lower()] = raw.get(name, raw.get(name.lower(), ""))

        # 也尝试从重定向的 Set-Cookie 中提取
        for h in resp.history:
            for set_cookie in h.headers.get("Set-Cookie", "").split(","):
                for name in ["BDUSS", "STOKEN", "BAIDUID", "TIEBAUID"]:
                    if name in set_cookie:
                        val = set_cookie.split(name + "=", 1)[-1].split(";")[0].strip()
                        cookies[name.lower()] = val

        return {
            "bduss": cookies.get("bduss", bduss),
            "stoken": cookies.get("stoken", ""),
            "baiduid": cookies.get("baiduid", ""),
            "tiebauid": cookies.get("tiebauid", ""),
            "cookies": cookies,
        }

    # ─── 全流程封装 ─────────────────────────────────────────

    def login_with_qr(
        self,
        poll_callback=None,
        poll_interval: float = 2.0,
        max_wait: float = 120.0,
    ) -> dict | None:
        """
        完整扫码登录流程（同步，需外部传入回调用于展示二维码）

        Args:
            poll_callback: 可选回调，每次轮询后调用 poll_callback(status_dict)
            poll_interval: 轮询间隔（秒）
            max_wait: 最大等待时间（秒）

        Returns:
            {"bduss": ..., "stoken": ..., "baiduid": ..., "tiebauid": ...}
            超时返回 None
        """
        # 步骤1: 获取二维码
        qr = self.get_qrcode()
        sign = qr["sign"]

        # 步骤2: 轮询
        start = time.time()
        while time.time() - start < max_wait:
            status = self.poll(sign)

            if poll_callback:
                poll_callback(status)

            if status["status"] == "confirmed" and status["bduss"]:
                result = self.login(status["bduss"])
                return {
                    "bduss": result["bduss"],
                    "stoken": result.get("stoken", ""),
                    "baiduid": result.get("baiduid", ""),
                    "tiebauid": result.get("tiebauid", ""),
                }
            elif status["status"] == "scanned":
                pass

            time.sleep(poll_interval)

        return None
