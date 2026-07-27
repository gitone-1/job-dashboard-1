#!/usr/bin/env python3
"""
求职工作台 - 每日数据更新流水线

用法:
    python3 pipeline/pipeline.py                    # 完整流水线
    python3 pipeline/pipeline.py --source api       # 仅抓取API数据源
    python3 pipeline/pipeline.py --dry-run          # 试运行（不写入jobs.json）
"""
import json
import sys
import os
import time
import argparse
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

# 添加项目根目录到 path
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.http_client import HTTPClient
from utils.logger import setup_logger, get_today_str
from pipeline.dedup import DedupEngine
from pipeline.matcher import MatchEngine

# 爬虫模块
from pipeline.api_sources import scrape_apis
from pipeline.scraper_guopin import scrape_guopin
from pipeline.scraper_liepin import scrape_liepin
from pipeline.scraper_boss import scrape_boss
from pipeline.scraper_wechat import scrape_wechat


def load_yaml(path: str) -> Dict:
    """加载 YAML 配置"""
    try:
        import yaml
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)
    except ImportError:
        print("⚠️ PyYAML 未安装，使用默认配置")
        return {}


def load_json(path: str) -> Any:
    """加载 JSON 文件"""
    path = Path(path)
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_json(path: str, data: Any):
    """保存 JSON 文件"""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def archive_raw_data(jobs: List[Dict], data_dir: str = "data/jobs_raw"):
    """存档原始抓取数据"""
    path = Path(data_dir)
    path.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    save_json(path / f"raw_{timestamp}.json", jobs)


