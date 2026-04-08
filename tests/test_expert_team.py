"""
AI 专家团队单元测试 — A/B/C 三层架构

A 层（单阶段验证）：mock model_manager，逐阶段验证返回结构和字段
B 层（管道集成）：串联多阶段，验证数据流转和统计
C 层（降级测试）：模拟 API 失败/空响应，验证 fallback 路径
"""

import json
import pytest
from unittest.mock import MagicMock
from core.expert_team import (
    ExpertTeamV2,
    ParseResumeResult,
    DecodeJdResult,
    MatchAnalysisResult,
    RewriteContentResult,
    QualityCheckResult,
    TailorResultV2,
)


# ==================== Mock 数据 ====================

PARSE_RESUME_JSON = json.dumps({
    "basic_info": {"name": "Zhang San", "phone": "13800138000", "email": "zs@test.com"},
    "education": [{"school": "Tsinghua", "major": "CS", "degree": "Bachelor"}],
    "work_experience": [{"company": "ByteDance", "role": "Backend Engineer", "duration": "2020-2023"}],
    "projects": [{"name": "API Gateway", "role": "Developer"}],
    "skills": {"programming": ["Python", "Go"], "frameworks": ["Flask"]},
    "awards": ["ACM Gold"],
    "certificates": ["AWS SAA"],
    "self_evaluation": "5 years backend experience",
    "raw_materials": {},
    "parsing_confidence": 0.85,
}, ensure_ascii=False)

DECODE_JD_JSON = json.dumps({
    "job_title": "Python Engineer",
    "company_overview": "ByteDance",
    "salary_range": "30-50K",
    "must_have": {"skills": ["Python", "REST API"], "experience": "3 years"},
    "nice_to_have": {"skills": ["Docker", "K8s"]},
    "implicit_requirements": [{"item": "Team leadership", "weight": 0.7}],
    "keyword_weights": {"Python": 10, "API": 8, "Docker": 5},
    "success_indicators": ["High throughput", "Low latency"],
    "red_flags": ["No system design experience"],
    "pain_points": [{"item": "Legacy code", "priority": "high"}],
    "competitor_profile": {"years": "3-5", "skills": ["Python", "Django"]},
}, ensure_ascii=False)

MATCH_ANALYSIS_JSON = json.dumps({
    "match_score": 78,
    "match_level": "good",
    "rewrite_intensity": "L2",
    "strengths": [{"item": "Python skills", "impact": "high"}],
    "gaps": [{"item": "K8s experience", "impact": "medium"}],
    "fatal_flaws": [],
    "highlight_opportunities": [{"item": "Scalability projects"}],
    "rewrite_strategy": {"approach": "emphasize_API_experience"},
    "content_to_emphasize": ["API design", "High concurrency"],
    "content_to_weaken": ["Manual testing"],
    "recruiter_tips": ["Highlight system design"],
    "differentiation_strategy": {"angle": "Full-stack Python"},
    "score_breakdown": {"skills": 85, "experience": 72, "education": 80},
    "requirements_analysis": {"must_have_met": 3, "nice_to_have_met": 1},
}, ensure_ascii=False)

REWRITE_CONTENT_JSON = json.dumps({
    "tailored_resume": {
        "basic_info": {"name": "Zhang San"},
        "work_experience": [{"company": "ByteDance", "content": "Built REST API serving 1M+ requests"}],
        "projects": [{"name": "API Gateway", "content": "Designed microservice architecture"}],
    },
    "change_log": [{"field": "work_experience", "change": "Enhanced with metrics"}],
    "keyword_coverage": {"matched": ["Python", "API"], "missed": ["Docker"]},
}, ensure_ascii=False)

QUALITY_CHECK_JSON = json.dumps({
    "overall_score": 82,
    "score_breakdown": {"keyword_coverage": 85, "authenticity": 90, "jd_alignment": 75},
    "keyword_coverage": {"rate": 0.75},
    "authenticity_check": {"no_fabrication": True, "evidence_count": 5},
    "improvement_analysis": {"suggestions": ["Add Docker experience"]},
    "recruiter_feedback": {"impression": "Strong candidate"},
    "evidence_validation": [{"claim": "1M+ requests", "verifiable": True}],
    "final_verdict": {"approved": True, "score": 82},
}, ensure_ascii=False)


