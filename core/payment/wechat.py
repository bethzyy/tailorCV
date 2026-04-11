"""
微信支付 Provider

集成微信支付 Native 扫码支付，支持沙箱和生产环境。
签名验证和回调解密标记为 TODO，待生产接入时实现。
"""

import logging
from typing import Optional, Dict, Any
from pathlib import Path

from flask import Request

from .base import BasePaymentProvider
from . import config  # 引入配置模块，避免循环导入

logger = logging.getLogger(__name__)

class WechatProvider(BasePaymentProvider):
    """微信支付"""

    provider_id = 'wechat'
    provider_name = '微信支付'

    def __init__(self, config):
        self._config = config
        self._client = None
        self._init_client()

    def _init_client(self):
        """初始化微信支付客户端"""
        if not self._config.WECHAT_APP_ID or not self._config.WECHAT_KEY_PATH:
            return

        try:
            from wechatpayv3 import WeChatPay, WeChatPayType

            cert_path = Path(self._config.WECHAT_CERT_PATH)
            if not cert_path.exists():
                logger.error(f"微信支付证书文件不存在: {self._config.WECHAT_CERT_PATH}")
                return

            serial_path = Path(f'{self._config.WECHAT_CERT_PATH}.serial')
            key_path = Path(self._config.WECHAT_KEY_PATH)
            if not key_path.exists():
                logger.error(f"微信支付私钥文件不存在: {self._config.WECHAT_KEY_PATH}")
                return

            self._client = WeChatPay(
                wechatpay_type=WeChatPayType.NATIVE,
                mchid=self._config.WECHAT_MCH_ID,
                appid=self._config.WECHAT_APP_ID,
                private_key=key_path.read_text(),
                cert_serial_no=serial_path.read_text().strip() if serial_path.exists() else '',
                app_secret=self._config.WECHAT_API_KEY_V3,
                notify_url=self._config.WECHAT_NOTIFY_URL,
            )

            logger.info(f"微信支付初始化成功: appid={self._config.WECHAT_APP_ID[:8]}...")

        except ImportError:
            logger.warning("wechatpayv3 SDK 未安装")
        except Exception as e:
            logger.error(f"微信支付初始化失败: {e}")

    def is_available(self) -> bool:
        return self._client is not None or self._config.WECHAT_SANDBOX

    def create_qr_order(self, order_no: str, amount: float,
                        description: str) -> Dict[str, Any]:
        """
        创建微信 Native 支付订单

        调用微信支付 V3 API 的 JSAPI/Native 下单接口。
        """
        if self._config.WECHAT_SANDBOX or not self._client:
            logger.info(f"[微信沙箱] 模拟创建订单: {order_no}")
            return {
                'code_url': f'weixin://wxpay/bizpayurl?pr=sandbox_{order_no[:8]}',
                'sandbox': True,
            }

        total_fee = int(amount * 100)  # 微信支付单位为分

        try:
            code, message = self._client.pay(
                description=description,
                out_trade_no=order_no,
                amount={'total': total_fee, 'currency': 'CNY'},
            )

            if code == 200 and message.get('code_url'):
                return {'code_url': message['code_url']}
            else:
                raise RuntimeError(f"微信支付返回错误: code={code}, message={message}")

        except Exception as e:
            logger.error(f"微信支付创建订单失败: {order_no}, {e}")
            if self._config.WECHAT_SANDBOX:
                return {
                    'code_url': f'weixin://wxpay/bizpayurl?pr=sandbox_{order_no[:8]}',
                    'sandbox': True,
                }
            raise

    def query_order(self, order_no: str) -> Optional[str]:
        """查询微信支付订单状态"""
        if self._config.WECHAT_SANDBOX or not self._client:
            return None

        try:
            code, message = self._client.query(out_trade_no=order_no)
            if code == 200:
                trade_state = message.get('trade_state', '')
                status_map = {
                    'SUCCESS': 'SUCCESS',
                    'NOTPAY': 'WAITING',
                    'USERPAYING': 'WAITING',
                    'CLOSED': 'CLOSED',
                    'REVOKED': 'CLOSED',
                    'PAYERROR': 'CLOSED',
                }
                return status_map.get(trade_state)
            return None

        except Exception as e:
            logger.error(f"微信支付查询订单失败: {order_no}, {e}")
            return None

    def verify_notify(self, request: Request) -> Optional[Dict[str, Any]]:
        """
        验证微信支付回调通知

        TODO: 生产环境需要实现签名验证和数据解密。
        当前沙箱模式下直接解析。
        """
        if self._config.WECHAT_SANDBOX:
            # 沙箱模式：直接解析请求体
            try:
                data = request.get_json(force=True) or {}
                return {
                    'order_no': data.get('out_trade_no', ''),
                    'transaction_id': data.get('transaction_id', f'sandbox_{data.get("out_trade_no", "")}'),
                }
            except Exception as e:
                logger.error(f"微信沙箱回调解析失败: {e}")
                return None

        # 生产模式：验证签名（TODO）
        logger.warning("TODO: 实现微信支付回调签名验证")
        try:
            data = request.get_json(force=True) or {}
            # TODO: 使用 wechatpayv3 SDK 验签和解密
            # decrypted = self._client.decrypt_callback(request)
            return {
                'order_no': data.get('out_trade_no', ''),
                'transaction_id': data.get('transaction_id', ''),
            }
        except Exception as e:
            logger.error(f"微信支付回调处理异常: {e}")
            return None
