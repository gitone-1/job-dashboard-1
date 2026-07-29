"""
去重引擎 - 三级去重策略 (URL -> 内容指纹 -> 语义相似度)
"""
import json
import hashlib
import sqlite3
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class DedupEngine:
    """岗位去重引擎，基于 SQLite 存储指纹"""

    def __init__(self, db_path: str = "data/state.db"):
        self.db_path = db_path
        self._init_db()

    def _init_db(self):
        """初始化数据库表"""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(self.db_path) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS job_fingerprints (
                    fingerprint TEXT PRIMARY KEY,
                    job_id INTEGER,
                    first_seen TEXT NOT NULL,
                    last_seen TEXT NOT NULL,
                    source_count INTEGER DEFAULT 1,
                    sources TEXT,
                    is_active INTEGER DEFAULT 1
                )
            """)
            conn.execute("""
                CREATE TABLE IF NOT EXISTS scrape_history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source TEXT NOT NULL,
                    scraped_at TEXT NOT NULL,
                    jobs_found INTEGER DEFAULT 0,
                    jobs_new INTEGER DEFAULT 0,
                    errors TEXT
                )
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_fingerprint_active
                ON job_fingerprints(is_active)
            """)
            conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_scrape_date
                ON scrape_history(scraped_at)
            """)
            conn.commit()

    def _compute_fingerprint(self, job: Dict) -> str:
        """计算岗位内容指纹 (company + title + city 的 SHA256)"""
        key = f"{job.get('company', '')}|{job.get('title', '')}|{job.get('city', '')}"
        return hashlib.sha256(key.encode('utf-8')).hexdigest()[:16]

    def _compute_url_fingerprint(self, url: str) -> str:
        """计算URL指纹"""
        if not url:
            return ""
        # 去掉 URL 中的查询参数和尾部斜杠
        clean_url = url.split('?')[0].rstrip('/')
        return hashlib.sha256(clean_url.encode('utf-8')).hexdigest()[:16]

    def _jaccard_similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的 Jaccard 相似度"""
        if not text1 or not text2:
            return 0.0
        # 使用2-gram字符级
        def ngrams(text, n=2):
            return set(text[i:i+n] for i in range(len(text) - n + 1))
        set1, set2 = ngrams(text1), ngrams(text2)
        if not set1 or not set2:
            return 0.0
        intersection = len(set1 & set2)
        union = len(set1 | set2)
        return intersection / union if union > 0 else 0.0

    def is_duplicate(self, job: Dict, existing_jobs: List[Dict], threshold: float = 0.85) -> Optional[Dict]:
        """检查岗位是否重复，返回重复的已有岗位或 None"""

        # Level 1: URL 精确匹配（仅当URL包含具体岗位ID时才去重，排除搜索页/首页URL）
        url_fp = self._compute_url_fingerprint(job.get('url', ''))
        if url_fp:
            # 跳过通用搜索页URL（如 /zhaopin/ /search/ /list 等），这类URL多个岗位可能共用
            job_url = job.get('url', '')
            is_generic_url = any(x in job_url for x in [
                '/search', '/zhaopin/', '/list', '/city-', '/job/',
                'iguopin.com/', 'zhipin.com/gongsi/job/', 'liepin.com/company/',
            ])
            if not is_generic_url:
                for ej in existing_jobs:
                    ej_url_fp = self._compute_url_fingerprint(ej.get('url', ''))
                    if url_fp and ej_url_fp and url_fp == ej_url_fp:
                        return ej

        # Level 2: 内容指纹匹配
        fp = self._compute_fingerprint(job)
        for ej in existing_jobs:
            ej_fp = self._compute_fingerprint(ej)
            if fp == ej_fp:
                return ej

        # Level 3: 语义相似度匹配
        job_text = f"{job.get('company', '')} {job.get('title', '')} {job.get('desc', '')}"
        for ej in existing_jobs:
            ej_text = f"{ej.get('company', '')} {ej.get('title', '')} {ej.get('desc', '')}"
            sim = self._jaccard_similarity(job_text[:200], ej_text[:200])
            if sim >= threshold:
                return ej

        return None

    def merge_and_dedup(self, existing: List[Dict], new: List[Dict],
                        threshold: float = 0.85) -> List[Dict]:
        """
        合并新旧岗位数据，去重后返回。
        策略：保留 match 分更高的版本，合并 source 信息。
        """
        merged = list(existing)  # 拷贝现有数据
        today = datetime.now().strftime("%Y-%m-%d")
        new_count = 0

        for job in new:
            dup = self.is_duplicate(job, merged, threshold)
            if dup:
                # 更新已有岗位
                if job.get('match', 0) > dup.get('match', 0):
                    # 新数据匹配分更高，替换核心字段
                    for field in ['match', 'desc', 'requirements', 'tags', 'salary', 'deadline']:
                        if job.get(field):
                            dup[field] = job[field]
                # 合并 source 信息
                if job.get('source') and job['source'] not in str(dup.get('_meta', {}).get('sources', '')):
                    meta = dup.setdefault('_meta', {})
                    sources = meta.get('sources', [])
                    if isinstance(sources, str):
                        sources = json.loads(sources)
                    if job['source'] not in sources:
                        sources.append(job['source'])
                    meta['sources'] = sources
                # 更新最后见到的时间
                dup.setdefault('_meta', {})['last_seen'] = today
            else:
                # 新岗位
                job.setdefault('_meta', {})
                job['_meta']['first_seen'] = today
                job['_meta']['last_seen'] = today
                job['_meta']['sources'] = [job.get('source', 'unknown')]
                merged.append(job)
                new_count += 1

                # 更新指纹数据库
                fp = self._compute_fingerprint(job)
                self._save_fingerprint(fp, job, today)

        return merged, new_count

    def _save_fingerprint(self, fp: str, job: Dict, today: str):
        """保存指纹到数据库"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT OR REPLACE INTO job_fingerprints
                    (fingerprint, first_seen, last_seen, sources, is_active)
                    VALUES (?, ?, ?, ?, 1)
                """, (fp, today, today, json.dumps([job.get('source', 'unknown')], ensure_ascii=False)))
                conn.commit()
        except Exception:
            pass

    def update_scrape_history(self, source: str, jobs_found: int, jobs_new: int, errors: str = ""):
        """记录抓取历史"""
        try:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("""
                    INSERT INTO scrape_history (source, scraped_at, jobs_found, jobs_new, errors)
                    VALUES (?, ?, ?, ?, ?)
                """, (source, datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                      jobs_found, jobs_new, errors))
                conn.commit()
        except Exception:
            pass

    def mark_expired(self, jobs: List[Dict], freshness_days: int = 30) -> List[Dict]:
        """将超过 freshness_days 天未更新的岗位标记为过期"""
        from datetime import timedelta
        cutoff = (datetime.now() - timedelta(days=freshness_days)).strftime("%Y-%m-%d")

        for job in jobs:
            last_seen = job.get('_meta', {}).get('last_seen', '')
            if last_seen and last_seen < cutoff and job.get('status') == '可投递':
                job['status'] = '已截止'
                job['note'] = job.get('note', '') + ' [已过期]'
            # 已标记不匹配/已关闭/已投递的岗位不会被重置

        return jobs
