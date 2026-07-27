# -*- coding: utf-8 -*-
"""
WeChat scraper - dual-mode with official account filtering
"""
import re
import time
import random
from typing import List, Dict, Any
from bs4 import BeautifulSoup
from utils.http_client import HTTPClient
from utils.parser import clean_text, extract_salary_range, extract_tags, normalize_city, classify_company_type

# Account blacklist keywords
ACCOUNT_BLACKLIST = [
    '个人', '学长', '学姐', '老师', '哥', '姐', '叔', '妈',
    '日记', '笔记', '随记', '分享', '生活', '日常', 'vlog',
    '成长', '记录', '心得', '小屋', '小站', '空间',
    '培训', '教育', '学院', '课堂', '课程', '学习', '辅导', '考试',
    '公考', '考编', '考研', '考公', '面试', '笔试', '真题', '题库',
    '中公', '华图', '粉笔', '学而思', '新东方', '高途',
    '猎头', '猎聘', '中介', '派遣', '外包', '劳务', '代招',
    '内推君', '内推哥', '内推达人', '直推', '帮推', '内推',
    '职场', '求职', '找工作', '就业', '实习', '校招助手', '招聘信息',
    '干货', '技巧', '攻略', '秘籍', '指南',
    '头条', '快讯', '资讯', '速递', '早知道', '每日',
    '汇总', '合集', '精选', '大集合', '大盘点', '最全',
    'offer', 'Offer', 'OFFER',
]

ACCOUNT_WHITELIST = [
    '招聘', '人才', '人力资源', 'HR', 'careers',
    '集团', '公司', '有限公司', '股份', '官方', '微招聘',
    '企业', '人才苑', '人才港',
    '微软', '亚马逊', '谷歌', '苹果', '宝洁', '联合利华', '博世', 'SAP',
    '西门子', 'IBM', '英特尔', '戴姆勒', '奔驰', '辉瑞', '诺华', '罗氏',
    '飞利浦', '施耐德', 'ABB', '通用电气', '卡特彼勒', 'SK海力士', '药明康德',
    '阿里巴巴', '腾讯', '字节跳动', '美团', '京东', '网易', '拼多多',
    '小红书', '快手', '蚂蚁', '百度', '滴滴', '哔哩哔哩', '携程', '同程',
    '华为', '吉利', '比亚迪', '海康威视', '大华', '浙江中控',
    '中国移动', '中国电信', '中国联通', '国家电网', '中石化', '中国石油',
    '国家能源', '中粮', '华润', '中国烟草', '中国邮政', '招商局',
    '中国铁塔', '中广核', '国投', '敏实', '天能',
    '国家数据', '人社', '公务员', '国聘',
]


def _is_official_account(account_name):
    if not account_name or len(account_name.strip()) < 2:
        return False
    name = account_name.strip()
    for kw in ACCOUNT_BLACKLIST:
        if kw.lower() in name.lower():
            return False
    for kw in ACCOUNT_WHITELIST:
        if kw.lower() in name.lower():
            return True
    if len(name) < 3 or len(name) > 18:
        return False
    if any(kw in name for kw in ['招聘', '人才', 'HR', '人事', '官方']):
        return True
    return True


def _is_job_article(title, summary):
    full_text = title + ' ' + summary
    ad_words = ['报名', '试听', '免费课', '体验课', '特训营', '训练营',
                '包过', '保过', '通过率', '上岸', '提分',
                '限时优惠', '团购', '折扣', '早鸟', '秒杀']
    if any(w in full_text for w in ad_words):
        return False
    job_signals = ['招聘', '社招', '校招', '岗位', '职位', 'JD', '热招', '急招', '诚聘']
    if not any(w in full_text for w in job_signals):
        return False
    # 排除汇总/盘点类非招聘文章
    summary_words = ['大盘点', '汇总', '合集', '精选', '盘点', '最全', '一览']
    if any(w in full_text for w in summary_words) and '【' not in title:
        return False
    return True


def scrape_wechat(config, http_client):
    all_jobs = []
    max_total = config.get('scraper', {}).get('max_jobs_per_source', 50)
    keyword_jobs = _search_by_keywords(config, http_client)
    print(f"  模式1(关键词+身份过滤): {len(keyword_jobs)} 条")
    all_jobs.extend(keyword_jobs)
    if len(all_jobs) < max_total:
        source_jobs = _search_by_sources(config, http_client, max_total - len(all_jobs))
        print(f"  模式2(公众号清单): {len(source_jobs)} 条")
        all_jobs.extend(source_jobs)
    seen_urls = set()
    unique_jobs = []
    for job in all_jobs:
        url = job.get('url', '')
        if url and url in seen_urls:
            continue
        if url:
            seen_urls.add(url)
        unique_jobs.append(job)
    return unique_jobs[:max_total]