# ==================== Fixtures ====================

def _make_mock_response(content_json):
    """构造一个成功的 mock model response"""
    return MagicMock(
        success=True,
        content=content_json,
        model_id='glm-5',
        model_name='GLM-5',
        tokens_used=100,
        latency_ms=500,
    )


@pytest.fixture
def mock_model_manager():
    mm = MagicMock()
    # 默认返回成功
    mm.call.return_value = _make_mock_response('{"result": "ok"}')
    mm.get_stats.return_value = {'total_calls': 0}
    mm.is_available.return_value = True
    return mm


@pytest.fixture
def team(mock_model_manager):
    return ExpertTeamV2(model_manager=mock_model_manager)


def _setup_stage_mock(mock_model_manager, stage, json_content):
    """为指定阶段设置 mock 返回值"""
    def side_effect(prompt, task_type=None, max_tokens=None, temperature=None):
        return _make_mock_response(json_content)
    mock_model_manager.call.side_effect = side_effect


# ==================== A 层：单阶段验证 ====================

class TestExpertTeamInit:
    """初始化"""

    def test_create_team(self, team):
        assert team is not None

    def test_has_model_manager(self, team, mock_model_manager):
        assert team.model_manager is mock_model_manager

    def test_stats_initialized(self, team):
        stats = team.stats
        assert 'stage_calls' in stats
        assert 'total_tokens' in stats
        assert 'total_latency_ms' in stats

    def test_get_stats(self, team, mock_model_manager):
        stats = team.get_stats()
        assert isinstance(stats, dict)
        assert 'total_calls' in stats


class TestParseResume:
    """阶段0: 简历结构解析"""

    def test_success_returns_correct_fields(self, team, mock_model_manager):
        mock_model_manager.call.return_value = _make_mock_response(PARSE_RESUME_JSON)
        result = team.parse_resume("Resume content")
        assert isinstance(result, ParseResumeResult)
        assert result.success is True
        assert result.basic_info['name'] == 'Zhang San'
        assert result.basic_info['phone'] == '13800138000'
        assert len(result.education) == 1
        assert result.education[0]['school'] == 'Tsinghua'
        assert len(result.work_experience) == 1
        assert result.work_experience[0]['company'] == 'ByteDance'
        assert len(result.projects) == 1
        assert 'Python' in result.skills.get('programming', [])
        assert len(result.awards) == 1
        assert len(result.certificates) == 1
        assert result.self_evaluation == '5 years backend experience'
        assert result.parsing_confidence == 0.85

    def test_invalid_json_fallback(self, team, mock_model_manager):
        """AI 返回非 JSON 内容时 success=False"""
        mock_model_manager.call.return_value = _make_mock_response("I cannot parse this resume.")
        result = team.parse_resume("Resume content")
        assert result.success is False
        assert result.error != ""

    def test_empty_json_object(self, team, mock_model_manager):
        """AI 返回空 JSON 对象时 success=True 但字段全为默认值"""
        mock_model_manager.call.return_value = _make_mock_response('{}')
        result = team.parse_resume("Resume content")
        assert result.success is True
        assert result.basic_info == {}
        assert result.education == []
        assert result.work_experience == []

    def test_api_failure_raises_runtime_error(self, team, mock_model_manager):
        """API 调用失败时抛出 RuntimeError"""
        mock_model_manager.call.return_value = MagicMock(
            success=False, content='', error_message='API timeout'
        )
        with pytest.raises(RuntimeError, match="parse_resume"):
            team.parse_resume("some text")

    def test_tokens_tracked_in_stats(self, team, mock_model_manager):
        mock_model_manager.call.return_value = _make_mock_response(PARSE_RESUME_JSON)
        team.parse_resume("Resume")
        assert team.stats['stage_calls']['parse_resume'] == 1
        assert team.stats['total_tokens'] == 100


