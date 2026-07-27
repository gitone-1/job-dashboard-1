"""
匹配度计算引擎 - 与前端 calcMatchScore 算法完全一致
"""
from typing import Dict, List


class MatchEngine:
    """岗位匹配度计算引擎"""

    def __init__(self, profile: Dict):
        self.profile = profile
        self.skills = [s.lower() for s in profile.get('skills', [])]
        self.roles = [r.lower() for r in profile.get('roles', [])]
        self.keywords = [k.lower() for k in profile.get('keywords', [])]

    def calc_match_score(self, job: Dict) -> int:
        """
        计算岗位匹配度 (0-100)
        4维度加权评分，与前端 calcMatchScore 保持一致
        """
        score = 0
        all_text = self._get_job_text(job).lower()

        # 1. 技能匹配 (40%)
        tags = job.get('tags', [])
        skill_hits = 0
        for skill in self.skills:
            if any(skill in t.lower() for t in tags) or skill in all_text:
                skill_hits += 1
        score += min(skill_hits / max(len(tags), 1) * 40, 40)

        # 2. 角色匹配 (30%)
        role_hits = sum(1 for r in self.roles if r in (
            job.get('title', '') + ' ' + job.get('desc', '')).lower())
        score += 30 if role_hits > 0 else (20 if '运营' in job.get('title', '') else 10)

        # 3. 关键词匹配 (20%)
        kw_hits = sum(1 for k in self.keywords if k in all_text)
        score += min(kw_hits / 5 * 20, 20)

        # 4. 经验匹配 (10%)
        if any(x in all_text for x in ['5年', '5年以上', '5-8年']):
            score += 10
        elif any(x in all_text for x in ['3年', '3-5年', '3年以上']):
            score += 7
        else:
            score += 5

        return min(round(score), 100)

    def _get_job_text(self, job: Dict) -> str:
        """获取岗位的全文信息"""
        parts = [
            job.get('title', ''),
            job.get('desc', ''),
            ' '.join(job.get('tags', [])),
            ' '.join(job.get('requirements', [])),
        ]
        return ' '.join(parts)

    def should_include(self, job: Dict, config: Dict) -> bool:
        """判断岗位是否应该被收录"""
        title_lower = job.get('title', '').lower()

        # 排除管理岗
        exclude_kw = config.get('exclude_title_keywords', [])
        for kw in exclude_kw:
            if kw.lower() in title_lower:
                return False

        # 排除非目标城市
        target_cities = config.get('cities', [])
        city = job.get('city', '')
        if city and city not in target_cities:
            return False

        return True

    def compute_all(self, jobs: List[Dict]) -> List[Dict]:
        """批量计算所有岗位的匹配度"""
        for job in jobs:
            job['match'] = self.calc_match_score(job)
        return jobs
