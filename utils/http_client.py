"""
HTTP 客户端 - 统一请求处理，包含反爬策略
"""
import time
import random
import requests
from typing import Optional, Dict, Any
from urllib.parse import urlparse

# 常用 User-Agent 列表
USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:128.0) Gecko/20100101 Firefox/128.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.5 Safari/605.1.15",
]


class HTTPClient:
    """带反爬策略的 HTTP 客户端"""

    def __init__(self, config: Dict[str, Any]):
        self.config = config.get("scraper", {})
        self.delay_min = self.config.get("request_delay_min", 2)
        self.delay_max = self.config.get("request_delay_max", 5)
        self.max_retries = self.config.get("max_retries", 3)
        self.timeout = self.config.get("timeout", 30)
        self.session = requests.Session()
        self.session.headers.update({
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Accept-Encoding": "gzip, deflate, br",
            "Cache-Control": "max-age=0",
            "Connection": "keep-alive",
        })

    def _random_delay(self):
        """随机延迟，模拟人类浏览行为"""
        delay = random.uniform(self.delay_min, self.delay_max)
        time.sleep(delay)

    def _get_random_ua(self) -> str:
        """获取随机 User-Agent"""
        return random.choice(USER_AGENTS)

    def get(self, url: str, headers: Optional[Dict] = None, **kwargs) -> Optional[requests.Response]:
        """GET 请求，带重试和延迟"""
        self.session.headers["User-Agent"] = self._get_random_ua()
        if headers:
            self.session.headers.update(headers)

        for attempt in range(self.max_retries):
            try:
                self._random_delay()
                resp = self.session.get(
                    url,
                    timeout=self.timeout,
                    **kwargs
                )
                if resp.status_code == 200:
                    return resp
                elif resp.status_code == 429:
                    wait = (attempt + 1) * 10
                    print(f"  ⚠️ 被限流 (429)，等待 {wait}s...")
                    time.sleep(wait)
                elif resp.status_code >= 500:
                    wait = (attempt + 1) * 5
                    print(f"  ⚠️ 服务器错误 ({resp.status_code})，重试 {attempt+1}/{self.max_retries}...")
                    time.sleep(wait)
                else:
                    print(f"  ⚠️ HTTP {resp.status_code}: {url}")
                    return None
            except requests.RequestException as e:
                print(f"  ⚠️ 请求异常 ({attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep((attempt + 1) * 3)
        return None

    def post(self, url: str, json_data: Optional[Dict] = None, data: Optional[Dict] = None,
             headers: Optional[Dict] = None, **kwargs) -> Optional[requests.Response]:
        """POST 请求，带重试"""
        self.session.headers["User-Agent"] = self._get_random_ua()
        if headers:
            self.session.headers.update(headers)

        for attempt in range(self.max_retries):
            try:
                self._random_delay()
                resp = self.session.post(
                    url,
                    json=json_data,
                    data=data,
                    timeout=self.timeout,
                    **kwargs
                )
                if resp.status_code in (200, 201):
                    return resp
                elif resp.status_code == 429:
                    time.sleep((attempt + 1) * 10)
                else:
                    print(f"  ⚠️ POST {resp.status_code}: {url}")
                    return None
            except requests.RequestException as e:
                print(f"  ⚠️ POST异常 ({attempt+1}/{self.max_retries}): {e}")
                if attempt < self.max_retries - 1:
                    time.sleep((attempt + 1) * 3)
        return None

    def close(self):
        """关闭会话"""
        self.session.close()