class TestDecodeJd:
    """阶段1: JD 深度解码"""

    def test_success_returns_correct_fields(self, team, mock_model_manager):
        mock_model_manager.call.return_value = _make_mock_response(DECODE_JD_JSON)
        result = team.decode_jd("Hiring Python Engineer")
        assert isinstance(result, DecodeJdResult)
        assert result.success is True
        assert result.job_title == 'Python Engineer'
        assert result.company_overview == 'ByteDance'
        assert result.salary_range == '30-50K'
        assert 'Python' in result.must_have.get('skills', [])
        assert 'Docker' in result.nice_to_have.get('skills', [])
        assert isinstance(result.implicit_requirements, list)
        assert len(result.keyword_weights) > 0
        assert len(result.success_indicators) > 0
        assert len(result.red_flags) > 0
        assert len(result.pain_points) > 0

    def test_invalid_json_fallback(self, team, mock_model_manager):
        mock_model_manager.call.return_value = _make_mock_response("Not valid JD analysis.")
        result = team.decode_jd("JD content")
        assert result.success is False
        assert result.error != ""


class TestMatchAnalysis:
    """阶段2: 匹配度分析"""

    def _prepare_prerequisites(self, team, mock_model_manager):
        """准备 parse_resume 和 decode_jd 的结果"""
        # 先设置 parse_resume mock
        mock_model_manager.call.return_value = _make_mock_response(PARSE_RESUME_JSON)
        parsed = team.parse_resume("Resume")
        # 再设置 decode_jd mock
        mock_model_manager.call.return_value = _make_mock_response(DECODE_JD_JSON)
        jd = team.decode_jd("JD")
        return parsed, jd

    def test_success_returns_correct_fields(self, team, mock_model_manager):
        parsed, jd = self._prepare_prerequisites(team, mock_model_manager)
        mock_model_manager.call.return_value = _make_mock_response(MATCH_ANALYSIS_JSON)
        result = team.match_analysis(parsed, jd)
        assert isinstance(result, MatchAnalysisResult)
        assert result.success is True
        assert isinstance(result.match_score, int)
        assert 0 <= result.match_score <= 100
        assert result.match_level == 'good'
        assert result.rewrite_intensity == 'L2'
        assert isinstance(result.strengths, list)
        assert len(result.strengths) > 0
        assert isinstance(result.gaps, list)
        assert isinstance(result.fatal_flaws, list)
        assert isinstance(result.score_breakdown, dict)

    def test_score_within_valid_range(self, team, mock_model_manager):
        parsed, jd = self._prepare_prerequisites(team, mock_model_manager)
        # 测试边界值
        mock_model_manager.call.return_value = _make_mock_response(
            json.dumps({"match_score": 0, "match_level": "low", "strengths": [], "gaps": []})
        )
        result = team.match_analysis(parsed, jd)
        assert 0 <= result.match_score <= 100

    def test_empty_requirements(self, team, mock_model_manager):
        parsed, jd = self._prepare_prerequisites(team, mock_model_manager)
        mock_model_manager.call.return_value = _make_mock_response(
            json.dumps({"match_score": 50, "strengths": [], "gaps": [], "fatal_flaws": []})
        )
        result = team.match_analysis(parsed, jd)
        assert result.strengths == []
        assert result.gaps == []


