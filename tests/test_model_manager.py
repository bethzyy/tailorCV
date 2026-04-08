"""
模型管理器单元测试

测试 core/model_manager.py — 模型调用、降级、统计。
mock provider 避免真实 API 调用。
"""

import pytest
from unittest.mock import MagicMock, patch
from core.model_manager import ModelManager
from core.providers.base_provider import ModelResponse


@pytest.fixture
def mock_provider():
    """mock provider"""
    provider = MagicMock()
    provider.provider_id = 'mock_provider'
    provider.available_models = ['glm-5', 'glm-4.6', 'glm-4-flash']
    provider.get_stats.return_value = {'total': 0}
    provider.is_available.return_value = True
    return provider


@pytest.fixture
def mm(mock_provider):
    return ModelManager(provider=mock_provider)


class TestCall:
    """模型调用"""

    def test_successful_call(self, mm, mock_provider):
        """正常调用"""
        mock_provider.call.return_value = ModelResponse(
            success=True,
            content='{"result": "ok"}',
            model_id='glm-5',
            model_name='GLM-5',
            tokens_used=100,
            latency_ms=500
        )
        response = mm.call('test prompt', task_type='analyze')
        assert response.success is True
        assert response.content == '{"result": "ok"}'

    def test_failed_call_returns_unsuccessful(self, mm, mock_provider):
        """所有模型失败时返回失败响应"""
        mock_provider.call.return_value = ModelResponse(
            success=False,
            content='',
            model_id='glm-5',
            model_name='GLM-5',
            error_message='API rate limit'
        )
        response = mm.call('test prompt')
        assert response.success is False
        assert response.error_message is not None

    def test_fallback_on_failure(self, mm, mock_provider):
        """主模型失败时降级到备用模型"""
        call_count = [0]

        def side_effect_call(**kwargs):
            call_count[0] += 1
            model = kwargs.get('model_id', 'glm-5')
            if model == 'glm-5':
                return ModelResponse(
                    success=False, content='', model_id=model, model_name=model,
                    error_message='overloaded'
                )
            return ModelResponse(
                success=True, content='fallback ok', model_id=model, model_name=model,
                tokens_used=50, latency_ms=300
            )

        mock_provider.call.side_effect = side_effect_call
        response = mm.call('test prompt')
        assert response.success is True
        assert mm.stats['fallback_used'] >= 1


class TestStats:
    """统计信息"""

    def test_initial_stats(self, mm):
        """初始统计"""
        stats = mm.get_stats()
        assert stats['total_calls'] == 0
        assert stats['success_calls'] == 0
        assert stats['failed_calls'] == 0

    def test_stats_after_calls(self, mm, mock_provider):
        """调用后统计更新"""
        mock_provider.call.return_value = ModelResponse(
            success=True, content='ok', model_id='glm-5', model_name='GLM-5',
            tokens_used=100, latency_ms=500
        )
        mm.call('prompt1')
        mm.call('prompt2')

        stats = mm.get_stats()
        assert stats['total_calls'] == 2
        assert stats['success_calls'] == 2
        assert stats['total_tokens'] == 200
        assert 'avg_latency_ms' in stats


class TestIsAvailable:
    """可用性检查"""

    def test_available(self, mm, mock_provider):
        """可用"""
        assert mm.is_available() is True

    def test_unavailable(self, mock_provider):
        """不可用"""
        mock_provider.is_available.return_value = False
        mm = ModelManager(provider=mock_provider)
        assert mm.is_available() is False


class TestCurrentModel:
    """当前模型"""

    def test_current_model(self, mm):
        """当前模型名"""
        assert mm.current_model is not None
        assert isinstance(mm.current_model, str)

    def test_current_provider(self, mm):
        """当前提供者"""
        assert mm.current_provider == 'mock_provider'
