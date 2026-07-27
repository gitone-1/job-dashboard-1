"""
国聘爬虫 - 抓取 iguopin.com (国资央企招聘平台)
"""
import json
from typing import List, Dict, Any
from utils.http_client import HTTPClient
from utils.parser import clean_text, extract_salary_range, extract_tags, normalize_city, classify_company_type


def scrape_guopin(config: Dict, http_client: HTTPClient) -> List[Dict]:
    """
    抓取国聘平台岗位数据
    国聘有公开的搜索API，JSON响应，解析最方便
    """
    all_jobs = []
    cities = config.get('cities', [])
    keywords = config.get('search_keywords', [])
    max_per_source = config.get('scraper', {}).get('max_jobs_per_source', 50)

    # 国聘搜索API
    search_url = "https://www.iguopin.com/api/search"

    for city in cities:
        for kw in keywords[:3]:  # 限制关键词数量
            try:
                resp = http_client.post(search_url, json_data={
                    'city': city,
                    'keyword': kw,
                    'page': 1,
                    'pageSize': 20,
                })
                if not resp:
                    continue

                data = resp.json()
                items = data.get('data', {}).get('list', [])
                if not items:
                    items = data.get('data', [])

                for item in items:
                    title = clean_text(item.get('jobName', item.get('name', item.get('title', ''))))
                    company = clean_text(item.get('companyName', item.get('company', item.get('enterpriseName', ''))))
                    if not title or not company:
                        continue

                    city_norm = normalize_city(
                        item.get('city', item.get('workCity', item.get('location', ''))),
                        cities
                    )
                    if not city_norm:
                        continue

                    job = {
                        'company': company,
                        'type': classify_company_type(company, config),
                        'title': title,
                        'city': city_norm,
                        'salary': extract_salary_range(item.get('salary', item.get('salaryRange', ''))),
                        'deadline': item.get('endTime', item.get('deadline', '')),
                        'url': item.get('url', item.get('detailUrl', '')),
                        'source': '国聘',
                        'source_type': 'guopin',
                        'desc': clean_text(item.get('description', item.get('jobDesc', item.get('duty', '')))),
                        'requirements': _parse_guopin_reqs(item),
                        'tags': [],
                        'status': '可投递',
                        'note': _get_guopin_note(item),
                    }

                    job['tags'] = extract_tags(
                        job['title'] + ' ' + job['desc'],
                        config.get('search_keywords', [])
                    )
                    all_jobs.append(job)

                    if len(all_jobs) >= max_per_source:
                        break
            except Exception as e:
                print(f"  国聘抓取异常 ({city}/{kw}): {e}")
                continue

            if len(all_jobs) >= max_per_source:
                break
        if len(all_jobs) >= max_per_source:
            break

    return all_jobs


def _parse_guopin_reqs(item: Dict) -> List[str]:
    """解析国聘岗位的任职要求"""
    req_text = item.get('qualification', item.get('requirement', item.get('requirements', '')))
    if isinstance(req_text, str):
        import re
        parts = re.split(r'[。；\n;]', req_text)
        return [r.strip() for r in parts if len(r.strip()) > 5][:6]
    if isinstance(req_text, list):
        return req_text[:6]
    return []


def _get_guopin_note(item: Dict) -> str:
    """获取国聘岗位的备注信息"""
    notes = []
    if item.get('isUrgent'):
        notes.append('急招')
    if item.get('needExam'):
        notes.append('需笔试')
    return '，'.join(notes)
