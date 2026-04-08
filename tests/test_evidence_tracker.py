"""
依据追踪器单元测试

测试 core/evidence_tracker.py — 依据验证、可疑关键词检测、模糊匹配。
mock _ai_validate 以避免真实 AI 调用。
"""

import pytest
from unittest.mock import MagicMock
from core.evidence_tracker import EvidenceTracker, ValidationResult, EvidenceReport


@pytest.fixture
def tracker():
    return EvidenceTracker(model_manager=None)


@pytest.fixture
def tracker_with_mock_ai():
    """带 mock AI 验证器的 tracker"""
    mm = MagicMock()
    mm.call.return_value = MagicMock(
        success=True,
        content='{"valid": false, "confidence": 0.3, "reason": "内容无法找到依据"}'
    )
    return EvidenceTracker(model_manager=mm)


class TestFuzzyMatch:
    """模糊匹配"""

    def test_identical_text(self, tracker):
        """完全相同的文本"""
        sim = tracker._fuzzy_match("Python后端开发工程师", "Python后端开发工程师")
        assert sim == 1.0

    def test_similar_text(self, tracker):
        """相似文本"""
        sim = tracker._fuzzy_match("负责后端服务开发", "负责后端服务的开发")
        assert sim > 0.5

    def test_different_text(self, tracker):
        """完全不同的文本"""
        sim = tracker._fuzzy_match("Python后端开发", "市场营销策划")
        assert sim < 0.5

    def test_empty_text(self, tracker):
        """空文本"""
        assert tracker._fuzzy_match("", "some text") == 0.0
        assert tracker._fuzzy_match("some text", "") == 0.0
        assert tracker._fuzzy_match("", "") == 0.0

    def test_one_empty(self, tracker):
        """一侧为空"""
        sim = tracker._fuzzy_match("有内容", "")
        assert sim == 0.0


class TestSuspiciousKeywords:
    """可疑关键词检测"""

    def test_no_suspicious(self, tracker):
        """正常文本"""
        result = tracker._check_suspicious_keywords("负责后端服务开发，使用Python和Go语言")
        assert result == []

    def test_suspicious_chinese(self, tracker):
        """包含可疑中文关键词"""
        result = tracker._check_suspicious_keywords("精通各种技术，是业界领先的技术专家")
        assert len(result) >= 2

    def test_suspicious_english(self, tracker):
        """包含可疑英文关键词"""
        result = tracker._check_suspicious_keywords("world-class expert in AI")
        assert len(result) >= 2


class TestValidateContent:
    """单条内容验证"""

    def test_identical_content_passes(self, tracker):
        """完全相同的内容通过"""
        original = "负责Python后端开发"
        tailored = "负责Python后端开发"
        result = tracker.validate_content(original, {
            'id': 'work_1',
            'original': original,
            'tailored': tailored,
            'evidence': {'confidence': 0.9}
        })
        assert result.action == 'pass'

    def test_low_similarity_rejected(self, tracker):
        """低相似度内容被拒绝"""
        original = "负责前端开发"
        tailored = "精通Kubernetes和Docker，是业界领先的架构专家"
        result = tracker.validate_content(original, {
            'id': 'work_1',
            'original': original,
            'tailored': tailored,
            'evidence': {'confidence': 0.9}
        })
        assert result.action == 'reject'

    def test_needs_review_low_confidence(self, tracker):
        """低置信度触发人工确认"""
        original = "负责Python后端开发"
        tailored = "负责Python后端开发"
        result = tracker.validate_content(original, {
            'id': 'work_1',
            'original': original,
            'tailored': tailored,
            'evidence': {'confidence': 0.1}
        })
        assert result.action == 'needs_review'

    def test_ai_validate_called_for_suspicious(self, tracker_with_mock_ai):
        """可疑内容触发 AI 验证"""
        original = "负责Python后端开发"
        tailored = "负责Python后端开发，精通各种技术"
        result = tracker_with_mock_ai.validate_content(original, {
            'id': 'work_1',
            'original': original,
            'tailored': tailored,
            'evidence': {'confidence': 0.1}
        })
        # "精通" 是可疑关键词 + 低置信度 + 有 model_manager → AI 验证
        assert tracker_with_mock_ai.validation_stats['ai_checks'] >= 1

    def test_no_model_manager_no_ai_call(self, tracker):
        """无 AI 管理器时不调用 AI"""
        original = "负责开发"
        tailored = "负责开发"
        tracker.validate_content(original, {
            'id': 'work_1',
            'original': original,
            'tailored': tailored,
            'evidence': {'confidence': 0.1}
        })
        assert tracker.validation_stats['ai_checks'] == 0


class TestValidateResume:
    """整体验证"""

    def test_full_validation(self, tracker):
        """完整简历验证"""
        original = "负责Python后端开发"
        tailored = {
            'work_experience': [
                {
                    'id': 'work_1',
                    'original': original,
                    'tailored': original,
                    'evidence': {'confidence': 0.9}
                }
            ],
            'projects': [],
            'skills': [],
            'education': []
        }
        report = tracker.validate_resume(original, tailored)
        assert isinstance(report, EvidenceReport)
        assert report.total_items == 1
        assert report.validated == 1

    def test_reject_all(self, tracker):
        """全部被拒绝"""
        tailored = {
            'work_experience': [
                {
                    'id': 'w1',
                    'original': 'a',
                    'tailored': 'completely different text',
                    'evidence': {'confidence': 0.9}
                },
            ],
            'projects': [],
            'skills': [],
            'education': []
        }
        report = tracker.validate_resume('a', tailored)
        assert report.total_items == 1
        assert report.rejected == 1

    def test_empty_sections(self, tracker):
        """空章节不报错"""
        report = tracker.validate_resume("some text", {
            'work_experience': [],
            'projects': [],
            'skills': [],
            'education': []
        })
        assert report.total_items == 0
        assert report.coverage == 0.0


class TestStats:
    """验证统计"""

    def test_stats_tracking(self, tracker):
        """统计信息正确更新"""
        tracker.validate_content("原始", {
            'id': '1', 'original': '原始', 'tailored': '原始',
            'evidence': {'confidence': 0.9}
        })
        stats = tracker.get_stats()
        assert stats['local_checks'] == 1
        assert stats['passed'] == 1
