"""
大厂招聘 API 数据源 - 直接请求各公司公开 API
"""
import json
from typing import List, Dict, Any
from utils.http_client import HTTPClient
from utils.parser import clean_text, extract_salary_range, extract_tags, normalize_city, classify_company_type


def scrape_apis(config: Dict, http_client: HTTPClient) -> List[Dict]:
    """
    抓取各大厂招聘 API
    注意：部分 API 可能需要 cookie/认证，失败时返回空列表
    """
    all_jobs = []
    cities = config.get('cities', [])
    keywords = config.get('search_keywords', [])
    api_endpoints = config.get('api_endpoints', {})

    # 阿里巴巴
    ali_jobs = _scrape_alibaba(api_endpoints, http_client, cities, keywords, config)
    if ali_jobs:
        print(f"  阿里巴巴 API: {len(ali_jobs)} 条")
    all_jobs.extend(ali_jobs)

    # 字节跳动
    bytedance_jobs = _scrape_bytedance(api_endpoints, http_client, cities, keywords, config)
    if bytedance_jobs:
        print(f"  字节跳动 API: {len(bytedance_jobs)} 条")
    all_jobs.extend(bytedance_jobs)

    # 腾讯
    tencent_jobs = _scrape_tencent(api_endpoints, http_client, cities, keywords, config)
    if tencent_jobs:
        print(f"  腾讯 API: {len(tencent_jobs)} 条")
    all_jobs.extend(tencent_jobs)

    return all_jobs


def _scrape_alibaba(endpoints: Dict, client: HTTPClient, cities: List[str],
                    keywords: List[str], config: Dict) -> List[Dict]:
    """阿里巴巴招聘 API"""
    jobs = []
    try:
        # 阿里公开搜索API
        url = endpoints.get('alibaba', 'https://talent.alibaba.com/api/search')
        for city in cities[:3]:  # 只搜前3个城市，控制请求量
            for kw in keywords[:2]:
                params = {
                    'city': city,
                    'keyword': kw,
                    'pageSize': 20,
                    'pageIndex': 1,
                }
                resp = client.get(url, params=params)
                if not resp:
                    continue

                try:
                    data = resp.json()
                    items = data.get('data', {}).get('list', [])
                    if not items:
                        items = data.get('content', [])
                except Exception:
                    continue

                for item in items:
                    job = {
                        'company': '阿里巴巴',
                        'type': classify_company_type('阿里巴巴', config),
                        'title': clean_text(item.get('name', item.get('title', ''))),
                        'city': normalize_city(item.get('city', item.get('workCity', '')), cities),
                        'salary': extract_salary_range(item.get('salary', '')),
                        'url': item.get('url', item.get('detailUrl', '')),
                        'source': '阿里巴巴招聘API',
                        'source_type': 'api',
                        'desc': clean_text(item.get('description', item.get('jobDesc', ''))),
                        'requirements': _parse_requirements(item),
                        'tags': [],
                        'status': '可投递',
                        'note': '',
                    }
                    if job['city'] and job['title']:
                        job['tags'] = extract_tags(
                            job['title'] + ' ' + job['desc'],
                            config.get('search_keywords', [])
                        )
                        jobs.append(job)
    except Exception as e:
        print(f"  阿里巴巴 API 异常: {e}")
    return jobs


def _scrape_bytedance(endpoints: Dict, client: HTTPClient, cities: List[str],
                      keywords: List[str], config: Dict) -> List[Dict]:
    """字节跳动招聘 API"""
    jobs = []
    try:
        url = endpoints.get('bytedance', 'https://jobs.bytedance.com/api/search')
        for city in cities[:3]:
            for kw in keywords[:2]:
                resp = client.post(url, json_data={
                    'city': city,
                    'keyword': kw,
                    'limit': 20,
                    'offset': 0,
                })
                if not resp:
                    continue
                try:
                    data = resp.json()
                    items = data.get('data', {}).get('jobPostList', [])
                except Exception:
                    continue

                for item in items:
                    job = {
                        'company': '字节跳动',
                        'type': classify_company_type('字节跳动', config),
                        'title': clean_text(item.get('title', item.get('name', ''))),
                        'city': normalize_city(item.get('city', ''), cities),
                        'salary': extract_salary_range(item.get('salary', '')),
                        'url': item.get('url', item.get('detailUrl', '')),
                        'source': '字节跳动招聘API',
                        'source_type': 'api',
                        'desc': clean_text(item.get('description', '')),
                        'requirements': _parse_requirements(item),
                        'tags': [],
                        'status': '可投递',
                        'note': '',
                    }
                    if job['city'] and job['title']:
                        job['tags'] = extract_tags(
                            job['title'] + ' ' + job['desc'],
                            config.get('search_keywords', [])
                        )
                        jobs.append(job)
    except Exception as e:
        print(f"  字节跳动 API 异常: {e}")
    return jobs


def _scrape_tencent(endpoints: Dict, client: HTTPClient, cities: List[str],
                    keywords: List[str], config: Dict) -> List[Dict]:
    """腾讯招聘 API"""
    jobs = []
    try:
        url = endpoints.get('tencent', 'https://careers.tencent.com/api/search')
        for city in cities[:3]:
            for kw in keywords[:2]:
                resp = client.post(url, json_data={
                    'city': city,
                    'keyword': kw,
                    'pageSize': 20,
                    'pageIndex': 1,
                })
                if not resp:
                    continue
                try:
                    data = resp.json()
                    items = data.get('Data', {}).get('Posts', [])
                except Exception:
                    continue

                for item in items:
                    job = {
                        'company': '腾讯',
                        'type': classify_company_type('腾讯', config),
                        'title': clean_text(item.get('RecruitPostName', item.get('title', ''))),
                        'city': normalize_city(item.get('LocationName', item.get('city', '')), cities),
                        'salary': extract_salary_range(item.get('Salary', '')),
                        'url': item.get('PostURL', item.get('url', '')),
                        'source': '腾讯招聘API',
                        'source_type': 'api',
                        'desc': clean_text(item.get('Responsibility', item.get('description', ''))),
                        'requirements': _parse_requirements(item),
                        'tags': [],
                        'status': '可投递',
                        'note': '',
                    }
                    if job['city'] and job['title']:
                        job['tags'] = extract_tags(
                            job['title'] + ' ' + job['desc'],
                            config.get('search_keywords', [])
                        )
                        jobs.append(job)
    except Exception as e:
        print(f"  腾讯 API 异常: {e}")
    return jobs


def _parse_requirements(item: Dict) -> List[str]:
    """解析任职要求"""
    reqs = []
    req_text = item.get('requirement', item.get('qualification', item.get('requirements', '')))
    if isinstance(req_text, str):
        # 按句号或换行拆分
        import re
        parts = re.split(r'[。；\n;]', req_text)
        reqs = [r.strip() for r in parts if len(r.strip()) > 5]
    elif isinstance(req_text, list):
        reqs = req_text
    return reqs[:6]  # 最多6条
