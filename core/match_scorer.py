"""
匹配度分数计算器

基于明确的权重规则计算简历-JD匹配分数，确保分数透明、可解释。
"""

import logging
from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class MatchStatus(Enum):
    """匹配状态"""
    FULLY_MATCHED = "fully_matched"      # 完全匹配
    PARTIALLY_MATCHED = "partially_matched"  # 部分匹配
    NOT_MATCHED = "not_matched"          # 不匹配
    EXCEEDS = "exceeds"                  # 超出要求
    UNKNOWN = "unknown"                  # 无法判断


class RequirementType(Enum):
    """要求类型"""
    MUST_HAVE = "must_have"      # 硬性要求
    NICE_TO_HAVE = "nice_to_have"  # 加分项
    PREFERRED = "preferred"      # 优先项


@dataclass
class RequirementMatch:
    """单个要求的匹配情况"""
    requirement: str              # JD 原文要求
    requirement_type: RequirementType  # 要求类型
    match_status: MatchStatus     # 匹配状态
    resume_evidence: str = ""     # 简历中的依据
    score_impact: int = 0         # 对分数的影响（正数加分，负数扣分）
    explanation: str = ""         # 解释说明


@dataclass
class MatchScoreResult:
    """匹配分数计算结果"""
    score: int = 60                           # 最终分数 (0-100)
    level: str = "待提升"                      # 等级
    breakdown: Dict[str, int] = field(default_factory=dict)  # 分数明细
    requirements_analysis: List[RequirementMatch] = field(default_factory=list)  # 各项分析
    summary: str = ""                         # 总结说明

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'score': self.score,
            'level': self.level,
            'breakdown': self.breakdown,
            'summary': self.summary,
            'requirements': [
                {
                    'requirement': r.requirement,
                    'type': r.requirement_type.value,
                    'status': r.match_status.value,
                    'evidence': r.resume_evidence,
                    'impact': r.score_impact,
                    'explanation': r.explanation
                }
                for r in self.requirements_analysis
            ]
        }


