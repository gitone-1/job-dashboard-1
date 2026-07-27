"""
微信公众号岗位抓取 — 改用 Playwright 模拟移动端微信搜索
绕过搜狗网页版的反爬限制
"""
import json
import random
import re
import time
from typing import List, Dict, Any


def scrape_wechat(config: Dict, http_client=None) -> List[Dict]:
    """
    微信岗位抓取
    方案：使用 Playwright 模拟移动端访问搜狗微信搜索
    移动端 User-Agent + 慢速操作，降低反爬概率
    """
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ⚠️ Playwright 未安装，跳过微信公众号")
        return []

    all_jobs = []
    cities = config.get('cities', [])[:3]
    keywords = config.get('search_keywords', [])[:4]
    max_jobs = config.get('scraper', {}).get('max_jobs_per_source', 50)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage']
        )

        # 使用移动端 User-Agent，减少反爬
        context = browser.new_context(
            user_agent="Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1",
            viewport={"width": 390, "height": 844},
            locale="zh-CN",
        )
        page = context.new_page()

        for kw in keywords[:3]:
            for city in cities[:2]:
                if len(all_jobs) >= max_jobs:
                    break
                try:
                    query = f"{kw} {city} 招聘 社招"
                    url = f"https://weixin.sogou.com/weixin?type=2&query={query}"
                    print(f"  微信搜索: {kw} {city}")

                    page.goto(url, wait_until="domcontentloaded", timeout=15000)
                    time.sleep(random.uniform(2, 4))

                    # 检测反爬验证码
                    content = page.content()
                    if '请输入验证码' in content or 'antispider' in content.lower():
                        print(f"    ⚠️ 触发验证码，跳过 {city}/{kw}")
                        time.sleep(10)
                        continue

                    # 提取文章列表
                    articles = page.query_selector_all('.news-list li, .txt-box, .news-item, .weui-media-box')
                    print(f"    找到 {len(articles)} 篇文章")

                    for article in articles[:10]:
                        if len(all_jobs) >= max_jobs:
                            break
                        try:
                            title_el = article.query_selector('h3, .tit, .weui-media-box__title')
                            title = title_el.inner_text().strip() if title_el else ''

                            desc_el = article.query_selector('.txt-info, .desc, .weui-media-box__desc')
                            desc = desc_el.inner_text().strip() if desc_el else ''

                            account_el = article.query_selector('.account, .s2, .weui-media-box__info__meta')
                            account = account_el.inner_text().strip() if account_el else ''

                            link_el = article.query_selector('a[href*="mp.weixin.qq.com"]')
                            link = link_el.get_attribute('href') if link_el else ''

                            if not title:
                                continue

                            full_text = f"{title} {desc}"

                            # 检查是否是招聘岗位文章
                            job_signals = ['招聘', '社招', '岗位', '职位', '热招', '急招', '诚聘']
                            if not any(s in full_text for s in job_signals):
                                continue

                            # 公众号身份过滤
                            if not _is_official_account(account):
                                continue

                            # 提取角色
                            found_roles = re.findall(
                                r'(数据运营|产品运营|策略运营|用户运营|电商运营|'
                                r'增长运营|数字化运营|社区运营|平台运营|内容运营|'
                                r'客户运营|活动运营|运营专员|运营助理|数据分析|'
                                r'数据产品|商业分析|业务运营)',
                                full_text
                            )

                            if not found_roles:
                                continue

                            # 提取公司名
                            company = _extract_company(full_text, account, config)

                            # 提取薪资
                            salary_match = re.search(
                                r'(\d+[-~]\d+[kK])|(\d+[-~]\d+万)|(月薪\s*\d+[-~]\d+[kK])',
                                full_text
                            )
                            salary = salary_match.group(0) if salary_match else '面议'

                            # 提取截止日期
                            deadline_match = re.search(
                                r'(截止|截止时间|截止日期)[:：]?\s*(\d{4}[-/]\d{1,2}[-/]\d{1,2})',
                                full_text
                            )
                            deadline = deadline_match.group(2) if deadline_match else ''

                            from utils.parser import classify_company_type, extract_salary_range

                            job = {
                                'company': company,
                                'type': classify_company_type(company, config),
                                'title': found_roles[0],
                                'city': city,
                                'salary': extract_salary_range(salary),
                                'deadline': deadline,
                                'url': link,
                                'source': f'微信公众号({account})',
                                'source_type': 'wechat',
                                'desc': full_text[:300],
                                'requirements': [],
                                'tags': list(set(found_roles[:5])),
                                'status': '可投递',
                                'note': f'来源公众号: {account}',
                                'recruit_type': '社招',
                            }
                            all_jobs.append(job)

                        except Exception as e:
                            continue

                    time.sleep(random.uniform(3, 6))

                except Exception as e:
                    print(f"  微信搜索异常 ({kw}/{city}): {e}")
                    continue

            if len(all_jobs) >= max_jobs:
                break

        browser.close()

    return all_jobs


def _is_official_account(account_name: str) -> bool:
    """检查是否是官方企业招聘公众号"""
    if not account_name or len(account_name.strip()) < 2:
        return False

    name = account_name.strip()

    # 黑名单关���词
    blacklist = [
        '个人', '学长', '学姐', '老师', '哥', '姐', '叔', '妈',
        '日记', '笔记', '随记', '分享', '生活', '日常', 'vlog',
        '成长', '记录', '心得', '小屋', '小站', '空间',
        '培训', '教育', '学院', '课堂', '课程', '学习', '辅导', '考试',
        '公考', '考编', '考研', '考公', '面试', '笔试', '真题', '题库',
        '中公', '华图', '粉笔', '学而思', '新东方', '高途',
        '猎头', '猎聘', '中介', '派遣', '外包', '劳务', '代招',
        '内推君', '内推哥', '内推达人', '直推', '帮推',
        '职场', '求职', '找工作', '就业',
        '干货', '技巧', '攻略', '秘籍', '指南',
        '头条', '快讯', '资讯', '速递', '早知道', '每日',
        '汇总', '合集', '精选', '大集合', '大盘点', '最全',
        'offer', 'Offer', 'OFFER',
    ]
    for kw in blacklist:
        if kw.lower() in name.lower():
            return False

    # 白名单关键词
    whitelist = [
        '招聘', '人才', '人力资源', 'HR', 'careers',
        '集团', '公司', '有限公司', '股份', '官方', '微招聘',
        '企业', '人才苑', '人才港',
    ]
    for kw in whitelist:
        if kw.lower() in name.lower():
            return True

    # 长度过滤
    if len(name) < 3 or len(name) > 18:
        return False

    return True


def _extract_company(text: str, account_name: str, config: Dict) -> str:
    """从文本和公众号名中提取公司名"""
    # 先尝试从已知公司列表匹配
    for type_key, companies in config.get('company_types', {}).items():
        for company in companies:
            if company in account_name or company in text[:100]:
                return company

    # 尝试从【】中提取
    bracket_match = re.search(r'【(.+?)】', text[:50])
    if bracket_match:
        name = bracket_match.group(1)
        if len(name) <= 10:
            return name

    # 从文本中匹配已知公司
    for type_key, companies in config.get('company_types', {}).items():
        for company in companies:
            if company in text[:200]:
                return company

    # 从公众号名推断
    return account_name.replace('招聘', '').replace('微招聘', '').replace('人才苑', '').strip() or '未知公司'
