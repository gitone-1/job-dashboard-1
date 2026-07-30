#!/usr/bin/env python3
"""
手动更新流水线 — 将 WebSearch 定向采集的新岗位合并进 jobs.json
复用 pipeline 的去重 / 匹配 / 状态恢复 / 版本化逻辑，但不依赖易崩溃的 Playwright 爬虫。
"""
import json
import sys
import time
import re
import argparse
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from utils.logger import setup_logger, get_today_str
from pipeline.dedup import DedupEngine
from pipeline.matcher import MatchEngine


def load_json(path):
    p = Path(path)
    if p.exists():
        with open(p, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def save_json(path, data):
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def update_index_data_ref(versioned_name, logger=None):
    index_path = Path('index.html')
    if not index_path.exists():
        return
    html = index_path.read_text(encoding='utf-8')
    new_html = re.sub(r"jobs_v\d+\.json", versioned_name, html)
    if new_html != html:
        index_path.write_text(new_html, encoding='utf-8')
        if logger:
            logger.info(f"✅ 更新 index.html 数据引用: {versioned_name}")


def restore_user_status(merged_jobs, logger=None):
    """从 user_status.json（本地+远程）恢复用户标注状态，避免已标记岗位回弹。"""
    status_map = load_json('user_status.json') or {}
    try:
        import urllib.request
        resp = urllib.request.urlopen(
            'https://gitone-1.github.io/job-dashboard-1/user_status.json?t=' + str(int(time.time())))
        remote_status = json.loads(resp.read())
        for k, v in remote_status.items():
            if k not in status_map:
                status_map[k] = v
    except Exception as e:
        if logger:
            logger.warning(f"读取远程用户状态失败(使用本地): {e}")

    if not status_map:
        return

    key_to_job = {}
    for j in merged_jobs:
        key = j.get('_meta', {}).get('fingerprint', '') or (j['company'] + '|' + j['title'] + '|' + j['city'])
        key_to_job[key] = j

    restored = 0
    for key, val in status_map.items():
        if key in key_to_job:
            st = val if isinstance(val, str) else val.get('status')
            if st and st != '可投递' and st in ('不匹配', '已关闭', '已投递'):
                key_to_job[key]['status'] = st
                restored += 1
    if logger:
        logger.info(f"✅ 恢复用户状态: {restored} 条 (不匹配/已关闭/已投递)")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', default='data/new_jobs_20260730.json')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    logger = setup_logger()
    logger.info("=" * 60)
    logger.info("手动更新流水线启动 (WebSearch 定向采集)")
    logger.info("=" * 60)

    try:
        import yaml
        with open('config.yaml', 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f) or {}
    except Exception:
        config = {}
    profile = load_json('resume_profile.json')
    if not profile:
        logger.error("resume_profile.json 不存在！")
        return

    existing = load_json('jobs.json') or []
    logger.info(f"现有岗位: {len(existing)} 条")

    new_jobs = load_json(args.seed) or []
    logger.info(f"待合并新岗位: {len(new_jobs)} 条")

    match_engine = MatchEngine(profile)

    # 预过滤：排除管理岗 / 非目标城市
    filtered = [j for j in new_jobs if match_engine.should_include(j, config)]
    # 标记新岗位，便于后续仅对新岗位计算匹配度/过滤（保留现有岗位原匹配度与状态）
    for j in filtered:
        j['_new_flag'] = True
    logger.info(f"预过滤后新岗位: {len(filtered)} 条")

    # 去重合并
    dedup = DedupEngine('data/state.db')
    merged, new_count = dedup.merge_and_dedup(existing, filtered,
                                              threshold=config.get('pipeline', {}).get('dedup_threshold', 0.85))
    logger.info(f"去重合并后: {len(merged)} 条 (新增 {new_count} 条)")

    # 仅对新岗位计算匹配度；现有岗位保留其原有(前端算法)匹配度，避免被误删
    min_match = config.get('pipeline', {}).get('min_match_score', 50)
    kept = []
    for j in merged:
        if j.pop('_new_flag', False):
            j['match'] = match_engine.calc_match_score(j)
            if j['match'] < min_match:
                logger.info(f"  新岗位匹配度过低，剔除: {j['company']} - {j['title']} ({j['match']}%)")
                continue
        kept.append(j)
    merged = kept
    logger.info(f"过滤低匹配度(<{min_match})后: {len(merged)} 条 (保留全部现有岗位)")

    # 标记过期
    freshness = config.get('pipeline', {}).get('freshness_days', 30)
    merged = dedup.mark_expired(merged, freshness)

    # 排序
    merged.sort(key=lambda j: j.get('match', 0), reverse=True)

    # 重新分配 ID
    for i, j in enumerate(merged, 1):
        j['id'] = i

    # 更新元数据
    today = get_today_str()
    for j in merged:
        meta = j.setdefault('_meta', {})
        if not meta.get('last_updated'):
            meta['last_updated'] = today

    if args.dry_run:
        logger.info(f"[试运行] 将生成 {len(merged)} 条，新增 {new_count} 条，不写入文件")
        for j in filtered:
            logger.info(f"  候选: [{match_engine.calc_match_score(j)}%] {j['company']} - {j['title']} ({j['city']})")
        return

    # 恢复用户状态（不匹配/已关闭/已投递 不回弹）
    restore_user_status(merged, logger)

    save_json('jobs.json', merged)
    logger.info(f"✅ jobs.json 已更新: {len(merged)} 条岗位")

    versioned_name = f'jobs_v{int(time.time())}.json'
    save_json(versioned_name, merged)
    update_index_data_ref(versioned_name, logger)

    logger.info(f"=== 完成: 共 {len(merged)} 个岗位，新增 {new_count} 条 ===")


if __name__ == '__main__':
    main()
