"""
匹配度计算引擎 - 与前端 calcMatchScore 算法完全一致
"""
import re
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
        """判断岗位是否应该被收录（含用户硬性过滤规则）"""
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

        # 用户硬性过滤规则（2026-07-30 新增，详见 RETROSPECTIVE.md 第五章）
        #   1) 明确要求 Python（必需）的岗去掉；"Python 优先" 保留
        #   2) 国企/事业单位 且 要求硕士 的去掉；私企要求硕士 保留
        if self.hard_exclude(job):
            return False

        return True

    def is_public_sector(self, job: Dict) -> bool:
        """是否为国企/事业单位（用户规则：此类要求硕士才去掉，私企不去掉）"""
        t = job.get('type', '')
        if t in ('state', 'gov', '国企'):
            return True
        blob = ' '.join([str(job.get('company', '')), str(job.get('source', '')),
                         str(job.get('note', ''))]).lower()
        for kw in ['国资', '国企', '事业单位', '事业编', '研究院', '局', '委']:
            if kw in blob:
                return True
        return False

    def _mentions_without_pref(self, text: str, pattern: str) -> bool:
        """text 中是否存在 pattern 的提及，且附近没有「优先 / prefer」（即"必需"而非"优先"）"""
        for m in re.finditer(pattern, text):
            seg = text[max(0, m.start() - 22): m.start() + 18]
            if '优先' not in seg and 'prefer' not in seg.lower():
                return True
        return False

    def hard_exclude(self, job: Dict) -> str:
        """返回硬过滤原因；None 表示不排除。

        规则（用户 2026-07-30）：
          - 明确要求 Python（必需）→ 去掉；"Python 优先" → 保留
          - 国企/事业单位 且 要求硕士 → 去掉；私企要求硕士 → 保留
        """
        blob = ' '.join([
            str(job.get('title', '')), str(job.get('desc', '')),
            ' '.join(job.get('requirements', [])), str(job.get('note', ''))
        ]).lower()
        if self._mentions_without_pref(blob, r'python|pyhon'):
            return '要求Python(必需)'
        if self.is_public_sector(job) and self._mentions_without_pref(blob, r'硕士|研究生|master'):
            return '国企/事业单位要求硕士'
        return None

    def compute_all(self, jobs: List[Dict]) -> List[Dict]:
        """批量计算所有岗位的匹配度"""
        for job in jobs:
            job['match'] = self.calc_match_score(job)
        return jobs
