"""
匹配评分器单元测试

测试 core/match_scorer.py — 简历-JD 匹配评分的纯规则计算逻辑。
无外部依赖，不需要 mock。
"""

import pytest
from core.match_scorer import (
    MatchScorer, MatchStatus, RequirementType,
    MatchScoreResult, calculate_match_score
)


@pytest.fixture
def scorer():
    return MatchScorer()


@pytest.fixture
def good_resume():
    """一份不错的简历数据"""
    return {
        'education': [
            {'school': '清华大学', 'degree': '硕士', 'major': '计算机'},
        ],
        'work_experience': [
            {'company': '字节跳动', 'duration': '3年', 'description': 'Python后端开发'},
            {'company': '腾讯', 'duration': '2年', 'description': 'Java微服务'},
        ],
        'skills': ['Python', 'Java', 'Go', 'Kubernetes', 'Docker'],
        'projects': [
            {'description': '使用 Go 和 Kubernetes 构建云原生平台', 'tech_stack': 'Go, K8s'},
        ],
    }


@pytest.fixture
def weak_resume():
    """一份较弱的简历数据"""
    return {
        'education': [
            {'school': '某学院', 'degree': '大专', 'major': '市场营销'},
        ],
        'work_experience': [
            {'company': '某公司', 'duration': '1年', 'description': '文员'},
        ],
        'skills': ['Word', 'Excel'],
    }


class TestCalculateScore:
    """calculate_score 主方法"""

    def test_perfect_match(self, scorer, good_resume):
        """完全匹配场景"""
        requirements = [
            {'requirement': '3年以上工作经验', 'type': 'must_have', 'category': 'experience'},
            {'requirement': '本科及以上学历', 'type': 'must_have', 'category': 'education'},
            {'requirement': '熟悉 Python', 'type': 'nice_to_have', 'category': 'skill'},
        ]
        result = scorer.calculate_score(requirements, good_resume)
        assert isinstance(result, MatchScoreResult)
        assert result.score > 60  # 基础分 + 匹配加分
        assert len(result.requirements_analysis) == 3

    def test_no_match(self, scorer, weak_resume):
        """简历与 JD 完全不匹配"""
        requirements = [
            {'requirement': '硕士及以上学历', 'type': 'must_have', 'category': 'education'},
            {'requirement': '5年以上Python开发经验', 'type': 'must_have', 'category': 'experience'},
            {'requirement': '熟悉 Kubernetes', 'type': 'must_have', 'category': 'skill'},
        ]
        result = scorer.calculate_score(requirements, weak_resume)
        assert result.score < 60  # 基础分 - 扣分

    def test_partial_match(self, scorer, good_resume):
        """部分匹配"""
        requirements = [
            {'requirement': '本科及以上学历', 'type': 'must_have', 'category': 'education'},
            {'requirement': '熟悉 Rust', 'type': 'must_have', 'category': 'skill'},
        ]
        result = scorer.calculate_score(requirements, good_resume)
        # 学历匹配加分，Rust 不匹配扣分
        assert 40 <= result.score <= 100

    def test_empty_requirements(self, scorer, good_resume):
        """空 JD 要求"""
        result = scorer.calculate_score([], good_resume)
        assert result.score == 60  # 只有基础分
        assert result.requirements_analysis == []

    def test_empty_resume(self, scorer):
        """空简历"""
        requirements = [
            {'requirement': '本科及以上学历', 'type': 'must_have', 'category': 'education'},
        ]
        result = scorer.calculate_score(requirements, {})
        # 空简历应该不崩溃，学历未知扣分
        assert isinstance(result, MatchScoreResult)
        assert result.score >= 0


class TestEducationCheck:
    """学历匹配检查"""

    def test_meet_requirement(self, scorer):
        """学历满足要求"""
        resume = {'education': [{'school': '某大学', 'degree': '硕士'}]}
        req = {'requirement': '本科及以上学历', 'type': 'must_have', 'category': 'education'}
        result = scorer.calculate_score([req], resume)
        # 硕士 >= 本科 → EXCEEDS 或 FULLY_MATCHED
        statuses = [r.match_status for r in result.requirements_analysis]
        assert statuses[0] in (MatchStatus.FULLY_MATCHED, MatchStatus.EXCEEDS)

    def test_below_requirement(self, scorer):
        """学历不满足"""
        resume = {'education': [{'school': '某学院', 'degree': '大专'}]}
        req = {'requirement': '本科及以上学历', 'type': 'must_have', 'category': 'education'}
        result = scorer.calculate_score([req], resume)
        assert result.requirements_analysis[0].match_status == MatchStatus.NOT_MATCHED

    def test_exceed_requirement(self, scorer):
        """学历超出要求"""
        resume = {'education': [{'school': '清华', 'degree': '博士'}]}
        req = {'requirement': '本科及以上学历', 'type': 'must_have', 'category': 'education'}
        result = scorer.calculate_score([req], resume)
        assert result.requirements_analysis[0].match_status == MatchStatus.EXCEEDS

    def test_no_education_in_resume(self, scorer):
        """简历没有学历信息"""
        resume = {'skills': ['Python']}
        req = {'requirement': '本科及以上学历', 'type': 'must_have', 'category': 'education'}
        result = scorer.calculate_score([req], resume)
        assert result.requirements_analysis[0].match_status == MatchStatus.UNKNOWN


