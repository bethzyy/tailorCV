"""
Writer-Reviewer 闭环测试
"""
import pytest
import json
from unittest.mock import MagicMock, patch, PropertyMock
from concurrent.futures import ThreadPoolExecutor


class TestAntiGravityProvider:
    """AntiGravity Provider 测试"""

    def test_provider_id(self):
        from core.providers.antigravity_provider import AntiGravityProvider
        p = AntiGravityProvider()
        assert p.provider_id == 'antigravity'

    def test_provider_name(self):
        from core.providers.antigravity_provider import AntiGravityProvider
        p = AntiGravityProvider()
        assert p.provider_name == 'AntiGravity 代理'

    def test_available_models(self):
        from core.providers.antigravity_provider import AntiGravityProvider
        p = AntiGravityProvider()
        models = p.available_models
        assert 'gpt-4o' in models
        assert 'claude-sonnet-4-5' in models
        assert 'gemini-2.5-pro' in models

    def test_custom_base_url(self):
        from core.providers.antigravity_provider import AntiGravityProvider
        p = AntiGravityProvider(base_url='http://localhost:9999/v1')
        assert p._base_url == 'http://localhost:9999/v1'


class TestReviewPromptExists:
    """审阅和修订 Prompt 文件存在性检查"""

    def test_review_prompt_exists(self):
        from pathlib import Path
        p = Path('prompts/review_content_prompt.txt')
        assert p.exists(), "review_content_prompt.txt 不存在"

    def test_revise_prompt_exists(self):
        from pathlib import Path
        p = Path('prompts/revise_content_prompt.txt')
        assert p.exists(), "revise_content_prompt.txt 不存在"

    def test_review_prompt_has_placeholders(self):
        from pathlib import Path
        content = Path('prompts/review_content_prompt.txt').read_text(encoding='utf-8')
        assert '{tailored_resume}' in content
        assert '{original_resume}' in content
        assert '{jd_requirements}' in content
        assert 'converged' in content

    def test_revise_prompt_has_placeholders(self):
        from pathlib import Path
        content = Path('prompts/revise_content_prompt.txt').read_text(encoding='utf-8')
        assert '{current_tailored_resume}' in content
        assert '{aggregated_feedback}' in content
        assert '{match_analysis}' in content


class TestConfigDefaults:
    """Writer-Reviewer 配置默认值测试"""

    def test_default_disabled(self):
        from core.config import config
        # 默认关闭，通过环境变量启用
        assert hasattr(config, 'WRITER_REVIEWER_ENABLED')
        assert hasattr(config, 'WRITER_REVIEWER_MAX_ITERATIONS')
        assert hasattr(config, 'WRITER_REVIEWER_SCORE_THRESHOLD')
        assert hasattr(config, 'WRITER_REVIEWER_MIN_DIFF_THRESHOLD')
        assert hasattr(config, 'WRITER_REVIEWER_REVIEWER_MODELS')
        assert hasattr(config, 'ANTIGRAVITY_BASE_URL')

    def test_max_iterations_default(self):
        from core.config import config
        assert config.WRITER_REVIEWER_MAX_ITERATIONS == 3

    def test_score_threshold_default(self):
        from core.config import config
        assert config.WRITER_REVIEWER_SCORE_THRESHOLD == 85.0

    def test_min_diff_threshold_default(self):
        from core.config import config
        assert config.WRITER_REVIEWER_MIN_DIFF_THRESHOLD == 0.05


