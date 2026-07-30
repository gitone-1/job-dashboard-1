"""
微信公众号招聘信息扫描配置
每次运行 update_pipeline 时自动遍历以下公众号近两个月的招聘内容
"""

import json
from datetime import datetime, timedelta

# ── 核心必扫公众号（用户指定） ──────────────────────────
CORE_SOURCES = [
    {
        "name": "苏州本地宝招聘",
        "account": "本地宝苏州招聘",
        "search_keywords": ["苏州本地宝 招聘 国企 运营 数据 数字化 2026"],
        "base_url": "https://suzhou.bendibao.com/job/",
        "type": "bendibao",
        "target_cities": ["苏州"],
    },
    {
        "name": "杭州本地宝招聘",
        "account": "本地宝杭州招聘",
        "search_keywords": ["杭州本地宝 招聘 国企 运营 数据 数字化 2026"],
        "base_url": "https://hz.bendibao.com/job/",
        "type": "bendibao",
        "target_cities": ["杭州"],
    },
    {
        "name": "国资小新",
        "account": "国资小新",
        "search_keywords": [
            "国资小新 招聘 苏州 杭州 运营 数据 数字化 2026",
            "国资小新 招聘 江苏 浙江 运营 数字化 2026",
        ],
        "type": "wechat",
        "target_cities": ["苏州", "杭州", "无锡", "嘉兴", "常州"],
    },
]

# ── 专精特新/瞪羚/独角兽企业扫描 ──────────────────
# 策略：从政府公示名单中提取企业名称，然后去其官网/公众号/BOSS直聘搜索招聘信息
GAOCHENGZHANG_ENTERPRISES = {
    "description": "专精特新小巨人/瞪羚/独角兽企业反向搜索",
    "search_method": "先搜认定名单→提取企业→搜其招聘",
    "苏州": {
        "独角兽企业": [
            "企查查科技", "智慧芽", "聚合数据（天聚地合）", "思必驰", "同元软控",
            "清睿智能", "盖雅工场", "云学堂", "艾隆科技", "纳芯微电子",
        ],
        "瞪羚企业": [
            "苏州精控能源", "苏州海鹏科技", "苏州瑞可达", "苏州瀚川智能",
            "苏州华兴源创", "苏州天准科技", "苏州绿的谐波", "苏州明皜传感",
        ],
        "专精特新小巨人": [
            "苏州轴承厂", "苏州海格电控", "江苏苏净集团", "创元科技",
            "苏州国芯科技", "苏州长光华芯", "苏州东微半导体",
        ],
    },
    "杭州": {
        "独角兽企业": [
            "DeepSeek（深度求索）", "邦盛科技", "酷家乐（群核科技）", "灵犀科技",
            "丁香园", "婚礼纪", "微脉", "微医", "禾连健康", "Babycare",
        ],
        "准独角兽企业": [
            "有赞", "涂鸦智能", "鲸灵集团", "闪修侠", "卖好车", "珊瑚跨境",
            "八维通", "聚玻网", "车点点", "麦瑞克",
        ],
        "专精特新小巨人": [
            "杭州迪普科技", "杭州安恒信息", "杭州当虹科技", "杭州宏杉科技",
            "杭州中控技术", "杭州品茗科技",
        ],
    },
    "search_keyword_template": "{company} 招聘 运营 数据 产品 2026 社招",
}

