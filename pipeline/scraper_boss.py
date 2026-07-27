"""
BOSS直聘爬虫 - 使用 Playwright 模拟浏览器
"""
import json
import random
import time
from typing import List, Dict, Any
from utils.parser import clean_text, extract_salary_range, extract_tags, normalize_city, classify_company_type


def scrape_boss(config: Dict) -> List[Dict]:
    """
    抓取 BOSS直聘岗位数据
    使用 Playwright 模拟浏览器，处理反爬
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ Playwright 未安装，跳过 BOSS直聘")
        return []

    all_jobs = []
    cities = config.get('cities', [])
    keywords = config.get('search_keywords', [])
    boss_codes = config.get('boss_city_codes', {})
    max_per_source = config.get('scraper', {}).get('max_jobs_per_source', 50)
    max_pages = config.get('scraper', {}).get('boss_max_pages', 3)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
            viewport={"width": 1920, "height": 1080},
            locale="zh-CN",
        )
        page = context.new_page()

        for city in cities[:5]:  # 限制城市数量，避免被封锁
            city_code = boss_codes.get(city, '')
            if not city_code:
                continue

            for kw in keywords[:2]:  # 限制关键词数量
                try:
                    for page_num in range(1, max_pages + 1):
                        url = f"https://www.zhipin.com/web/geek/job?city={city_code}&query={kw}&page={page_num}"
                        page.goto(url, wait_until="networkidle", timeout=30000)

                        # 模拟人类行为：随机滚动
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
                        time.sleep(random.uniform(1, 2))
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.8)")
                        time.sleep(random.uniform(1, 2))

                        # 等待岗位列表加载
                        page.wait_for_selector('.job-card-wrap, .job-list-box, [class*="job-card"]',
                                               timeout=10000)

                        # 提取岗位卡片
                        cards = page.query_selector_all('.job-card-wrap, .job-card-box, li[class*="job-card"]')
                        if not cards:
                            cards = page.query_selector_all('[class*="job-card"]')

                        for card in cards:
                            try:
                                title_el = card.query_selector('.job-name, .job-title, [class*="job-name"]')
                                company_el = card.query_selector('.company-name, [class*="company-name"]')
                                salary_el = card.query_selector('.salary, [class*="salary"]')
                                city_el = card.query_selector('.job-area, [class*="area"], [class*="city"]')
                                tags_els = card.query_selector_all('.tag-item, [class*="tag"]')

                                title = clean_text(title_el.inner_text()) if title_el else ''
                                company = clean_text(company_el.inner_text()) if company_el else ''
                                salary = clean_text(salary_el.inner_text()) if salary_el else ''
                                city_text = clean_text(city_el.inner_text()) if city_el else ''
                                tags_text = ' '.join([clean_text(t.inner_text()) for t in tags_els])

                                if not title or not company:
                                    continue

                                city_norm = normalize_city(city_text, cities)
                                if not city_norm:
                                    city_norm = city  # fallback

                                job = {
                                    'company': company,
                                    'type': classify_company_type(company, config),
                                    'title': title,
                                    'city': city_norm,
                                    'salary': extract_salary_range(salary),
                                    'url': page.url,  # BOSS直聘动态加载，记录搜索页URL
                                    'source': 'BOSS直聘',
                                    'source_type': 'boss',
                                    'desc': tags_text,  # 标签作为初步描述
                                    'requirements': [],
                                    'tags': [],
                                    'status': '可投递',
                                    'note': '',
                                }

                                # 提取标签
                                job['tags'] = extract_tags(
                                    job['title'] + ' ' + tags_text,
                                    config.get('search_keywords', [])
                                )
                                all_jobs.append(job)

                                if len(all_jobs) >= max_per_source:
                                    break
                            except Exception:
                                continue

                        if len(all_jobs) >= max_per_source:
                            break

                        # 翻页间随机延迟
                        time.sleep(random.uniform(3, 8))

                except Exception as e:
                    print(f"  BOSS直聘抓取异常 ({city}/{kw}): {e}")
                    continue

                if len(all_jobs) >= max_per_source:
                    break
            if len(all_jobs) >= max_per_source:
                break

        browser.close()

    return all_jobs