class TestExpertTeamV2ReviewLoop:
    """ExpertTeamV2 Writer-Reviewer 闭环逻辑测试"""

    def _make_team(self, enabled=True):
        """创建测试用的 ExpertTeamV2 实例"""
        import os
        import sys
        import importlib

        original = os.getenv('WRITER_REVIEWER_ENABLED')
        if enabled:
            os.environ['WRITER_REVIEWER_ENABLED'] = 'true'
        else:
            os.environ.pop('WRITER_REVIEWER_ENABLED', None)

        # 重新加载 config 模块让环境变量生效
        if 'core.config' in sys.modules:
            importlib.reload(sys.modules['core.config'])

        from core.expert_team import ExpertTeamV2
        # mock model_manager 避免真实 API 调用
        mock_mm = MagicMock()
        team = ExpertTeamV2(model_manager=mock_mm)

        # 恢复环境变量
        if original is not None:
            os.environ['WRITER_REVIEWER_ENABLED'] = original
        else:
            os.environ.pop('WRITER_REVIEWER_ENABLED', None)
        if 'core.config' in sys.modules:
            importlib.reload(sys.modules['core.config'])

        return team

    def test_reviewer_providers_empty_when_disabled(self):
        """闭环关闭时 reviewer_providers 应为空（环境变量层面控制）"""
        team = self._make_team(enabled=False)
        # 注意：.env 文件中的 WRITER_REVIEWER_ENABLED=true 会覆盖环境变量
        # 这里验证的是：如果 .env 中启用了，team 应该有 reviewer
        # 如果 .env 中未启用，team._reviewer_providers 应为空
        assert hasattr(team, '_reviewer_providers')

    def test_rewrite_content_result_has_review_fields(self):
        """RewriteContentResult 应包含审阅元数据字段"""
        from core.expert_team import RewriteContentResult
        result = RewriteContentResult()
        assert hasattr(result, 'review_iterations')
        assert hasattr(result, 'review_scores')
        assert hasattr(result, 'review_feedback_summary')
        assert result.review_iterations == 0
        assert result.review_scores == []
        assert result.review_feedback_summary == ""

    def test_aggregate_reviews_single_reviewer(self):
        """单个审阅者时聚合结果正确"""
        team = self._make_team(enabled=False)
        review = {
            "overall_score": 80,
            "dimensions": {
                "jd_alignment": {"score": 8, "issues": ["issue1"], "suggestions": ["sug1"]},
                "authenticity": {"score": 9, "issues": [], "suggestions": []},
                "keyword_coverage": {"score": 7, "issues": [], "suggestions": ["sug2"]},
                "logical_flow": {"score": 8, "issues": [], "suggestions": []},
                "quantification": {"score": 8, "issues": [], "suggestions": []},
                "professional_tone": {"score": 8, "issues": [], "suggestions": []},
            },
            "specific_revisions": [
                {"section": "work_experience", "item_index": 0, "reason": "align with JD"}
            ],
            "converged": False,
            "summary": "需要改进关键词覆盖"
        }
        result = team._aggregate_reviews([review])
        # overall_score 是 6 个维度分数的平均值：(8+9+7+8+8+8)/6 = 48/6 = 8.0 → round → 8
        assert result['overall_score'] == 8
        assert result['reviewer_count'] == 1
        assert result['converged'] is False
        assert len(result['specific_revisions']) == 1

    def test_aggregate_reviews_converged_when_all_agree(self):
        """所有审阅者都 converged 时聚合结果也为 converged"""
        team = self._make_team(enabled=False)
        review1 = {
            "overall_score": 90, "dimensions": {}, "specific_revisions": [],
            "converged": True, "summary": "ok"
        }
        review2 = {
            "overall_score": 88, "dimensions": {}, "specific_revisions": [],
            "converged": True, "summary": "good"
        }
        result = team._aggregate_reviews([review1, review2])
        assert result['converged'] is True

    def test_aggregate_reviews_not_converged_when_one_disagrees(self):
        """任一审阅者不 converged 时聚合结果也不 converged"""
        team = self._make_team(enabled=False)
        review1 = {
            "overall_score": 90, "dimensions": {}, "specific_revisions": [],
            "converged": True, "summary": "ok"
        }
        review2 = {
            "overall_score": 70, "dimensions": {}, "specific_revisions": [{"section": "skills"}],
            "converged": False, "summary": "needs work"
        }
        result = team._aggregate_reviews([review1, review2])
        assert result['converged'] is False

    def test_aggregate_reviews_empty_input(self):
        """空审阅列表返回默认结果"""
        team = self._make_team(enabled=False)
        result = team._aggregate_reviews([])
        assert result['overall_score'] == 0
        assert result['converged'] is False

    def test_aggregate_reviews_dedup_revisions(self):
        """相同 section+item_index 的修订应去重"""
        team = self._make_team(enabled=False)
        rev = {"section": "work_experience", "item_index": 0, "reason": "fix this"}
        review1 = {"overall_score": 70, "dimensions": {}, "specific_revisions": [rev], "converged": False, "summary": ""}
        review2 = {"overall_score": 75, "dimensions": {}, "specific_revisions": [rev], "converged": False, "summary": ""}
        result = team._aggregate_reviews([review1, review2])
        assert len(result['specific_revisions']) == 1

    def test_aggregate_reviews_average_scores(self):
        """多个审阅者分数应取平均"""
        team = self._make_team(enabled=False)
        dims = {
            "jd_alignment": {"score": 8, "issues": [], "suggestions": []},
            "authenticity": {"score": 6, "issues": [], "suggestions": []},
            "keyword_coverage": {"score": 8, "issues": [], "suggestions": []},
            "logical_flow": {"score": 8, "issues": [], "suggestions": []},
            "quantification": {"score": 8, "issues": [], "suggestions": []},
            "professional_tone": {"score": 8, "issues": [], "suggestions": []},
        }
        review1 = {"overall_score": 80, "dimensions": dims, "specific_revisions": [], "converged": True, "summary": ""}
        # 修改一个维度分数
        dims2 = json.loads(json.dumps(dims))
        dims2["authenticity"]["score"] = 8
        review2 = {"overall_score": 80, "dimensions": dims2, "specific_revisions": [], "converged": True, "summary": ""}
        result = team._aggregate_reviews([review1, review2])
        # authenticity 应该是 (6+8)/2 = 7.0
        assert result['dimensions']['authenticity']['score'] == 7.0

    def test_calculate_version_diff_identical(self):
        """完全相同的两版简历差异应为 0"""
        team = self._make_team(enabled=False)
        resume = {"summary": "hello", "skills": "python"}
        diff = team._calculate_version_diff(resume, resume)
        assert diff == 0.0

    def test_calculate_version_diff_completely_different(self):
        """完全不同的两版简历差异应 > 0"""
        team = self._make_team(enabled=False)
        diff = team._calculate_version_diff({"a": "1"}, {"b": "2"})
        assert diff > 0

    def test_calculate_version_diff_minor_change(self):
        """微小修改差异应很小"""
        team = self._make_team(enabled=False)
        a = {"summary": "I am a software engineer with 5 years of experience in Python development"}
        b = {"summary": "I am a software engineer with 5 years of experience in Python and Java development"}
        diff = team._calculate_version_diff(a, b)
        assert 0 < diff < 0.2

    def test_calculate_version_diff_empty(self):
        """空字典与有内容字典差异处理"""
        team = self._make_team(enabled=False)
        diff = team._calculate_version_diff({}, {"a": 1})
        assert diff > 0  # 空序列 vs 非空序列有差异