# ── 苏杭外企名单 ──────────────────────────────
# 苏州185家世界500强、杭州众多知名外企，按行业分类
FOREIGN_ENTERPRISES = {
    "description": "苏州和杭州的外企/外资企业反向搜索",
    "search_method": "按行业分类→搜索企业招聘信息",
    "苏州": {
        "科技与电子": [
            "博世（Bosch）", "三星电子（Samsung）", "西门子（Siemens）",
            "富士通（Fujitsu）", "松下（Panasonic）", "佳能（Canon）",
            "日立（Hitachi）", "飞利浦（Philips）", "霍尼韦尔（Honeywell）",
            "泰科电子（TE Connectivity）", "通富超威（TF-AMD）", "楼氏电子（Knowles）",
        ],
        "汽车与零部件": [
            "舍弗勒（Schaeffler）", "博格华纳（BorgWarner）", "采埃孚（ZF）",
            "耐世特（Nexteer）", "麦格纳（Magna）", "大陆集团（Continental）",
            "丰田（Toyota）", "本田（Honda）", "日产（Nissan）",
        ],
        "工业与自动化": [
            "SEW传动设备", "ABB", "艾默生（Emerson）", "施耐德（Schneider）",
            "罗克韦尔（Rockwell）", "费斯托（Festo）", "倍加福（Pepperl+Fuchs）",
        ],
        "医药与生命科学": [
            "礼来（Eli Lilly）", "辉瑞（Pfizer）", "强生（Johnson & Johnson）",
            "葛兰素史克（GSK）", "罗氏（Roche）", "碧迪医疗（BD）",
            "赛默飞（Thermo Fisher）", "丹纳赫（Danaher）", "奥林巴斯（Olympus）",
        ],
        "消费品与零售": [
            "耐克（Nike）", "阿迪达斯（Adidas）", "宝洁（P&G）",
            "联合利华（Unilever）", "雀巢（Nestle）", "亿滋（Mondelez）",
            "欧莱雅（L'Oreal）",
        ],
        "互联网与软件": [
            "微软（Microsoft）", "SAP", "甲骨文（Oracle）",
            "思科（Cisco）", "惠普（HP）", "亚马逊（Amazon）",
        ],
    },
    "杭州": {
        "科技与互联网": [
            "思科（Cisco）", "ZOOM", "诺基亚（Nokia）",
            "道富银行（State Street）", "微策略（MicroStrategy）",
            "惠普（HP）", "亚马逊（Amazon）AWS",
        ],
        "工业与自动化": [
            "ABB", "西门子（Siemens）", "博世（Bosch）",
            "松下（Panasonic）", "史陶比尔（Staubli）",
            "通用电气（GE）",
        ],
        "医药与生命科学": [
            "默沙东（MSD）", "拜耳（Bayer）", "阿斯利康（AstraZeneca）",
            "赛诺菲（Sanofi）", "诺华（Novartis）", "辉瑞（Pfizer）",
            "罗氏（Roche）", "礼来（Eli Lilly）",
        ],
        "消费品与零售": [
            "宝洁（P&G）", "联合利华（Unilever）", "可口可乐（Coca-Cola）",
            "百事（PepsiCo）", "欧莱雅（L'Oreal）",
        ],
        "金融与咨询": [
            "摩根士丹利（Morgan Stanley）", "汇丰银行（HSBC）",
            "花旗银行（Citibank）", "渣打银行（Standard Chartered）",
        ],
    },
    "search_keyword_template": "{company} 招聘 运营 数据 产品 数字化 苏州 OR 杭州 2026",
}

# ── 自动发现的补充公众号 ──────────────────────────
AUTO_DISCOVERED = [
    {
        "name": "苏州各国企官方公众号",
        "search_keywords": [
            "苏州城投集团 招聘 运营 数据 2026",
            "苏州交投集团 招聘 运营 数据 2026",
            "苏州国投集团 招聘 产品 数据 2026",
            "苏州轨道交通 招聘 运营 数字化 2026",
        ],
        "note": "通过苏州本地宝发现的各国企招聘公告来源",
    },
    {
        "name": "杭州各国企官方公众号",
        "search_keywords": [
            "杭州数据集团 招聘 运营 产品 2026",
            "杭州城投集团 招聘 运营 数字化 2026",
            "杭州商旅集团 招聘 运营 数据 2026",
            "杭州交投集团 招聘 运营 数字化 2026",
        ],
        "note": "通过杭州本地宝发现的各国企招聘公告来源",
    },
    {
        "name": "知名企业招聘公众号",
        "search_keywords": [
            "阿里巴巴招聘 苏州 杭州 运营 数据 2026",
            "华为招聘 苏州 杭州 数据运营 2026",
            "海康威视招聘 杭州 数据运营 2026",
            "博世中国人才苑 苏州 数字化 2026",
            "西门子招聘 苏州 数字化 运营 2026",
            "卡特彼勒招聘 苏州 数字化 2026",
        ],
        "note": "外企及大厂官方招聘公众号",
    },
    {
        "name": "高校人才网",
        "search_keywords": [
            "高校人才网 苏州 国企 运营 数据 2026",
            "高校人才网 杭州 国企 运营 数据 2026",
        ],
        "note": "高校人才网经常转载各国企招聘公告",
    },
]

