"""
国聘爬虫 — 使用 Playwright 抓取 iguopin.com (国资央企招聘平台)
国聘是 React SPA，API 需要从页面行为中探测
"""
import json
import random
import re
import time
from typing import List, Dict, Any


def scrape_guopin(config: Dict, http_client=None) -> List[Dict]:
    """
    抓取国聘平台岗位数据
    国聘是 React SPA，使用 Playwright 模拟浏览器操作
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ Playwright 未安装，跳过国聘")
        return []

    all_jobs = []
    cities = config.get('cities', [])[:3]
    keywords = config.get('search_keywords', [])[:3]
    max_jobs = config.get('scraper', {}).get('max_jobs_per_source', 30)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            viewport={"width": 1440, "height": 900},
            locale="zh-CN",
        )
        page = context.new_page()

        for kw in keywords:
            if len(all_jobs) >= max_jobs:
                break
            try:
                # 国聘搜索页
                url = f"https://www.iguopin.com/search?keyword={kw}"
                print(f"  国聘搜索: {kw}")

                page.goto(url, wait_until="domcontentloaded", timeout=20000)
                time.sleep(5)  # 等 React 渲染

                # 尝试从页面内容提取
                content = page.content()

                # 尝试提取内嵌的 JSON 数据
                script_data = page.evaluate("""() => {
                    const scripts = document.querySelectorAll('script');
                    for (const s of scripts) {
                        const text = s.textContent || '';
                        if (text.includes('"jobList"') || text.includes('"data"') || text.includes('"list"')) {
                            try {
                                // 尝试从 __NEXT_DATA__ 或 window.__INITIAL_STATE__ 提取
                                if (text.includes('__NEXT_DATA__')) {
                                    const match = text.match(/__NEXT_DATA__\\s*=\\s*(\\{[^<]+\\})/);
                                    if (match) return match[1];
                                }
                            } catch(e) {}
                        }
                    }
                    // 尝试从页面文本中提取岗位信息
                    const jobCards = document.querySelectorAll('[class*="job"], [class*="card"], [class*="item"]');
                    const results = [];
                    jobCards.forEach(card => {
                        const text = card.textContent.trim();
                        if (text.length > 20 && text.length < 500) {
                            results.push(text);
                        }
                    });
                    return JSON.stringify(results.slice(0, 20));
                }""")

                if script_data:
                    try:
                        cards = json.loads(script_data) if isinstance(script_data, str) else script_data
                        if isinstance(cards, list):
                            for card_text in cards:
                                if len(all_jobs) >= max_jobs:
                                    break
                                job = _parse_guopin_card(card_text, kw, config)
                                if job:
                                    all_jobs.append(job)
                    except Exception:
                        pass

                # 也直接从 DOM 提取
                if not all_jobs:
                    cards = page.query_selector_all('[class*="job-item"], [class*="job-card"], [class*="position-item"], .search-result-item')
                    for card in cards[:20]:
                        if len(all_jobs) >= max_jobs:
                            break
                        try:
                            card_text = card.inner_text()
                            job = _parse_guopin_card(card_text, kw, config)
                            if job:
                                # 尝试获取链接
                                link_el = card.query_selector('a')
                                if link_el:
                                    href = link_el.get_attribute('href') or ''
                                    if href:
                                        job['url'] = f"https://www.iguopin.com{href}" if href.startswith('/') else href
                                all_jobs.append(job)
                        except Exception:
                            continue

                print(f"    找到 {len(all_jobs)} 条")
                time.sleep(random.uniform(3, 6))

            except Exception as e:
                print(f"  国聘异常 ({kw}): {e}")
                continue

        browser.close()

    return all_jobs


def _parse_guopin_card(text: str, keyword: str, config: Dict) -> Dict:
    """从文本中解析国聘岗位卡片"""
    from utils.parser import classify_company_type, extract_salary_range, normalize_city, extract_tags

    # 提取标题
    title = ''
    title_patterns = [
        r'(数据运营|产品运营|策略运营|用户运营|电商运营|增长运营|数字化运营|'
        r'社区运营|平台运营|内容运营|客户运营|活动运营|运营专员|数据分析|'
        r'数据产品|商业分析|业务运营|市场运营|品牌运营)',
    ]
    for pat in title_patterns:
        m = re.search(pat, text)
        if m:
            title = m.group(1)
            break

    if not title:
        return None

    # 排除管理岗
    exclude_words = config.get('exclude_title_keywords', [])
    if any(w in text for w in exclude_words):
        return None

    # 排除校招/实习
    if any(w in text for w in ['实习', '校招', '应届']):
        return None

    # 提取公司
    company = '未知公司'
    for type_key, companies in config.get('company_types', {}).items():
        for c in companies:
            if c in text:
                company = c
                break
        if company != '未知公司':
            break

    # 提取城市
    cities = config.get('cities', [])
    city = None
    for c in cities:
        if c in text:
            city = c
            break

    # 提取薪资
    salary_match = re.search(
        r'(\d+[-~]\d+[kK])|(\d+[-~]\d+万)|(月薪\s*\d+[-~]\d+[kK])|(\d+K[-~]\d+K)',
        text
    )
    salary = salary_match.group(0) if salary_match else '面议'

    return {
        'company': company,
        'type': classify_company_type(company, config),
        'title': title,
        'city': city or '苏州',
        'salary': extract_salary_range(salary),
        'url': '',
        'source': '国聘',
        'source_type': 'guopin',
        'desc': text[:300],
        'requirements': [],
        'tags': extract_tags(text, config.get('search_keywords', [])),
        'status': '可投递',
        'note': '国聘社招',
        'recruit_type': '社招',
    }