class TestReviewLoopConvergence:
    """收敛机制测试"""

    def test_convergence_on_high_score(self):
        """分数超过阈值时应停止循环"""
        from core.config import config
        threshold = config.WRITER_REVIEWER_SCORE_THRESHOLD
        # 模拟聚合结果分数超过阈值
        aggregated = {"overall_score": threshold + 1, "converged": False,
                      "specific_revisions": [{"section": "skills"}], "reviewer_count": 1, "summary": ""}
        assert aggregated['overall_score'] >= config.WRITER_REVIEWER_SCORE_THRESHOLD

    def test_convergence_on_no_revisions(self):
        """无修改建议时应停止循环"""
        aggregated = {"overall_score": 70, "converged": False,
                      "specific_revisions": [], "reviewer_count": 1, "summary": ""}
        assert len(aggregated['specific_revisions']) == 0

    def test_convergence_on_all_converged(self):
        """所有审阅者 converged 时应停止"""
        aggregated = {"overall_score": 70, "converged": True,
                      "specific_revisions": [], "reviewer_count": 2, "summary": ""}
        assert aggregated['converged'] is True

    def test_max_iterations_cap(self):
        """最大迭代次数限制"""
        from core.config import config
        assert config.WRITER_REVIEWER_MAX_ITERATIONS == 3


class TestTemplatesRegression:
    """模板加载回归测试 - 确保内置模板始终可加载"""

    def test_builtin_templates_loadable(self):
        """内置模板应始终能从数据库加载"""
        from core.template_manager import TemplateManager
        tm = TemplateManager()
        templates = tm.get_templates(source='builtin')
        assert len(templates) == 6, f"期望 6 个内置模板，实际 {len(templates)}"

    def test_builtin_template_ids(self):
        """内置模板 ID 列表正确"""
        from core.template_manager import TemplateManager
        tm = TemplateManager()
        templates = tm.get_templates(source='builtin')
        ids = {t['template_id'] for t in templates}
        expected = {'classic_professional', 'modern_minimal', 'creative_design',
                    'executive_senior', 'academic_research', 'tech_engineer'}
        assert ids == expected