def run_pipeline(source_filter: str = None, dry_run: bool = False):
    """运行完整流水线"""
    logger = setup_logger()
    logger.info("=" * 60)
    logger.info(f"求职工作台 - 每日岗位更新流水线启动")
    logger.info(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info("=" * 60)

    # 1. 加载配置
    config = load_yaml('config.yaml')
    profile = load_json('resume_profile.json')
    if not profile:
        logger.error("简历画像 (resume_profile.json) 不存在！")
        return None

    # 2. 加载现有数据
    existing_jobs = load_json('jobs.json') or []
    logger.info(f"现有岗位: {len(existing_jobs)} 条")

    # 3. 初始化 HTTP 客户端
    http_client = HTTPClient(config)

    # 4. 抓取新数据
    raw_jobs = []

    if source_filter is None or source_filter == "api":
        logger.info("[1/5] 抓取大厂招聘 API...")
        try:
            api_jobs = scrape_apis(config, http_client)
            logger.info(f"  API 源: {len(api_jobs)} 条")
            raw_jobs.extend(api_jobs)
        except Exception as e:
            logger.error(f"  API 抓取失败: {e}")

    if source_filter is None or source_filter == "guopin":
        logger.info("[2/5] 抓取国聘...")
        try:
            guopin_jobs = scrape_guopin(config, http_client)
            logger.info(f"  国聘: {len(guopin_jobs)} 条")
            raw_jobs.extend(guopin_jobs)
        except Exception as e:
            logger.error(f"  国聘抓取失败: {e}")

    if source_filter is None or source_filter == "liepin":
        logger.info("[3/5] 抓取猎聘...")
        try:
            liepin_jobs = scrape_liepin(config, http_client)
            logger.info(f"  猎聘: {len(liepin_jobs)} 条")
            raw_jobs.extend(liepin_jobs)
        except Exception as e:
            logger.error(f"  猎聘抓取失败: {e}")

    if source_filter is None or source_filter == "boss":
        logger.info("[4/5] 抓取 BOSS直聘 (Playwright)...")
        try:
            boss_jobs = scrape_boss(config)
            logger.info(f"  BOSS直聘: {len(boss_jobs)} 条")
            raw_jobs.extend(boss_jobs)
        except Exception as e:
            logger.error(f"  BOSS直聘抓取失败: {e}")

    if source_filter is None or source_filter == "wechat":
        logger.info("[5/5] 抓取微信公众号...")
        try:
            wechat_jobs = scrape_wechat(config, http_client)
            logger.info(f"  微信公众号: {len(wechat_jobs)} 条")
            raw_jobs.extend(wechat_jobs)
        except Exception as e:
            logger.error(f"  微信公众号抓取失败: {e}")

    http_client.close()
    logger.info(f"原始抓取总计: {len(raw_jobs)} 条")

    if not raw_jobs:
        logger.warning("未抓取到任何新岗位！")
        return existing_jobs

    # 5. 预过滤：排除管理岗、非目标城市
    match_engine = MatchEngine(profile)
    filtered_jobs = []
    for job in raw_jobs:
        if match_engine.should_include(job, config):
            filtered_jobs.append(job)
    logger.info(f"预过滤后: {len(filtered_jobs)} 条 (排除管理岗/非目标城市)")

    # 6. 去重合并
    dedup_engine = DedupEngine('data/state.db')
    merged_jobs, new_count = dedup_engine.merge_and_dedup(
        existing_jobs, filtered_jobs,
        threshold=config.get('pipeline', {}).get('dedup_threshold', 0.85)
    )
    logger.info(f"去重合并后: {len(merged_jobs)} 条 (新增 {new_count} 条)")

    # 7. 计算匹配度
    merged_jobs = match_engine.compute_all(merged_jobs)

    # 8. 过滤低匹配度
    min_match = config.get('pipeline', {}).get('min_match_score', 50)
    merged_jobs = [j for j in merged_jobs if j.get('match', 0) >= min_match]
    logger.info(f"过滤低匹配度(<{min_match})后: {len(merged_jobs)} 条")

    # 9. 标记过期岗位
    freshness_days = config.get('pipeline', {}).get('freshness_days', 30)
    merged_jobs = dedup_engine.mark_expired(merged_jobs, freshness_days)

    # 10. 排序（按匹配度降序）
    merged_jobs.sort(key=lambda j: j.get('match', 0), reverse=True)

    # 11. 重新分配 ID
    for i, job in enumerate(merged_jobs, 1):
        job['id'] = i

    # 12. 更新元数据
    today = get_today_str()
    for job in merged_jobs:
        meta = job.setdefault('_meta', {})
        if not meta.get('last_updated'):
            meta['last_updated'] = today

    # 13. 写入文件或试运行
    if dry_run:
        logger.info(f"[试运行] 将生成 {len(merged_jobs)} 条岗位，但不写入文件")
        # 打印 TOP 5
        for j in merged_jobs[:5]:
            logger.info(f"  [{j.get('match', 0)}%] {j.get('company')} - {j.get('title')} ({j.get('city')})")
    else:
        save_json('jobs.json', merged_jobs)
        logger.info(f"✅ jobs.json 已更新: {len(merged_jobs)} 条岗位")

        # 存档原始数据
        archive_raw_data(raw_jobs)

        # 更新抓取历史
        dedup_engine.update_scrape_history(
            source_filter or 'all',
            len(raw_jobs),
            new_count
        )

    # 14. 更新数据文件时间戳
    update_time_file(today)

    logger.info(f"=== 流水线完成: 共 {len(merged_jobs)} 个岗位 ===")
    return merged_jobs


def update_time_file(date_str: str):
    """更新最后更新时间文件"""
    with open('data/last_update.txt', 'w') as f:
        f.write(date_str)


def main():
    parser = argparse.ArgumentParser(description='求职工作台 - 每日数据更新流水线')
    parser.add_argument('--source', type=str, default=None,
                        choices=['api', 'guopin', 'liepin', 'boss', 'wechat'],
                        help='仅抓取指定数据源')
    parser.add_argument('--dry-run', action='store_true',
                        help='试运行模式，不写入文件')
    args = parser.parse_args()

    run_pipeline(source_filter=args.source, dry_run=args.dry_run)


if __name__ == '__main__':
    main()