def _search_by_keywords(config, http_client):
    jobs = []
    cities = config.get('cities', [])
    job_keywords = [
        '数据运营 招聘', '产品运营 招聘', '策略运营 招聘',
        '用户运营 招聘', '增长运营 招聘', '数字化运营 招聘',
        '运营数据分析 招聘',
    ]
    for kw in job_keywords[:5]:
        for city in cities[:5]:
            try:
                query = f"{kw} {city}"
                url = f"https://weixin.sogou.com/weixin?type=2&query={query}"
                resp = http_client.get(url)
                if not resp:
                    continue
                soup = BeautifulSoup(resp.text, 'lxml')
                articles = soup.select('.news-list li, .txt-box')
                for article in articles[:8]:
                    try:
                        title_el = article.select_one('h3 a, .tit a')
                        if not title_el:
                            continue
                        title = clean_text(title_el.get_text())
                        link = title_el.get('href', '')
                        summary_el = article.select_one('.txt-info, .s-p')
                        summary = clean_text(summary_el.get_text()) if summary_el else ''
                        account_el = article.select_one('.account, .s2')
                        account_name = clean_text(account_el.get_text()) if account_el else ''
                        if not _is_official_account(account_name):
                            continue
                        full_text = title + ' ' + summary
                        if not _is_job_article(title, summary):
                            continue
                        found_roles = re.findall(
                            r'(数据运营|产品运营|策略运营|用户运营|电商运营|'
                            r'增长运营|数字化运营|社区运营|平台运营|内容运营|'
                            r'客户运营|活动运营|运营专员|运营助理|数据分析)',
                            full_text
                        )
                        found_city = None
                        for c in cities:
                            if c in full_text:
                                found_city = c
                                break
                        if not found_city:
                            found_city = city
                        salary_match = re.search(
                            r'(\d+[-~]\d+[kK])|(\d+[-~]\d+万)|(月薪\s*\d+[-~]\d+[kK])',
                            full_text
                        )
                        salary = salary_match.group(0) if salary_match else '面议'
                        company = _extract_company(full_text, account_name, config)
                        deadline_match = re.search(
                            r'(截止|截止时间|截止日期)[:：]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                            full_text
                        )
                        deadline = deadline_match.group(2) if deadline_match else ''
                        role_title = found_roles[0] if found_roles else kw.split()[0]
                        job = {
                            'company': company, 'type': classify_company_type(company, config),
                            'title': role_title, 'city': found_city,
                            'salary': extract_salary_range(salary),
                            'deadline': deadline, 'url': link,
                            'source': f'微信({account_name})', 'source_type': 'wechat',
                            'desc': full_text[:300],
                            'requirements': _extract_requirements(full_text),
                            'tags': list(set(found_roles[:5])),
                            'status': '可投递', 'note': f'来源公众号: {account_name}',
                        }
                        jobs.append(job)
                    except Exception:
                        continue
                time.sleep(random.uniform(2, 4))
            except Exception as e:
                print(f"  微信关键词搜索异常 ({kw}/{city}): {e}")
                continue
    return jobs


def _search_by_sources(config, http_client, limit):
    jobs = []
    cities = config.get('cities', [])
    sources = config.get('wechat_sources', [])

    # 用户指定必搜号，优先级最高
    priority_sources = ['国资小新', '苏州本地宝', '杭州本地宝']
    all_sources = priority_sources + [s for s in sources if s not in priority_sources]

    for source in all_sources[:25]:
        for city in cities[:3]:
            if len(jobs) >= limit:
                return jobs
            try:
                query = f"{source} 招聘 {city}"
                url = f"https://weixin.sogou.com/weixin?type=2&query={query}"
                resp = http_client.get(url)
                if not resp:
                    continue
                soup = BeautifulSoup(resp.text, 'lxml')
                articles = soup.select('.news-list li, .txt-box')
                for article in articles[:5]:
                    if len(jobs) >= limit:
                        return jobs
                    try:
                        title_el = article.select_one('h3 a, .tit a')
                        if not title_el:
                            continue
                        title = clean_text(title_el.get_text())
                        link = title_el.get('href', '')
                        summary_el = article.select_one('.txt-info, .s-p')
                        summary = clean_text(summary_el.get_text()) if summary_el else ''
                        full_text = title + ' ' + summary
                        found_roles = re.findall(
                            r'(数据运营|产品运营|策略运营|用户运营|电商运营|'
                            r'增长运营|数字化运营|社区运营|平台运营|内容运营|'
                            r'客户运营|活动运营|运营专员|运营助理|数据分析)',
                            full_text
                        )
                        if not found_roles:
                            continue
                        company = _infer_company(source, config)
                        city_norm = city if city in cities else None
                        salary_match = re.search(r'(\d+[-~]\d+[kK])|(\d+[-~]\d+万)', full_text)
                        salary = salary_match.group(0) if salary_match else '面议'
                        job = {
                            'company': company, 'type': classify_company_type(company, config),
                            'title': found_roles[0], 'city': city_norm or city,
                            'salary': extract_salary_range(salary), 'url': link,
                            'source': f'微信公众号({source})', 'source_type': 'wechat',
                            'desc': full_text[:300],
                            'requirements': _extract_requirements(full_text),
                            'tags': list(set(found_roles[:5])),
                            'status': '可投递', 'note': '来自官方招聘号',
                        }
                        jobs.append(job)
                    except Exception:
                        continue
                time.sleep(random.uniform(1, 3))
            except Exception as e:
                print(f"  微信公众号搜索异常 ({source}): {e}")
                continue
    return jobs


def _extract_company(text, account_name, config):
    if account_name:
        for type_key, companies in config.get('company_types', {}).items():
            for company in companies:
                if company in account_name or company in text[:100]:
                    return company
    bracket_match = re.search(r'【(.+?)】', text[:50])
    if bracket_match:
        name = bracket_match.group(1)
        if len(name) <= 10:
            return name
    for type_key, companies in config.get('company_types', {}).items():
        for company in companies:
            if company in text[:200]:
                return company
    return account_name or '未知公司'


def _extract_requirements(text):
    reqs = []
    req_match = re.search(
        r'(任职要求|岗位要求|职位要求|我们需要你|希望你)[:：]?\s*(.+?)(?=岗位职责|工作内容|薪资|福利|$)',
        text, re.DOTALL
    )
    if req_match:
        req_text = req_match.group(2)
        parts = re.split(r'[。；;]', req_text)
        reqs = [r.strip() for r in parts if len(r.strip()) > 5][:5]
    return reqs


def _infer_company(source, config):
    for type_key, companies in config.get('company_types', {}).items():
        for company in companies:
            if company in source:
                return company
    return source.replace('招聘', '').replace('微招聘', '').strip()
