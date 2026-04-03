"""
支付宝当面付 Provider

集成支付宝当面付（扫码支付），支持沙箱和生产环境。
使用官方 SDK alipay-sdk-python。
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from flask import Request

from .base import BasePaymentProvider
from .. import config

logger = logging.getLogger(__name__)


class AlipayProvider(BasePaymentProvider):
    """支付宝当面付"""

    provider_id = 'alipay'
    provider_name = '支付宝'

    def __init__(self):
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化支付宝客户端"""
        if not config.ALIPAY_APP_ID or not config.ALIPAY_PRIVATE_KEY_PATH:
            return

        try:
            from alipay.aop.api.DefaultAlipayClient import DefaultAlipayClient
            from alipay.aop.api.AlipayClientConfig import AlipayClientConfig

            private_key_path = Path(config.ALIPAY_PRIVATE_KEY_PATH)
            if not private_key_path.exists():
                logger.error(f"支付宝私钥文件不存在: {config.ALIPAY_PRIVATE_KEY_PATH}")
                return

            # 读取私钥
            private_key = private_key_path.read_text().strip()

            # 读取支付宝公钥
            alipay_public_key = ''
            if config.ALIPAY_PUBLIC_KEY_PATH:
                pub_key_path = Path(config.ALIPAY_PUBLIC_KEY_PATH)
                if pub_key_path.exists():
                    alipay_public_key = pub_key_path.read_text().strip()

            # 沙箱/生产网关
            if config.ALIPAY_SANDBOX:
                server_url = 'https://openapi-sandbox.dl.alipaydev.com/gateway.do'
            else:
                server_url = 'https://openapi.alipay.com/gateway.do'

            alipay_config = AlipayClientConfig(
                server_url=server_url,
                app_id=config.ALIPAY_APP_ID,
                app_private_key_string=private_key,
                alipay_public_key_string=alipay_public_key,
                charset='utf-8',
                sign_type='RSA2',
            )

            self._client = DefaultAlipayClient(alipay_config=alipay_config)

            mode = '沙箱' if config.ALIPAY_SANDBOX else '生产'
            logger.info(f"支付宝 {mode} 环境初始化成功: appid={config.ALIPAY_APP_ID[:8]}...")

        except ImportError:
            logger.error("alipay-sdk-python 未安装，请执行: pip install alipay-sdk-python")
        except Exception as e:
            logger.error(f"支付宝初始化失败: {e}")

    def is_available(self) -> bool:
        return self._client is not None

    def create_qr_order(self, order_no: str, amount: float,
                        description: str) -> Dict[str, Any]:
        """
        创建当面付扫码支付订单

        调用 alipay.trade.precreate 接口。
        """
        if not self._client:
            if config.ALIPAY_SANDBOX:
                logger.info(f"[支付宝沙箱] 模拟创建订单: {order_no}")
                return {
                    'code_url': f'https://qr.alipay.com/mock_{order_no[:12]}',
                    'sandbox': True,
                }
            raise RuntimeError("支付宝未配置或初始化失败")

        try:
            from alipay.aop.api.request.AlipayTradePrecreateRequest import AlipayTradePrecreateRequest

            model = self._client._model("AlipayTradePrecreateModel", {
                "out_trade_no": order_no,
                "total_amount": str(round(amount, 2)),
                "subject": description,
            })

            request = AlipayTradePrecreateRequest(biz_model=model)
            request.set_notify_url(config.ALIPAY_NOTIFY_URL)

            response = self._client.execute(request)

            if response.code == '10000':
                return {'code_url': response.qr_code}
            else:
                msg = response.msg or response.sub_msg or '未知错误'
                raise RuntimeError(f"支付宝下单失败: [{response.code}] {msg}")

        except Exception as e:
            logger.error(f"支付宝创建订单失败: {order_no}, {e}")
            if config.ALIPAY_SANDBOX:
                return {
                    'code_url': f'https://qr.alipay.com/mock_{order_no[:12]}',
                    'sandbox': True,
                }
            raise

    def query_order(self, order_no: str) -> Optional[str]:
        """
        查询订单状态

        调用 alipay.trade.query 接口。
        """
        if not self._client:
            return None

        try:
            from alipay.aop.api.request.AlipayTradeQueryRequest import AlipayTradeQueryRequest

            model = self._client._model("AlipayTradeQueryModel", {
                "out_trade_no": order_no,
            })

            request = AlipayTradeQueryRequest(biz_model=model)
            response = self._client.execute(request)

            if response.code == '10000':
                status_map = {
                    'TRADE_SUCCESS': 'SUCCESS',
                    'TRADE_FINISHED': 'SUCCESS',
                    'WAIT_BUYER_PAY': 'WAITING',
                    'TRADE_CLOSED': 'CLOSED',
                }
                return status_map.get(response.trade_status)
            return None

        except Exception as e:
            logger.error(f"支付宝查询订单失败: {order_no}, {e}")
            return None

    def verify_notify(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        验证支付宝异步通知

        支付宝通过 POST form data 发送通知。
        """
        if not self._client:
            logger.error("支付宝未初始化，无法验证回调")
            return None

        try:
            data = request.form.to_dict()
            if not data:
                logger.error("支付宝回调数据为空")
                return None

            trade_status = data.get('trade_status', '')
            if trade_status not in ('TRADE_SUCCESS', 'TRADE_FINISHED'):
                logger.info(f"支付宝回调非成功状态: {trade_status}")
                return None

            # TODO: 生产环境使用 SDK verify 方法验签
            # 目前沙箱模式直接信任
            if not config.ALIPAY_SANDBOX:
                logger.warning("TODO: 实现支付宝回调签名验证")

            return {
                'order_no': data.get('out_trade_no', ''),
                'transaction_id': data.get('trade_no', ''),
                'buyer_id': data.get('buyer_id', ''),
                'total_amount': data.get('total_amount', ''),
            }

        except Exception as e:
            logger.error(f"支付宝回调处理异常: {e}")
            return None
