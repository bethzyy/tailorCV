"""
支付 Provider 抽象基类

定义统一的支付接口，所有支付提供商（支付宝、微信、Stripe 等）均需实现此接口。
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from flask import Request


class BasePaymentProvider(ABC):
    """支付提供商抽象基类"""

    provider_id: str = ''      # 'alipay' / 'wechat' / 'stripe'
    provider_name: str = ''    # '支付宝' / '微信支付'

    @abstractmethod
    def create_qr_order(self, order_no: str, amount: float,
                        description: str) -> Dict[str, Any]:
        """
        创建扫码支付订单

        Args:
            order_no: 商户订单号
            amount: 金额（元）
            description: 商品描述

        Returns:
            dict: {code_url: str, ...} 二维码链接
        """

    @abstractmethod
    def query_order(self, order_no: str) -> Optional[str]:
        """
        查询订单状态

        Args:
            order_no: 商户订单号

        Returns:
            'SUCCESS' / 'WAITING' / 'CLOSED' / None(查询失败)
        """

    @abstractmethod
    def verify_notify(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        验证并解析支付回调通知

        Args:
            request: Flask request 对象

        Returns:
            dict: {order_no: str, transaction_id: str, ...} 或 None(验签失败)
        """

    @abstractmethod
    def is_available(self) -> bool:
        """检查是否已配置且可用"""

    def get_info(self) -> Dict[str, str]:
        """获取 provider 基本信息"""
        return {
            'provider_id': self.provider_id,
            'provider_name': self.provider_name,
            'available': self.is_available(),
        }