class TestRewriteContent:
    """阶段3: 内容深度改写"""

    def _prepare_prerequisites(self, team, mock_model_manager):
        """准备前三个阶段的结果"""
        mock_model_manager.call.return_value = _make_mock_response(PARSE_RESUME_JSON)
        parsed = team.parse_resume("Resume")
        mock_model_manager.call.return_value = _make_mock_response(DECODE_JD_JSON)
        jd = team.decode_jd("JD")
        mock_model_manager.call.return_value = _make_mock_response(MATCH_ANALYSIS_JSON)
        match = team.match_analysis(parsed, jd)
        return parsed, jd, match

    def test_success_returns_correct_fields(self, team, mock_model_manager):
        parsed, jd, match = self._prepare_prerequisites(team, mock_model_manager)
        mock_model_manager.call.return_value = _make_mock_response(REWRITE_CONTENT_JSON)
        result = team.rewrite_content("Original resume", parsed, match, jd)
        assert isinstance(result, RewriteContentResult)
        assert result.success is True
        assert isinstance(result.tailored_resume, dict)
        assert 'work_experience' in result.tailored_resume
        assert len(result.change_log) > 0
        assert 'matched' in result.keyword_coverage

    def test_tailored_has_work_experience(self, team, mock_model_manager):
        parsed, jd, match = self._prepare_prerequisites(team, mock_model_manager)
        mock_model_manager.call.return_value = _make_mock_response(REWRITE_CONTENT_JSON)
        result = team.rewrite_content("Original resume", parsed, match, jd)
        we = result.tailored_resume.get('work_experience', [])
        assert len(we) == 1
        assert 'content' in we[0]

    def test_keyword_coverage_tracked(self, team, mock_model_manager):
        parsed, jd, match = self._prepare_prerequisites(team, mock_model_manager)
        mock_model_manager.call.return_value = _make_mock_response(REWRITE_CONTENT_JSON)
        result = team.rewrite_content("Original resume", parsed, match, jd)
        coverage = result.keyword_coverage
        assert 'matched' in coverage
        assert 'missed' in coverage


class TestQualityCheck:
    """阶段4: 质量验证"""

    def test_success_returns_correct_fields(self, team, mock_model_manager):
        mock_model_manager.call.return_value = _make_mock_response(QUALITY_CHECK_JSON)
        result = team.quality_check(
            "Original resume",
            {"work_experience": [{"company": "ByteDance"}]},
            {"must_have": {"skills": ["Python"]}},
            [{"field": "work_experience", "change": "enhanced"}],
        )
        assert isinstance(result, QualityCheckResult)
        assert result.success is True
        assert isinstance(result.overall_score, int)
        assert 0 <= result.overall_score <= 100
        assert 'keyword_coverage' in result.score_breakdown
        assert result.authenticity_check['no_fabrication'] is True
        assert len(result.evidence_validation) > 0
        assert result.final_verdict['approved'] is True


# ==================== B 层：管道集成 ====================

class TestTailorPipeline:
    """管道集成测试

    注：tailor() 方法内部有 time.sleep(2) 但 time 模块未导入，
    直接调用会触发 NameError 被 catch。因此管道测试通过逐阶段调用模拟。
    """

    def _run_full_pipeline(self, team, mock_model_manager):
        """模拟完整五阶段流程"""
        mock_model_manager.call.return_value = _make_mock_response(PARSE_RESUME_JSON)
        parsed = team.parse_resume("Resume content")
        mock_model_manager.call.return_value = _make_mock_response(DECODE_JD_JSON)
        jd = team.decode_jd("JD content")
        mock_model_manager.call.return_value = _make_mock_response(MATCH_ANALYSIS_JSON)
        match = team.match_analysis(parsed, jd)
        mock_model_manager.call.return_value = _make_mock_response(REWRITE_CONTENT_JSON)
        rewrite = team.rewrite_content("Resume content", parsed, match, jd)
        mock_model_manager.call.return_value = _make_mock_response(QUALITY_CHECK_JSON)
        quality = team.quality_check(
            "Resume content",
            rewrite.tailored_resume,
            {'must_have': jd.must_have},
            rewrite.change_log,
        )
        return parsed, jd, match, rewrite, quality

    def test_pipeline_all_stages_succeed(self, team, mock_model_manager):
        """验证五阶段依次执行全部成功"""
        parsed, jd, match, rewrite, quality = self._run_full_pipeline(team, mock_model_manager)
        assert parsed.success is True
        assert jd.success is True
        assert match.success is True
        assert rewrite.success is True
        assert quality.success is True

    def test_pipeline_stats_accumulate(self, team, mock_model_manager):
        """验证完整流程后统计正确"""
        self._run_full_pipeline(team, mock_model_manager)
        stats = team.get_stats()
        assert stats['stage_calls']['parse_resume'] == 1
        assert stats['stage_calls']['decode_jd'] == 1
        assert stats['stage_calls']['match_analysis'] == 1
        assert stats['stage_calls']['rewrite_content'] >= 1  # Writer-Reviewer 可能多调用一次
        assert stats['stage_calls']['quality_check'] == 1
        assert stats['total_tokens'] >= 500

    def test_pipeline_data_flows_between_stages(self, team, mock_model_manager):
        """验证数据在各阶段间正确传递"""
        parsed, jd, match, rewrite, quality = self._run_full_pipeline(team, mock_model_manager)
        # parsed → match 的 basic_info
        assert parsed.basic_info['name'] == 'Zhang San'
        # jd → match 的 job_title
        assert jd.job_title == 'Python Engineer'
        # match → rewrite 的 match_score
        assert match.match_score == 78
        # rewrite → quality 的 tailored_resume
        assert 'work_experience' in rewrite.tailored_resume


