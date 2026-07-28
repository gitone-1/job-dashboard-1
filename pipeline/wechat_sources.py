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
        "type": "bendibao",  # 本地宝类型，优先从bendibao.com抓取
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
        "target_cities": ["苏州", "杭州", "上海", "无锡", "嘉兴", "常州"],
    },
]

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
    "target_cities": ["苏州", "杭州", "上海", "无锡", "嘉兴", "常州", "湖州", "绍兴"],
    "target_industries": ["互联网", "国企", "外企", "数字科技", "金融科技"],
    "keywords": ["运营", "数据", "产品", "数字化", "用户增长", "数据分析"],
    "experience": "5-8年",
    "education": "本科（山东科技大学 通信工程）",
    "skills": ["PowerBI", "SQL", "Excel", "数据分析", "用户运营", "指标体系搭建"],
}

# ── 扫描时间范围 ──────────────────────────
SCAN_RANGE = {
    "months": 2,  # 扫描近2个月
    "from_date": (datetime.now() - timedelta(days=60)).strftime("%Y-%m-%d"),
}


def get_all_search_queries():
    """生成所有搜索查询关键词组"""
    queries = []
    for src in CORE_SOURCES:
        queries.extend(src.get("search_keywords", []))
    for src in AUTO_DISCOVERED:
        queries.extend(src.get("search_keywords", []))
    return queries


def get_source_config():
    """返回完整扫描配置"""
    return {
        "core_sources": CORE_SOURCES,
        "auto_discovered": AUTO_DISCOVERED,
        "user_profile": USER_PROFILE,
        "scan_range": SCAN_RANGE,
    }


if __name__ == "__main__":
    config = get_source_config()
    print(f"核心公众号: {len(CORE_SOURCES)} 个")
    print(f"自动发现: {len(AUTO_DISCOVERED)} 个")
    print(f"搜索词组: {len(get_all_search_queries())} 个")
    print(f"扫描范围: 近{SCAN_RANGE['months']}个月 (从{SCAN_RANGE['from_date']}起)")
    print(f"\n完整配置:\n{json.dumps(config, ensure_ascii=False, indent=2)}")
