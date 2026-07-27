"""
BOSS直聘 Playwright 爬虫 — 使用真实浏览器绕过反爬
抓取苏州/杭州/上海等城市的运营类社招岗位
"""
import json
import random
import re
import time
from typing import List, Dict, Any
from pathlib import Path


def scrape_boss(config: Dict) -> List[Dict]:
    """
    使用 Playwright 真实浏览器抓取 BOSS直聘岗位
    策略：先访问首页建立 cookie，再逐步搜索
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ Playwright 未安装，跳过 BOSS直聘")
        return []

    all_jobs = []
    # 核心城市：苏州、杭州
    cities = [c for c in config.get('cities', []) if c in ('苏州', '杭州')]
    keywords = config.get('search_keywords', [])[:3]  # 产品运营、数据运营、策略运营
    boss_codes = config.get('boss_city_codes', {})
    max_per_source = config.get('scraper', {}).get('max_jobs_per_source', 100)
    exclude_words = config.get('exclude_title_keywords', [])

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
            timezone_id="Asia/Shanghai",
        )
        page = context.new_page()

        # 隐藏自动化特征
        page.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', { get: () => false });
            Object.defineProperty(navigator, 'plugins', { get: () => [1, 2, 3, 4, 5] });
            window.chrome = { runtime: {} };
            delete navigator.__proto__.webdriver;
        """)

        # Step 1: 先访问首页建立 cookie
        print("  正在建立 BOSS直聘 会话...")
        try:
            page.goto("https://www.zhipin.com/", wait_until="domcontentloaded", timeout=30000)
            time.sleep(3)
            # 关闭可能弹出的对话框
            try:
                close_btn = page.query_selector('.sider-close, .dialog-close, .modal-close, [class*="close"]')
                if close_btn:
                    close_btn.click()
                    time.sleep(1)
            except Exception:
                pass
        except Exception as e:
            print(f"  首页访问失败: {e}")

        for city in cities:
            city_code = boss_codes.get(city, '')
            if not city_code:
                continue
            if len(all_jobs) >= max_per_source:
                break

            for kw in keywords:
                if len(all_jobs) >= max_per_source:
                    break

                try:
                    print(f"  BOSS直聘: {city} × {kw}")
                    url = f"https://www.zhipin.com/web/geek/job?city={city_code}&query={kw}&page=1"

                    # 用 domcontentloaded 避免重定向中断
                    try:
                        page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    except Exception:
                        # 如果重定向到登录页，跳过
                        current_url = page.url
                        if 'passport' in current_url or 'user' in current_url:
                            print(f"    ⚠️ 被重定向到登录页，跳过 {city}/{kw}")
                            # 重新建立会话
                            try:
                                page.goto("https://www.zhipin.com/", wait_until="domcontentloaded", timeout=15000)
                                time.sleep(3)
                            except Exception:
                                pass
                            continue
                        else:
                            # 其他情况继续
                            pass

                    # 等待列表加载
                    time.sleep(5)

                    # 检查是否需要登录
                    if 'passport' in page.url or 'login' in page.url.lower():
                        print(f"    ⚠️ 需要登录，跳过")
                        continue

                    # 滚动加载
                    for scroll_i in range(3):
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.7)")
                        time.sleep(random.uniform(2, 3))
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(random.uniform(2, 3))

                    # 提取岗位卡片 - BOSS直聘常见选择器
                    selectors = [
                        '.job-card-wrap',
                        '.job-card-box',
                        'li.job-card-box',
                        '.search-job-result li',
                        '[class*="job-card"]',
                    ]

                    cards = []
                    for sel in selectors:
                        cards = page.query_selector_all(sel)
                        if cards:
                            print(f"    选择器 '{sel}' 匹配 {len(cards)} 个卡片")
                            break

                    if not cards:
                        # 最后尝试：获取所有可见文字来分析
                        print(f"    未匹配到岗位卡片，页面 URL: {page.url[:80]}")
                        continue

                    for card in cards[:25]:
                        if len(all_jobs) >= max_per_source:
                            break
                        try:
                            title = ''
                            company = ''
                            salary = ''
                            area_text = ''
                            link = ''

                            # 尝试多种选择器提取字段
                            for title_sel in ['.job-name', '.job-title', '[class*="job-name"]', '.name']:
                                el = card.query_selector(title_sel)
                                if el:
                                    title = el.inner_text().strip()
                                    if title:
                                        break

                            for comp_sel in ['.company-name', '.company-text', '[class*="company-name"]']:
                                el = card.query_selector(comp_sel)
                                if el:
                                    company = el.inner_text().strip()
                                    if company:
                                        break

                            for sal_sel in ['.salary', '.red', '[class*="salary"]']:
                                el = card.query_selector(sal_sel)
                                if el:
                                    salary = el.inner_text().strip()
                                    if salary:
                                        break

                            for area_sel in ['.job-area', '.job-location', '[class*="area"]', '[class*="location"]']:
                                el = card.query_selector(area_sel)
                                if el:
                                    area_text = el.inner_text().strip()
                                    if area_text:
                                        break

                            link_el = card.query_selector('a.job-card-left, a[href*="job_detail"], a[href*="/job_detail/"]')
                            if link_el:
                                link = link_el.get_attribute('href') or ''

                            if not title or not company:
                                continue

                            # 过滤管理岗
                            if any(w in title for w in exclude_words):
                                continue

                            # 过滤校招/实习
                            if any(w in title for w in ['实习', '校招', '应届', '培训生', '管培生']):
                                continue

                            from utils.parser import normalize_city, classify_company_type, extract_salary_range, extract_tags
                            city_norm = normalize_city(area_text, config.get('cities', [])) or city

                            # 过滤不在目标城市的
                            if city_norm not in config.get('cities', []):
                                continue

                            job = {
                                'company': company,
                                'type': classify_company_type(company, config),
                                'title': title,
                                'city': city_norm,
                                'salary': extract_salary_range(salary),
                                'url': f"https://www.zhipin.com{link}" if link and link.startswith('/') else (link or page.url),
                                'source': 'BOSS直聘',
                                'source_type': 'boss',
                                'desc': f"{title} - {company} - {city_norm}",
                                'requirements': [],
                                'tags': extract_tags(title, config.get('search_keywords', [])),
                                'status': '可投递',
                                'note': 'BOSS直聘社招',
                                'recruit_type': '社招',
                            }
                            all_jobs.append(job)

                        except Exception as e:
                            continue

                    print(f"    本轮产出: {len(all_jobs)} 条累计")
                    time.sleep(random.uniform(3, 7))

                except Exception as e:
                    print(f"  BOSS直聘异常 ({city}/{kw}): {str(e)[:100]}")
                    continue

        browser.close()

    print(f"  BOSS直聘总计: {len(all_jobs)} 条")
    return all_jobs
