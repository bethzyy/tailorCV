import unittest
from core.providers.base_provider import ModelResponse, BaseModelProvider


class MockModelProvider(BaseModelProvider):
    """用于测试的模拟提供者"""

    def __init__(self, models=None):
        self._models = models or {"model_1": "Model One", "model_2": "Model Two"}

    @property
    def provider_id(self) -> str:
        return "mock_provider"

    @property
    def provider_name(self) -> str:
        return "Mock Provider"

    @property
    def available_models(self) -> dict:
        return self._models

    def call(self, prompt: str, model_id: str = None, **kwargs) -> ModelResponse:
        return ModelResponse(
            success=True,
            content="mock response",
            model_id=model_id or self.get_default_model(),
            model_name=self.get_model_name(model_id or self.get_default_model())
        )

    def is_available(self) -> bool:
        return True


class TestModelResponse(unittest.TestCase):
    """测试 ModelResponse 数据结构"""

    def test_initialization_with_defaults(self):
        """测试带默认值的初始化"""
        response = ModelResponse(
            success=True,
            content="test",
            model_id="id",
            model_name="name"
        )
        self.assertTrue(response.success)
        self.assertEqual(response.content, "test")
        self.assertEqual(response.model_id, "id")
        self.assertEqual(response.model_name, "name")
        self.assertEqual(response.tokens_used, 0)
        self.assertEqual(response.latency_ms, 0)
        self.assertEqual(response.error_message, "")

    def test_initialization_with_all_args(self):
        """测试指定所有参数的初始化"""
        response = ModelResponse(
            success=False,
            content="",
            model_id="id",
            model_name="name",
            tokens_used=100,
            latency_ms=50,
            error_message="Error"
        )
        self.assertFalse(response.success)
        self.assertEqual(response.tokens_used, 100)
        self.assertEqual(response.latency_ms, 50)
        self.assertEqual(response.error_message, "Error")

    def test_to_dict(self):
        """测试转换为字典"""
        response = ModelResponse(
            success=True,
            content="test",
            model_id="id",
            model_name="name",
            tokens_used=10,
            latency_ms=20,
            error_message=""
        )
        expected = {
            'success': True,
            'content': 'test',
            'model_id': 'id',
            'model_name': 'name',
            'tokens_used': 10,
            'latency_ms': 20,
            'error_message': ''
        }
        self.assertEqual(response.to_dict(), expected)


class TestBaseModelProvider(unittest.TestCase):
    """测试 BaseModelProvider 抽象基类"""

    def test_cannot_instantiate_abstract_class(self):
        """测试无法实例化抽象基类"""
        with self.assertRaises(TypeError):
            BaseModelProvider()

    def test_get_default_model(self):
        """测试获取默认模型"""
        provider = MockModelProvider()
        self.assertEqual(provider.get_default_model(), "model_1")

    def test_get_default_model_empty(self):
        """测试可用模型为空时获取默认模型"""
        provider = MockModelProvider(models={})
        self.assertEqual(provider.get_default_model(), "")

    def test_get_model_name(self):
        """测试获取模型显示名称"""
        provider = MockModelProvider()
        self.assertEqual(provider.get_model_name("model_1"), "Model One")

    def test_get_model_name_unknown(self):
        """测试获取未知模型的显示名称"""
        provider = MockModelProvider()
        self.assertEqual(provider.get_model_name("unknown_model"), "unknown_model")


if __name__ == '__main__':
    unittest.main()