# ── 用户画像（用于岗位匹配） ──────────────────────────
USER_PROFILE = {
    "name": "王婷婷",
    "target_roles": ["数据运营", "产品运营", "用户运营", "数字化运营", "策略运营", "平台运营"],
    "exclude_roles": ["数据标注", "AI训练师", "经理", "主管", "总监", "专家"],
    "target_cities": ["苏州", "杭州", "无锡", "嘉兴", "常州", "湖州", "绍兴"],
    "target_industries": ["互联网", "国企", "外企", "数字科技", "金融科技"],
    "keywords": ["运营", "数据", "产品", "数字化", "用户增长", "数据分析"],
    "experience": "5-8年",
    "education": "本科（山东科技大学 通信工程）",
    "skills": ["PowerBI", "SQL", "Excel", "数据分析", "用户运营", "指标体系搭建"],
}

# ── 扫描时间范围 ──────────────────────────
SCAN_RANGE = {
    "months": 2,
    "from_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
}


def get_all_search_queries():
    """生成所有搜索查询关键词组"""
    queries = []
    for src in CORE_SOURCES:
        queries.extend(src.get("search_keywords", []))
    for src in AUTO_DISCOVERED:
        queries.extend(src.get("search_keywords", []))
    # 生成高成长企业搜索词
    for city, categories in GAOCHENGZHANG_ENTERPRISES.items():
        if city in ["苏州", "杭州"]:
            for cat_name, companies in categories.items():
                for company in companies:
                    queries.append(f"{company} 招聘 运营 数据 产品 2026 社招")
    # 生成外企搜索词
    for city, categories in FOREIGN_ENTERPRISES.items():
        if city in ["苏州", "杭州"]:
            for cat_name, companies in categories.items():
                for company in companies:
                    queries.append(f"{company} 招聘 运营 数据 产品 数字化 {city} 2026")
    return queries


def get_source_config():
    """返回完整扫描配置"""
    return {
        "core_sources": CORE_SOURCES,
        "gaochengzhang_enterprises": GAOCHENGZHANG_ENTERPRISES,
        "foreign_enterprises": FOREIGN_ENTERPRISES,
        "auto_discovered": AUTO_DISCOVERED,
        "user_profile": USER_PROFILE,
        "scan_range": SCAN_RANGE,
    }


if __name__ == "__main__":
    config = get_source_config()
    # 统计各类企业数量
    gao_count = sum(len(v) for city in GAOCHENGZHANG_ENTERPRISES.values() if isinstance(city, dict) for v in city.values())
    foreign_count = sum(len(v) for city in FOREIGN_ENTERPRISES.values() if isinstance(city, dict) for v in city.values())
    print(f"核心公众号: {len(CORE_SOURCES)} 个")
    print(f"高成长企业(专精特新/瞪羚/独角兽): {gao_count} 家")
    print(f"外企/外资企业: {foreign_count} 家")
    print(f"自动发现: {len(AUTO_DISCOVERED)} 组")
    print(f"搜索词组: {len(get_all_search_queries())} 个")
    print(f"扫描范围: 近{SCAN_RANGE['months']}个月 (从{SCAN_RANGE['from_date']}起)")
