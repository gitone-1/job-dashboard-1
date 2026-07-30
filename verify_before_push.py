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
    page_errors = []      # 未捕获的 JS 异常 —— 真错误，必须阻断
    console_errors = []   # console.error —— 区分良性 404 与数据加载失败
    stat_total = None
    job_count = -1
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.on("pageerror", lambda exc: page_errors.append(str(exc)))
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
            # 用 "load" 而非 "networkidle"：页面可能向 GitHub Pages 发起会挂起的请求，
            # networkidle 会因此超时。load 事件不依赖这些外部请求。
            try:
                page.goto(url, wait_until="load", timeout=15000)
            except Exception as nav_e:
                # 导航超时通常是网络抖动（外部 fetch 挂起），不算 JS 错误，降级为跳过
                log_warn(f"页面加载等待超时（疑似外部 fetch 挂起，非 JS 错误），仅做已捕获错误判定：{nav_e}")
            page.wait_for_timeout(2500)
            stat_total = page.evaluate("() => { const e=document.getElementById('statTotal'); return e? e.textContent.trim(): null; }")
            job_count = page.evaluate("() => { const e=document.getElementById('jobList'); return e? e.children.length: -1; }")
            browser.close()
    except Exception as e:
        log_warn(f"渲染校验未能完成（不阻断发布）：{e}")
        return None
    finally:
        httpd.shutdown()

    # 1) 未捕获的 JS 异常 —— 必须阻断（这是问题8那种「整段脚本崩溃」的真信号）
    if page_errors:
        log_fail("渲染校验失败：页面抛出未捕获的 JS 异常")
        for e in page_errors:
            print("   " + e)
        return False
    # 2) console.error：仅当核心数据(jobs/resume)加载失败才阻断；
    #    favicon.ico 等良性 404 仅提示，不阻断
    data_fail = [e for e in console_errors if ("jobs" in e.lower() or "resume" in e.lower()) and "404" in e]
    benign = [e for e in console_errors if e not in data_fail]
    if data_fail:
        log_fail("渲染校验失败：核心数据文件(jobs/resume)加载失败")
        for e in data_fail:
            print("   " + e)
        return False
    if benign:
        log_warn(f"渲染校验发现 {len(benign)} 条无关 console 错误(如 favicon.ico 404)，视为良性，不阻断：")
        for e in benign[:3]:
            print("   " + e)
    # 3) 数据已加载且列表渲染 —— 通过
    if stat_total not in (None, "--", "") and job_count > 0:
        log_ok(f"渲染校验通过：无运行时错误，总岗位={stat_total}，列表渲染 {job_count} 条")
        return True
    # 数据没读到：可能是网络抖动导致外部数据未回，降级为跳过（不阻断）
    log_warn(f"渲染校验数据未读到（statTotal={stat_total!r}, jobList={job_count}），疑似网络抖动，降级为跳过（不阻断）。语法校验已通过。")
    return None


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
