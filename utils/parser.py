"""
通用解析器 - HTML/JSON 解析与字段标准化
"""
import re
from typing import Optional, List, Dict, Any
from bs4 import BeautifulSoup


def clean_text(text: str) -> str:
    """清洗文本：去除多余空白、换行等"""
    if not text:
        return ""
    text = re.sub(r'\s+', ' ', text)
    text = text.replace('\n', ' ').replace('\r', ' ').replace('\t', ' ')
    return text.strip()


def extract_salary_range(salary_text: str) -> str:
    """标准化薪资格式为 XX-XXK·X薪"""
    if not salary_text:
        return "面议"

    text = salary_text.strip()

    # 已经格式化好的
    if re.match(r'\d+-\d+K', text):
        return text

    # 处理"15k-25k"格式
    m = re.search(r'(\d+)\s*[kK]\s*[-~到]\s*(\d+)\s*[kK]', text)
    if m:
        base = f"{m.group(1)}-{m.group(2)}K"
        # 检查是否有薪数
        sal = re.search(r'(\d+)\s*薪', text)
        if sal:
            base += f"·{sal.group(1)}薪"
        return base

    # 处理"15000-25000"格式
    m = re.search(r'(\d{4,5})\s*[-~到]\s*(\d{4,5})', text)
    if m:
        low = int(int(m.group(1)) / 1000)
        high = int(int(m.group(2)) / 1000)
        return f"{low}-{high}K"

    # 处理"月薪15000"格式
    m = re.search(r'(\d{4,5})', text)
    if m:
        k = int(int(m.group(1)) / 1000)
        return f"{k}K"

    return text if len(text) < 20 else "面议"


def extract_tags(text: str, config_tags: List[str] = None) -> List[str]:
    """从文本中提取技能标签"""
    if not config_tags:
        config_tags = [
            "SQL", "Python", "Excel", "PowerBI", "Tableau",
            "数据分析", "数据运营", "产品运营", "用户运营", "策略运营",
            "电商运营", "平台运营", "内容运营", "增长", "CRM",
            "A/B测试", "数据可视化", "指标体系", "项目管理"
        ]

    text_lower = text.lower()
    found = []
    for tag in config_tags:
        if tag.lower() in text_lower:
            found.append(tag)

    return found[:8]  # 最多8个标签


def normalize_city(city: str, target_cities: List[str]) -> Optional[str]:
    """城市名标准化"""
    if not city:
        return None

    city = city.strip()
    for target in target_cities:
        if target in city:
            return target

    # 常见别名映射
    aliases = {
        "上海": ["上海市", "沪"],
        "苏州": ["苏州市", "工业园区", "吴中", "吴江", "昆山", "张家港", "常熟", "太仓"],
        "杭州": ["杭州市", "余杭", "西湖", "滨江", "萧山", "钱塘"],
        "无锡": ["无锡市", "江阴", "宜兴"],
        "嘉兴": ["嘉兴市", "海宁", "桐乡", "平湖"],
        "湖州": ["湖州市", "德清", "长兴"],
        "常州": ["常州市", "武进", "溧阳"],
        "绍兴": ["绍兴市", "柯桥", "诸暨", "上虞"],
    }

    for std_name, aliases_list in aliases.items():
        for alias in aliases_list:
            if alias in city:
                return std_name

    return None


def classify_company_type(company_name: str, config: Dict[str, List[str]]) -> str:
    """根据公司名判断公司类型"""
    for type_key, companies in config.get("company_types", {}).items():
        for keyword in companies:
            if keyword in company_name:
                return type_key
    return "other"


def parse_html_job_list(html: str, selector_map: Dict[str, str]) -> List[Dict]:
    """通用的HTML岗位列表解析器"""
    soup = BeautifulSoup(html, 'lxml')
    results = []

    # 使用选择器映射来定位元素
    cards = soup.select(selector_map.get("card", ".job-card"))
    if not cards:
        cards = soup.select(selector_map.get("card_fallback", ".job-list-item"))

    for card in cards:
        try:
            title_el = card.select_one(selector_map.get("title", ".job-title"))
            company_el = card.select_one(selector_map.get("company", ".company-name"))
            salary_el = card.select_one(selector_map.get("salary", ".salary"))
            city_el = card.select_one(selector_map.get("city", ".city"))
            link_el = card.select_one(selector_map.get("link", "a"))

            title = clean_text(title_el.get_text()) if title_el else ""
            company = clean_text(company_el.get_text()) if company_el else ""
            salary = clean_text(salary_el.get_text()) if salary_el else ""
            city = clean_text(city_el.get_text()) if city_el else ""
            link = link_el.get("href", "") if link_el else ""

            if not title or not company:
                continue

            results.append({
                "title": title,
                "company": company,
                "salary": salary,
                "city": city,
                "url": link,
            })
        except Exception as e:
            continue

    return results