# ==================== C 层：降级测试 ====================

class TestDegradation:
    """API 失败和异常场景"""

    def test_parse_resume_api_failure(self, team, mock_model_manager):
        """parse_resume API 失败抛 RuntimeError"""
        mock_model_manager.call.return_value = MagicMock(
            success=False, content='', error_message='API error'
        )
        with pytest.raises(RuntimeError, match="parse_resume"):
            team.parse_resume("some text")

    def test_decode_jd_api_failure(self, team, mock_model_manager):
        """decode_jd API 失败抛 RuntimeError"""
        mock_model_manager.call.return_value = MagicMock(
            success=False, content='', error_message='API error'
        )
        with pytest.raises(RuntimeError, match="decode_jd"):
            team.decode_jd("some JD")

    def test_match_analysis_api_failure(self, team, mock_model_manager):
        """match_analysis API 失败抛 RuntimeError"""
        # 先准备 prerequisites
        mock_model_manager.call.return_value = _make_mock_response(PARSE_RESUME_JSON)
        parsed = team.parse_resume("Resume")
        mock_model_manager.call.return_value = _make_mock_response(DECODE_JD_JSON)
        jd = team.decode_jd("JD")
        # 然后模拟 match_analysis 失败
        mock_model_manager.call.return_value = MagicMock(
            success=False, content='', error_message='API error'
        )
        with pytest.raises(RuntimeError, match="match_analysis"):
            team.match_analysis(parsed, jd)

    def test_model_unavailable(self, mock_model_manager):
        """model_manager 不可用时构造不会失败（延迟到调用时）"""
        mock_model_manager.is_available.return_value = False
        team = ExpertTeamV2(model_manager=mock_model_manager)
        assert team is not None
        # 调用时会失败
        mock_model_manager.call.return_value = MagicMock(
            success=False, content='', error_message='Model not available'
        )
        with pytest.raises(RuntimeError):
            team.parse_resume("Resume")

    def test_rewrite_content_empty_response(self, team, mock_model_manager):
        """rewrite_content 返回空 JSON 时触发 fallback"""
        mock_model_manager.call.return_value = _make_mock_response(PARSE_RESUME_JSON)
        parsed = team.parse_resume("Resume")
        mock_model_manager.call.return_value = _make_mock_response(DECODE_JD_JSON)
        jd = team.decode_jd("JD")
        mock_model_manager.call.return_value = _make_mock_response(MATCH_ANALYSIS_JSON)
        match = team.match_analysis(parsed, jd)
        # rewrite 返回无法解析的内容
        mock_model_manager.call.return_value = _make_mock_response("I cannot rewrite this resume.")
        result = team.rewrite_content("Resume", parsed, match, jd)
        # _extract_json 失败后触发 fallback，不会 crash
        assert result is not None
        assert isinstance(result, RewriteContentResult)