class MatchScorer:
    """匹配度分数计算器"""

    # 基础分数
    BASE_SCORE = 60

    # 分数范围
    MIN_SCORE = 0
    MAX_SCORE = 100

    # 要求类型对应的分数影响
    SCORE_IMPACTS = {
        # 硬性要求
        (RequirementType.MUST_HAVE, MatchStatus.FULLY_MATCHED): 10,
        (RequirementType.MUST_HAVE, MatchStatus.PARTIALLY_MATCHED): 3,
        (RequirementType.MUST_HAVE, MatchStatus.NOT_MATCHED): -20,
        (RequirementType.MUST_HAVE, MatchStatus.EXCEEDS): 12,
        # 加分项
        (RequirementType.NICE_TO_HAVE, MatchStatus.FULLY_MATCHED): 6,
        (RequirementType.NICE_TO_HAVE, MatchStatus.PARTIALLY_MATCHED): 2,
        (RequirementType.NICE_TO_HAVE, MatchStatus.NOT_MATCHED): 0,  # 加分项不匹配不扣分
        (RequirementType.NICE_TO_HAVE, MatchStatus.EXCEEDS): 8,
        # 优先项
        (RequirementType.PREFERRED, MatchStatus.FULLY_MATCHED): 5,
        (RequirementType.PREFERRED, MatchStatus.PARTIALLY_MATCHED): 2,
        (RequirementType.PREFERRED, MatchStatus.NOT_MATCHED): 0,
        (RequirementType.PREFERRED, MatchStatus.EXCEEDS): 6,
        # 未知状态
        (RequirementType.MUST_HAVE, MatchStatus.UNKNOWN): -5,
        (RequirementType.NICE_TO_HAVE, MatchStatus.UNKNOWN): 0,
        (RequirementType.PREFERRED, MatchStatus.UNKNOWN): 0,
    }

    # 分数等级
    SCORE_LEVELS = [
        (80, "优秀匹配", "简历与职位高度匹配，建议突出差异化优势"),
        (60, "良好匹配", "简历与职位基本匹配，建议优化待提升项"),
        (40, "待提升", "简历与职位有一定差距，建议重点提升核心要求"),
        (0, "高风险/低匹配", "简历与职位匹配度较低，建议重点补充核心技能"),
    ]

    # 学历映射
    EDUCATION_LEVELS = {
        '高中': 1, '中专': 1, '大专': 2, '专科': 2,
        '本科': 3, '学士': 3, '硕士': 4, '研究生': 4,
        '博士': 5, '博士后': 6
    }

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def calculate_score(
        self,
        jd_requirements: List[Dict[str, Any]],
        resume_data: Dict[str, Any],
        ai_analysis: Optional[Dict[str, Any]] = None
    ) -> MatchScoreResult:
        """
        计算匹配分数

        Args:
            jd_requirements: JD 要求列表，每项包含:
                - requirement: 要求描述（JD原文）
                - type: must_have/nice_to_have/preferred
                - category: education/experience/skill/age/salary/other
                - value: 具体值（可选）
            resume_data: 简历数据
            ai_analysis: AI 分析结果（可选，用于辅助判断）

        Returns:
            MatchScoreResult: 计算结果
        """
        result = MatchScoreResult()
        score = self.BASE_SCORE
        breakdown = {
            '基础分': self.BASE_SCORE,
            '硬性要求匹配': 0,
            '加分项匹配': 0,
            '优先项匹配': 0,
            '扣分项': 0,
        }

        requirements_analysis = []

        for req in jd_requirements:
            req_text = req.get('requirement', '')
            req_type_str = req.get('type', 'nice_to_have')
            req_category = req.get('category', 'other')
            req_value = req.get('value')

            # 转换要求类型
            try:
                req_type = RequirementType(req_type_str)
            except ValueError:
                req_type = RequirementType.NICE_TO_HAVE

            # 判断匹配状态
            match_status, evidence, explanation = self._check_match(
                req_text, req_category, req_value, resume_data, ai_analysis
            )

            # 计算分数影响
            impact = self.SCORE_IMPACTS.get((req_type, match_status), 0)

            # 记录分析
            req_match = RequirementMatch(
                requirement=req_text,
                requirement_type=req_type,
                match_status=match_status,
                resume_evidence=evidence,
                score_impact=impact,
                explanation=explanation
            )
            requirements_analysis.append(req_match)

            # 更新分数
            score += impact

            # 更新明细
            if impact > 0:
                if req_type == RequirementType.MUST_HAVE:
                    breakdown['硬性要求匹配'] += impact
                elif req_type == RequirementType.NICE_TO_HAVE:
                    breakdown['加分项匹配'] += impact
                else:
                    breakdown['优先项匹配'] += impact
            elif impact < 0:
                breakdown['扣分项'] += impact

        # 限制分数范围
        score = max(self.MIN_SCORE, min(self.MAX_SCORE, score))

        # 确定等级
        level, summary = self._get_level_and_summary(score, requirements_analysis)

        result.score = score
        result.level = level
        result.breakdown = breakdown
        result.requirements_analysis = requirements_analysis
        result.summary = summary

        self.logger.info(f"匹配分数计算完成: score={score}, level={level}")
        return result

    def _check_match(
        self,
        requirement: str,
        category: str,
        req_value: Any,
        resume_data: Dict[str, Any],
        ai_analysis: Optional[Dict[str, Any]] = None
    ) -> tuple:
        """
        检查单个要求的匹配情况

        Returns:
            (MatchStatus, evidence, explanation)
        """
        evidence = ""
        explanation = ""

        # 优先使用 AI 分析结果
        if ai_analysis:
            # 检查 AI 识别的优势
            for strength in ai_analysis.get('strengths', []):
                strength_text = strength if isinstance(strength, str) else strength.get('item', '')
                if self._is_related_requirement(requirement, strength_text):
                    return MatchStatus.FULLY_MATCHED, strength_text, "AI识别为匹配优势"

            # 检查 AI 识别的差距
            for gap in ai_analysis.get('gaps', []):
                gap_text = gap if isinstance(gap, str) else gap.get('item', '')
                if self._is_related_requirement(requirement, gap_text):
                    return MatchStatus.NOT_MATCHED, "", f"AI识别为差距: {gap_text}"

        # 根据类别检查
        if category == 'education':
            return self._check_education(requirement, req_value, resume_data)
        elif category == 'experience':
            return self._check_experience(requirement, req_value, resume_data)
        elif category == 'skill':
            return self._check_skill(requirement, req_value, resume_data)
        elif category == 'age':
            return self._check_age(requirement, req_value, resume_data)
        elif category == 'salary':
            return self._check_salary(requirement, req_value, resume_data)

        # 默认：无法判断
        return MatchStatus.UNKNOWN, "", "需要人工确认"

    def _check_education(self, requirement: str, req_value: Any, resume_data: Dict) -> tuple:
        """检查学历匹配"""
        education = resume_data.get('education', [])
        if not education:
            return MatchStatus.UNKNOWN, "", "简历未提供学历信息"

        # 获取简历中的最高学历
        highest_edu_level = 0
        highest_edu_text = ""
        for edu in education:
            degree = edu.get('degree', edu.get('学历', ''))
            level = self.EDUCATION_LEVELS.get(degree, 0)
            if level > highest_edu_level:
                highest_edu_level = level
                highest_edu_text = f"{edu.get('school', edu.get('学校', ''))} {degree}"

        # 检查要求
        for edu_name, level in self.EDUCATION_LEVELS.items():
            if edu_name in requirement:
                if highest_edu_level >= level:
                    if highest_edu_level > level:
                        return MatchStatus.EXCEEDS, highest_edu_text, f"学历超出要求（{edu_name}）"
                    return MatchStatus.FULLY_MATCHED, highest_edu_text, f"学历符合要求（{edu_name}）"
                else:
                    return MatchStatus.NOT_MATCHED, highest_edu_text, f"学历不符合要求（需要{edu_name}，实际{list(self.EDUCATION_LEVELS.keys())[highest_edu_level-1] if highest_edu_level > 0 else '未知'}）"

        return MatchStatus.UNKNOWN, highest_edu_text, "无法判断学历要求"

    def _check_experience(self, requirement: str, req_value: Any, resume_data: Dict) -> tuple:
        """检查工作经验匹配"""
        import re

        work_exp = resume_data.get('work_experience', [])

        # 提取年限要求
        years_match = re.search(r'(\d+)[年+]?\s*(经验|工作|以上|及以上)', requirement)
        if years_match:
            required_years = int(years_match.group(1))

            # 计算简历中的工作年限
            total_years = 0
            evidence_parts = []
            for exp in work_exp:
                duration = exp.get('duration', exp.get('时长', ''))
                # 尝试提取年数
                year_match = re.search(r'(\d+)\s*年', duration)
                if year_match:
                    total_years += int(year_match.group(1))
                evidence_parts.append(exp.get('company', exp.get('公司', '')))

            evidence = f"共约{total_years}年经验: " + ", ".join(evidence_parts[:3])

            if total_years >= required_years:
                if total_years > required_years + 2:
                    return MatchStatus.EXCEEDS, evidence, f"经验超出要求（需要{required_years}年，实际约{total_years}年）"
                return MatchStatus.FULLY_MATCHED, evidence, f"经验符合要求（需要{required_years}年，实际约{total_years}年）"
            else:
                return MatchStatus.PARTIALLY_MATCHED, evidence, f"经验略不足（需要{required_years}年，实际约{total_years}年）"

        return MatchStatus.UNKNOWN, "", "无法判断经验要求"

    def _check_skill(self, requirement: str, req_value: Any, resume_data: Dict) -> tuple:
        """检查技能匹配"""
        skills = resume_data.get('skills', [])
        work_exp = resume_data.get('work_experience', [])
        projects = resume_data.get('projects', [])

        # 合并所有可能的技能来源
        all_text = ""
        for skill in skills:
            all_text += f" {skill if isinstance(skill, str) else skill.get('name', skill.get('技能', ''))}"
        for exp in work_exp:
            all_text += f" {exp.get('description', exp.get('描述', ''))}"
        for proj in projects:
            all_text += f" {proj.get('description', proj.get('描述', ''))} {proj.get('tech_stack', proj.get('技术栈', ''))}"

        all_text = all_text.lower()

        # 提取技能关键词
        skill_keywords = requirement.lower().replace('熟悉', '').replace('精通', '').replace('掌握', '').replace('了解', '')
        skill_keywords = skill_keywords.replace('，', ' ').replace(',', ' ').replace('/', ' ').split()

        matched_skills = []
        for keyword in skill_keywords:
            if len(keyword) >= 2 and keyword in all_text:
                matched_skills.append(keyword)

        if len(skill_keywords) > 0:
            match_ratio = len(matched_skills) / len(skill_keywords)
            if match_ratio >= 0.8:
                return MatchStatus.FULLY_MATCHED, f"匹配技能: {', '.join(matched_skills)}", "技能匹配"
            elif match_ratio >= 0.4:
                return MatchStatus.PARTIALLY_MATCHED, f"部分匹配: {', '.join(matched_skills)}", f"技能部分匹配（{int(match_ratio*100)}%）"
            else:
                return MatchStatus.NOT_MATCHED, "", f"技能不匹配（需要: {requirement}）"

        return MatchStatus.UNKNOWN, "", "无法判断技能要求"

    def _check_age(self, requirement: str, req_value: Any, resume_data: Dict) -> tuple:
        """检查年龄匹配"""
        import re

        # 简历通常不直接包含年龄，这里返回未知
        # 但如果 JD 明确写了年龄要求，标记为需要关注

        age_match = re.search(r'(\d+)\s*岁', requirement)
        if age_match:
            return MatchStatus.UNKNOWN, "", f"JD要求年龄{age_match.group(1)}岁以下，请确认"

        return MatchStatus.UNKNOWN, "", "无法判断年龄"

    def _check_salary(self, requirement: str, req_value: Any, resume_data: Dict) -> tuple:
        """检查薪资匹配"""
        import re

        # 薪资通常在面试阶段讨论，简历中可能没有
        salary_match = re.search(r'(\d+)[kK万]?\s*[-~至]\s*(\d+)[kK万]?', requirement)
        if salary_match:
            return MatchStatus.UNKNOWN, "", f"薪资范围: {salary_match.group(0)}"

        if '面议' in requirement:
            return MatchStatus.FULLY_MATCHED, "", "薪资面议"

        return MatchStatus.UNKNOWN, "", "无法判断薪资"

    def _is_related_requirement(self, requirement: str, text: str) -> bool:
        """判断两段文本是否相关"""
        # 简单的关键词匹配
        req_words = set(requirement.lower().replace('，', ' ').replace(',', ' ').split())
        text_words = set(text.lower().replace('，', ' ').replace(',', ' ').split())

        # 计算重叠
        overlap = req_words & text_words
        if len(overlap) >= 1:
            return True

        return False

    def _get_level_and_summary(self, score: int, requirements: List[RequirementMatch]) -> tuple:
        """根据分数确定等级和总结"""
        # 找到对应的等级
        for threshold, level, summary in self.SCORE_LEVELS:
            if score >= threshold:
                break

        # 统计匹配情况
        matched = sum(1 for r in requirements if r.match_status in [MatchStatus.FULLY_MATCHED, MatchStatus.EXCEEDS])
        not_matched = sum(1 for r in requirements if r.match_status == MatchStatus.NOT_MATCHED)
        total = len(requirements) if requirements else 1

        # 生成总结
        if score >= 80:
            summary = f"匹配度优秀！{matched}/{total}项要求匹配"
        elif score >= 60:
            summary = f"匹配度良好，{matched}/{total}项匹配，{not_matched}项待提升"
        elif score >= 40:
            summary = f"匹配度一般，{matched}/{total}项匹配，{not_matched}项需要重点提升"
        else:
            summary = f"匹配度较低，仅{matched}/{total}项匹配，建议重新评估"

        return level, summary


# 便捷函数
def calculate_match_score(
    jd_requirements: List[Dict[str, Any]],
    resume_data: Dict[str, Any],
    ai_analysis: Optional[Dict[str, Any]] = None
) -> MatchScoreResult:
    """
    计算匹配分数的便捷函数

    Args:
        jd_requirements: JD 要求列表
        resume_data: 简历数据
        ai_analysis: AI 分析结果（可选）

    Returns:
        MatchScoreResult: 计算结果
    """
    scorer = MatchScorer()
    return scorer.calculate_score(jd_requirements, resume_data, ai_analysis)