class TestExperienceCheck:
    """工作经验匹配检查"""

    def test_meet_experience(self, scorer):
        """经验满足"""
        resume = {'work_experience': [{'company': 'A', 'duration': '5年'}]}
        req = {'requirement': '3年以上工作经验', 'type': 'must_have', 'category': 'experience'}
        result = scorer.calculate_score([req], resume)
        assert result.requirements_analysis[0].match_status in (
            MatchStatus.FULLY_MATCHED, MatchStatus.EXCEEDS
        )

    def test_below_experience(self, scorer):
        """经验不足"""
        resume = {'work_experience': [{'company': 'A', 'duration': '1年'}]}
        req = {'requirement': '5年以上工作经验', 'type': 'must_have', 'category': 'experience'}
        result = scorer.calculate_score([req], resume)
        assert result.requirements_analysis[0].match_status == MatchStatus.PARTIALLY_MATCHED


class TestSkillCheck:
    """技能匹配检查"""

    def test_skill_match(self, scorer, good_resume):
        """技能匹配"""
        req = {'requirement': '熟悉 Python', 'type': 'must_have', 'category': 'skill'}
        result = scorer.calculate_score([req], good_resume)
        assert result.requirements_analysis[0].match_status == MatchStatus.FULLY_MATCHED

    def test_skill_no_match(self, scorer, weak_resume):
        """技能不匹配"""
        req = {'requirement': '熟悉 Kubernetes', 'type': 'must_have', 'category': 'skill'}
        result = scorer.calculate_score([req], weak_resume)
        assert result.requirements_analysis[0].match_status == MatchStatus.NOT_MATCHED

    def test_nice_to_have_no_penalty(self, scorer, weak_resume):
        """加分项不匹配不扣分"""
        req = {'requirement': '熟悉 Kubernetes', 'type': 'nice_to_have', 'category': 'skill'}
        result = scorer.calculate_score([req], weak_resume)
        # NICE_TO_HAVE + NOT_MATCHED → impact = 0
        assert result.requirements_analysis[0].score_impact == 0


class TestScoreLevels:
    """分数等级判定"""

    def test_high_score_level(self, scorer, good_resume):
        """高分 → 优秀匹配"""
        requirements = [
            {'requirement': '3年经验', 'type': 'must_have', 'category': 'experience'},
            {'requirement': '熟悉 Python', 'type': 'must_have', 'category': 'skill'},
            {'requirement': '熟悉 Java', 'type': 'nice_to_have', 'category': 'skill'},
            {'requirement': '熟悉 Go', 'type': 'nice_to_have', 'category': 'skill'},
            {'requirement': '熟悉 Docker', 'type': 'nice_to_have', 'category': 'skill'},
        ]
        result = scorer.calculate_score(requirements, good_resume)
        if result.score >= 80:
            assert '优秀' in result.level

    def test_score_clamped_to_range(self, scorer):
        """分数不超过 0-100"""
        resume = {}
        # 大量不满足的硬性要求
        requirements = [
            {'requirement': f'技能{i}', 'type': 'must_have', 'category': 'skill'}
            for i in range(20)
        ]
        result = scorer.calculate_score(requirements, resume)
        assert 0 <= result.score <= 100


class TestConvenienceFunction:
    """便捷函数 calculate_match_score"""

    def test_convenience_returns_result(self, scorer, good_resume):
        result = calculate_match_score(
            [{'requirement': '熟悉 Python', 'type': 'must_have', 'category': 'skill'}],
            good_resume
        )
        assert isinstance(result, MatchScoreResult)

    def test_to_dict(self, scorer, good_resume):
        result = scorer.calculate_score(
            [{'requirement': '熟悉 Python', 'type': 'must_have', 'category': 'skill'}],
            good_resume
        )
        d = result.to_dict()
        assert 'score' in d
        assert 'level' in d
        assert 'breakdown' in d
        assert 'requirements' in d
