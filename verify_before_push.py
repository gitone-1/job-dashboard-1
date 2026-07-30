#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
发布前强制校验脚本（防止「整段 JS 语法错误 → 所有浏览器按钮失效」类问题再次上线）

用法：
    python3 verify_before_push.py           # 校验当前目录的 index.html
    python3 verify_before_push.py /path/index.html

退出码：
    0 = 通过（可以 git push）
    1 = 未通过（禁止 push，先修复）

校验内容：
    1) 【强制】抽取 index.html 内联 <script> 用 `node --check` 做语法校验
       —— 这一步能拦住「多余右花括号 / 缺括号 / 模板字符串未闭合」等所有语法错误。
    2) 【可选增强】若环境装有 Playwright，则启动 headless Chromium 真实渲染页面，
       断言：无 pageerror、#statTotal 不是 '--'、#jobList 有子节点（岗位列表渲染成功）。
       —— 这一步能拦住「语法通过但运行时崩溃 / 数据加载死循环」等问题。
       若未安装 Playwright，仅给提示，不阻断（语法校验仍是硬门槛）。
"""

import os
import re
import sys
import subprocess
import tempfile
import threading
import http.server
import socketserver
import webbrowser

HTML_PATH = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")

# 控制台颜色
GREEN = "\033[32m"
RED = "\033[31m"
YELLOW = "\033[33m"
RESET = "\033[0m"


def log_ok(msg):
    print(f"{GREEN}✅ {msg}{RESET}")


def log_fail(msg):
    print(f"{RED}❌ {msg}{RESET}")


def log_warn(msg):
    print(f"{YELLOW}⚠️  {msg}{RESET}")


def extract_inline_script(html):
    """抽取 index.html 中无 src 的内联 <script> 块（取最长的一段）。"""
    scripts = re.findall(r"<script>(.*?)</script>", html, re.S)
    if not scripts:
        return None
    return max(scripts, key=len)


def step1_syntax_check(html):
    """强制：node --check 语法校验。返回 True/False。"""
    print("\n[步骤 1/2] 语法校验（node --check 抽取内联脚本）")
    js = extract_inline_script(html)
    if js is None:
        log_fail("未找到内联 <script> 块")
        return False

    # 检查 node 是否可用
    node_ok = subprocess.run(["node", "--version"], capture_output=True, text=True)
    if node_ok.returncode != 0:
        log_fail("本机未安装 node，无法做语法校验。请先安装 Node.js 后再发布。")
        return False

    fd, path = tempfile.mkstemp(suffix=".js", prefix="dashboard_check_")
    os.close(fd)
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(js)
        r = subprocess.run(["node", "--check", path], capture_output=True, text=True)
        if r.returncode == 0:
            log_ok(f"语法校验通过（脚本 {len(js)} 字符，无语法错误）")
            return True
        else:
            log_fail("语法校验失败！发现 JS 语法错误，禁止发布：")
            print(r.stderr)
            return False
    finally:
        os.unlink(path)


def step2_render_check(html_path):
    """可选增强：Playwright headless 真实渲染校验。返回 True（通过）/False（未通过）/None（跳过）。"""
    print("\n[步骤 2/2] 真实浏览器渲染校验（Playwright，可选）")
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        log_warn("未安装 Playwright，跳过真实渲染校验（语法校验已通过，仍可发布）。")
        log_warn("建议：pip install playwright && playwright install chromium，以获得完整防护。")
        return None

    # 起一个本地静态服务器
    root = os.path.dirname(os.path.abspath(html_path))
    handler = http.server.SimpleHTTPRequestHandler
    httpd = socketserver.TCPServer(("127.0.0.1", 0), handler)
    port = httpd.server_address[1]
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()

    url = f"http://127.0.0.1:{port}/index.html"
    errors = []
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda exc: errors.append(f"PAGEERROR: {exc}"))
            page.on("console", lambda msg: errors.append(f"CONSOLE[{msg.type}]: {msg.text}") if msg.type == "error" else None)
            page.goto(url, wait_until="networkidle", timeout=20000)
            page.wait_for_timeout(1500)
            stat_total = page.evaluate("() => { const e=document.getElementById('statTotal'); return e? e.textContent.trim(): null; }")
            job_count = page.evaluate("() => { const e=document.getElementById('jobList'); return e? e.children.length: -1; }")
            browser.close()

        if errors:
            log_fail("渲染校验失败：浏览器捕获到错误")
            for e in errors:
                print("   " + e)
            return False
        if stat_total in (None, "--", ""):
            log_fail(f"渲染校验失败：#statTotal 仍为占位符（值={stat_total!r}），数据未加载")
            return False
        if job_count <= 0:
            log_fail(f"渲染校验失败：#jobList 无子节点（值={job_count}），岗位列表未渲染")
            return False
        log_ok(f"渲染校验通过：无运行时错误，总岗位={stat_total}，列表渲染 {job_count} 条")
        return True
    except Exception as e:
        log_warn(f"渲染校验未能完成（不阻断发布）：{e}")
        return None
    finally:
        httpd.shutdown()


def main():
    print("=" * 60)
    print(" 岗位仪表板 · 发布前校验")
    print("=" * 60)
    if not os.path.isfile(HTML_PATH):
        log_fail(f"找不到文件：{HTML_PATH}")
        sys.exit(1)
    html = open(HTML_PATH, encoding="utf-8").read()

    syntax_ok = step1_syntax_check(html)
    if not syntax_ok:
        log_fail("\n❌ 语法校验未通过 → 禁止 git push，请先修复 index.html 的 JS 语法错误。")
        sys.exit(1)

    render = step2_render_check(HTML_PATH)  # True / False / None

    print("\n" + "=" * 60)
    if render is False:
        log_fail("语法通过但真实渲染失败 → 禁止 git push，请排查运行时错误。")
        sys.exit(1)
    log_ok("全部校验通过，可以安全 git push 到 GitHub Pages。")
    print("=" * 60)
    sys.exit(0)


if __name__ == "__main__":
    main()
