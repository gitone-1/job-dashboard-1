"""
大厂招聘数据源 — 使用 Playwright 搜索各大厂官网招聘页面
替代已失效的内部 API
"""
import json
import random
import re
import time
from typing import List, Dict, Any


def scrape_apis(config: Dict, http_client=None) -> List[Dict]:
    """
    抓取各大厂招聘官网
    使用 Playwright 搜索各公司的招聘页面
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ Playwright 未安装，跳过大厂招聘")
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

        # 定义大厂招聘搜索 URL
        company_searches = [
            # 腾讯
            {
                'company': '腾讯',
                'url_tpl': 'https://careers.tencent.com/search.html?keyword={kw}&city={city}',
            },
            # 字节跳动
            {
                'company': '字节跳动',
                'url_tpl': 'https://jobs.bytedance.com/experienced/position?keywords={kw}&location={city}',
            },
            # 阿里巴巴
            {
                'company': '阿里巴巴',
                'url_tpl': 'https://talent.alibaba.com/off-campus/position-list?lang=zh&search={kw}',
            },
            # 美团
            {
                'company': '美团',
                'url_tpl': 'https://zhaopin.meituan.com/web/personal?keyword={kw}',
            },
            # 京东
            {
                'company': '京东',
                'url_tpl': 'https://zhaopin.jd.com/web/job/job_info_list/3?keyword={kw}',
            },
            # 网易
            {
                'company': '网易',
                'url_tpl': 'https://hr.163.com/job-list.html?keyword={kw}',
            },
            # 华为
            {
                'company': '华为',
                'url_tpl': 'https://career.huawei.com/reccampportal/portal5/social-recruitment.html?keywords={kw}',
            },
            # 比亚迪
            {
                'company': '比亚迪',
                'url_tpl': 'https://job.byd.com/portal/social/search?keyword={kw}',
            },
        ]

        for cs in company_searches:
            if len(all_jobs) >= max_jobs:
                break
            for kw in keywords[:2]:
                if len(all_jobs) >= max_jobs:
                    break
                try:
                    url = cs['url_tpl'].format(kw=kw, city=cities[0])
                    print(f"  大厂搜索: {cs['company']} × {kw}")
                    page.goto(url, wait_until="domcontentloaded", timeout=20000)
                    time.sleep(4)

                    # 等待页面渲染
                    page.evaluate("window.scrollTo(0, document.body.scrollHeight * 0.5)")
                    time.sleep(2)

                    # 提取岗位信息
                    cards = page.query_selector_all(
                        '[class*="job-item"], [class*="position-item"], '
                        '[class*="job-card"], [class*="job-list"] > div, '
                        '[class*="list-item"], [class*="result-item"], '
                        'tr[class*="job"], li[class*="item"]'
                    )

                    for card in cards[:15]:
                        if len(all_jobs) >= max_jobs:
                            break
                        try:
                            card_text = card.inner_text().strip()
                            if len(card_text) < 10 or len(card_text) > 500:
                                continue

                            job = _parse_company_job(card_text, cs['company'], kw, config)
                            if job:
                                # 尝试获取链接
                                link_el = card.query_selector('a')
                                if link_el:
                                    href = link_el.get_attribute('href') or ''
                                    if href and not href.startswith('javascript'):
                                        job['url'] = href if href.startswith('http') else f"{url.split('/web')[0]}{href}" if not href.startswith('/') else href
                                all_jobs.append(job)
                        except Exception:
                            continue

                    print(f"    找到 {len([j for j in all_jobs if j['company'] == cs['company']])} 条")
                    time.sleep(random.uniform(3, 6))

                except Exception as e:
                    print(f"  大厂搜索异常 ({cs['company']}/{kw}): {e}")
                    continue

        browser.close()

    return all_jobs


def _parse_company_job(text: str, company: str, keyword: str, config: Dict) -> Dict:
    """解析大厂官网岗位卡片文本"""
    from utils.parser import classify_company_type, extract_salary_range, normalize_city, extract_tags

    # 排除校招/实习
    if any(w in text for w in ['实习', '校招', '应届', '培训生', '管培生', '2026', '2027']):
        return None

    # 排除管理岗
    exclude_words = config.get('exclude_title_keywords', [])
    if any(w in text for w in exclude_words):
        return None

    # 提取岗位标题
    title = ''
    title_patterns = [
        r'(数据运营|产品运营|策略运营|用户运营|电商运营|增长运营|数字化运营|'
        r'社区运营|平台运营|内容运营|客户运营|活动运营|运营专员|数据分析|'
        r'数据产品|商业分析|业务运营|市场运营|品牌运营|商户运营|'
        r'数据策略|增长策略|运营分析)',
    ]
    for pat in title_patterns:
        m = re.search(pat, text)
        if m:
            title = m.group(1)
            break

    if not title:
        # 检查是否包含关键词相关
        kw_match = re.search(r'运营|数据|分析|增长|策略|产品', text)
        if not kw_match:
            return None
        # 取第一行作为标题
        lines = text.strip().split('\n')
        title = lines[0][:30] if lines else keyword

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
        'source': f'{company}招聘官网',
        'source_type': 'api',
        'desc': text[:300],
        'requirements': [],
        'tags': extract_tags(text, config.get('search_keywords', [])),
        'status': '可投递',
        'note': f'{company}社招',
        'recruit_type': '社招',
    }
