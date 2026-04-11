"""
测试支付 Provider 抽象基类
"""

import pytest
from core.payment.base import BasePaymentProvider


class DummyPaymentProvider(BasePaymentProvider):
    """用于测试的具体实现"""

    provider_id = 'dummy'
    provider_name = '测试支付'

    def create_qr_order(self, order_no: str, amount: float,
                        description: str):
        return {'code_url': 'https://example.com/qr'}

    def query_order(self, order_no: str):
        return 'SUCCESS'

    def verify_notify(self, request):
        return {'order_no': '123', 'transaction_id': 'tx_123'}

    def is_available(self):
        return True


class UnavailablePaymentProvider(BasePaymentProvider):
    """不可用的支付提供商"""

    provider_id = 'unavailable'
    provider_name = '不可用支付'

    def create_qr_order(self, order_no: str, amount: float,
                        description: str):
        return {}

    def query_order(self, order_no: str):
        return None

    def verify_notify(self, request):
        return None

    def is_available(self):
        return False


class TestBasePaymentProvider:
    """测试 BasePaymentProvider 抽象基类"""

    def test_cannot_instantiate_abstract_class(self):
        """抽象基类不能直接实例化"""
        with pytest.raises(TypeError):
            BasePaymentProvider()

    def test_concrete_implementation_can_instantiate(self):
        """具体实现可以实例化"""
        provider = DummyPaymentProvider()
        assert provider is not None

    def test_provider_id(self):
        """测试 provider_id"""
        provider = DummyPaymentProvider()
        assert provider.provider_id == 'dummy'

    def test_provider_name(self):
        """测试 provider_name"""
        provider = DummyPaymentProvider()
        assert provider.provider_name == '测试支付'

    def test_get_info_available(self):
        """测试 get_info 方法 - 可用状态"""
        provider = DummyPaymentProvider()
        info = provider.get_info()
        assert info == {
            'provider_id': 'dummy',
            'provider_name': '测试支付',
            'available': True,
        }

    def test_get_info_unavailable(self):
        """测试 get_info 方法 - 不可用状态"""
        provider = UnavailablePaymentProvider()
        info = provider.get_info()
        assert info == {
            'provider_id': 'unavailable',
            'provider_name': '不可用支付',
            'available': False,
        }

    def test_create_qr_order(self):
        """测试 create_qr_order 方法"""
        provider = DummyPaymentProvider()
        result = provider.create_qr_order('order_001', 100.0, '测试商品')
        assert result == {'code_url': 'https://example.com/qr'}

    def test_query_order(self):
        """测试 query_order 方法"""
        provider = DummyPaymentProvider()
        result = provider.query_order('order_001')
        assert result == 'SUCCESS'

    def test_verify_notify(self):
        """测试 verify_notify 方法"""
        provider = DummyPaymentProvider()
        result = provider.verify_notify(None)
        assert result == {'order_no': '123', 'transaction_id': 'tx_123'}

    def test_is_available_true(self):
        """测试 is_available 方法 - 可用"""
        provider = DummyPaymentProvider()
        assert provider.is_available() is True

    def test_is_available_false(self):
        """测试 is_available 方法 - 不可用"""
        provider = UnavailablePaymentProvider()
        assert provider.is_available() is False

