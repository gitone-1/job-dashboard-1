"""
猎聘爬虫 - 抓取 liepin.com
"""
import json
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from utils.http_client import HTTPClient
from utils.parser import clean_text, extract_salary_range, extract_tags, normalize_city, classify_company_type


def scrape_liepin(config: Dict, http_client: HTTPClient) -> List[Dict]:
    """
    抓取猎聘岗位数据
    策略：requests + BeautifulSoup 解析搜索页面
    """
    all_jobs = []
    cities = config.get('cities', [])
    keywords = config.get('search_keywords', [])
    max_per_source = config.get('scraper', {}).get('max_jobs_per_source', 50)
    city_codes = config.get('liepin_city_codes', {})

    for city in cities[:5]:  # 限制城市数量
        city_code = city_codes.get(city, '')
        for kw in keywords[:3]:
            try:
                # 猎聘搜索URL
                url = f"https://www.liepin.com/zhaopin/"
                params = {
                    'city': city_code,
                    'key': kw,
                    'dq': city_code if city_code else '',
                }

                resp = http_client.get(url, params=params)
                if not resp:
                    continue

                soup = BeautifulSoup(resp.text, 'lxml')

                # 尝试多种选择器
                cards = soup.select('.job-list-item')
                if not cards:
                    cards = soup.select('.job-card')
                if not cards:
                    cards = soup.select('[class*="job"]')

                for card in cards:
                    try:
                        title_el = card.select_one('[class*="title"], .job-title, h3 a')
                        company_el = card.select_one('[class*="company"], .company-name')
                        salary_el = card.select_one('[class*="salary"], .job-salary')
                        city_el = card.select_one('[class*="area"], .job-area, [class*="city"]')
                        desc_el = card.select_one('[class*="desc"], .job-desc, [class*="info"]')

                        title = clean_text(title_el.get_text()) if title_el else ''
                        company = clean_text(company_el.get_text()) if company_el else ''
                        salary = clean_text(salary_el.get_text()) if salary_el else ''
                        city_text = clean_text(city_el.get_text()) if city_el else ''
                        desc = clean_text(desc_el.get_text()) if desc_el else ''

                        if not title or not company:
                            continue

                        city_norm = normalize_city(city_text, cities)
                        if not city_norm:
                            # 从URL参数中推断
                            city_norm = city if city in cities else None

                        if not city_norm:
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
                            'desc': desc,
                            'requirements': [],
                            'tags': [],
                            'status': '可投递',
                            'note': '',
                        }
                        job['tags'] = extract_tags(
                            job['title'] + ' ' + job['desc'],
                            config.get('search_keywords', [])
                        )
                        all_jobs.append(job)

                        if len(all_jobs) >= max_per_source:
                            break
                    except Exception:
                        continue
            except Exception as e:
                print(f"  猎聘抓取异常 ({city}/{kw}): {e}")
                continue

            if len(all_jobs) >= max_per_source:
                break
        if len(all_jobs) >= max_per_source:
            break

    return all_jobs
