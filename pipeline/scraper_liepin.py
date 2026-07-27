"""
猎聘爬虫 — 使用 Playwright 抓取 liepin.com
猎聘反爬较弱，用 requests 也可以，但 Playwright 更稳定
"""
import json
import random
import re
import time
from typing import List, Dict, Any


def scrape_liepin(config: Dict, http_client=None) -> List[Dict]:
    """
    抓取猎聘岗位数据
    先用 requests 尝试，失败则用 Playwright
    """
    all_jobs = []

    # 先试 requests 方式
    try:
        import requests
        jobs = _scrape_liepin_requests(config)
        if jobs:
            print(f"  猎聘(requests): {len(jobs)} 条")
            all_jobs.extend(jobs)
            return all_jobs
    except Exception as e:
        print(f"  猎聘 requests 失败: {e}")

    # 降级到 Playwright
    try:
        from playwright.sync_api import sync_playwright
        jobs = _scrape_liepin_playwright(config)
        if jobs:
            print(f"  猎聘(Playwright): {len(jobs)} 条")
            all_jobs.extend(jobs)
    except Exception as e:
        print(f"  猎聘 Playwright 也失败: {e}")

    return all_jobs


def _scrape_liepin_requests(config: Dict) -> List[Dict]:
    """用 requests 抓猎聘"""
    import requests
    from bs4 import BeautifulSoup
    from utils.parser import clean_text, extract_salary_range, extract_tags, normalize_city, classify_company_type

    jobs = []
    cities = config.get('cities', [])[:3]
    keywords = config.get('search_keywords', [])[:3]
    max_jobs = config.get('scraper', {}).get('max_jobs_per_source', 50)

    session = requests.Session()
    session.headers.update({
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        'Accept': 'text/html,application/xhtml+xml',
        'Accept-Language': 'zh-CN,zh;q=0.9',
    })

    for city in cities:
        for kw in keywords:
            if len(jobs) >= max_jobs:
                break
            try:
                # 猎聘搜索页
                url = f"https://www.liepin.com/zhaopin/?city={city}&key={kw}"
                resp = session.get(url, timeout=15)
                if resp.status_code != 200:
                    continue

                soup = BeautifulSoup(resp.text, 'lxml')
                cards = soup.select('.job-list-item, .job-card, [class*="job"]')

                for card in cards:
                    if len(jobs) >= max_jobs:
                        break
                    try:
                        title_el = card.select_one('[class*="title"], .job-title, h3 a')
                        company_el = card.select_one('[class*="company"], .company-name')
                        salary_el = card.select_one('[class*="salary"], .job-salary')
                        city_el = card.select_one('[class*="area"], .job-area')

                        title = clean_text(title_el.get_text()) if title_el else ''
                        company = clean_text(company_el.get_text()) if company_el else ''
                        salary = clean_text(salary_el.get_text()) if salary_el else ''
                        city_text = clean_text(city_el.get_text()) if city_el else ''

                        if not title or not company:
                            continue

                        city_norm = normalize_city(city_text, config.get('cities', []))
                        if not city_norm:
                            city_norm = city

                        # 过滤管理岗
                        exclude_words = config.get('exclude_title_keywords', [])
                        if any(w in title for w in exclude_words):
                            continue

                        link = ''
                        if title_el and title_el.name == 'a':
                            link = title_el.get('href', '')
                        elif title_el:
                            a_tag = title_el.find('a')
                            if a_tag:
                                link = a_tag.get('href', '')

                        job = {
                            'company': company,
                            'type': classify_company_type(company, config),
                            'title': title,
                            'city': city_norm,
                            'salary': extract_salary_range(salary),
                            'url': link,
                            'source': '猎聘',
                            'source_type': 'liepin',
                            'desc': '',
                            'requirements': [],
                            'tags': extract_tags(title, config.get('search_keywords', [])),
                            'status': '可投递',
                            'note': '猎聘社招',
                            'recruit_type': '社招',
                        }
                        jobs.append(job)
                    except Exception:
                        continue

                time.sleep(random.uniform(2, 4))

            except Exception as e:
                print(f"  猎聘异常 ({city}/{kw}): {e}")
                continue

    return jobs


def _scrape_liepin_playwright(config: Dict) -> List[Dict]:
    """用 Playwright 抓猎聘（备用方案）"""
    from playwright.sync_api import sync_playwright
    from utils.parser import clean_text, extract_salary_range, extract_tags, normalize_city, classify_company_type

    jobs = []
    cities = config.get('cities', [])[:3]
    keywords = config.get('search_keywords', [])[:3]
    max_jobs = config.get('scraper', {}).get('max_jobs_per_source', 50)

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        for city in cities:
            for kw in keywords:
                if len(jobs) >= max_jobs:
                    break
                try:
                    url = f"https://www.liepin.com/zhaopin/?city={city}&key={kw}"
                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    time.sleep(3)

                    cards = page.query_selector_all('.job-list-item, [class*="job-list"] > div')

                    for card in cards[:20]:
                        if len(jobs) >= max_jobs:
                            break
                        try:
                            title_el = card.query_selector('[class*="title"], h3, .job-name')
                            company_el = card.query_selector('[class*="company"], .company-name')
                            salary_el = card.query_selector('[class*="salary"]')
                            city_el = card.query_selector('[class*="area"]')

                            title = title_el.inner_text().strip() if title_el else ''
                            company = company_el.inner_text().strip() if company_el else ''
                            salary = salary_el.inner_text().strip() if salary_el else ''
                            city_text = city_el.inner_text().strip() if city_el else ''

                            if not title or not company:
                                continue

                            city_norm = normalize_city(city_text, config.get('cities', [])) or city

                            exclude_words = config.get('exclude_title_keywords', [])
                            if any(w in title for w in exclude_words):
                                continue

                            job = {
                                'company': company,
                                'type': classify_company_type(company, config),
                                'title': title,
                                'city': city_norm,
                                'salary': extract_salary_range(salary),
                                'url': page.url,
                                'source': '猎聘',
                                'source_type': 'liepin',
                                'desc': '',
                                'requirements': [],
                                'tags': extract_tags(title, config.get('search_keywords', [])),
                                'status': '可投递',
                                'note': '猎聘社招',
                                'recruit_type': '社招',
                            }
                            jobs.append(job)
                        except Exception:
                            continue

                    time.sleep(random.uniform(2, 4))
                except Exception as e:
                    print(f"  猎聘 Playwright 异常: {e}")
                    continue

        browser.close()

    return jobs
