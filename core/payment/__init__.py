"""
支付模块

支持多支付提供商，采用 provider 模式。
当前支持：支付宝当面付、微信支付（预留）。

对外统一接口：
- create_payment()       创建支付订单
- handle_payment_notify() 处理支付回调
- query_payment()        查询支付状态
- simulate_payment()     模拟支付（沙箱）
- get_available_providers() 获取可用支付方式列表
"""

import time
import uuid
import base64
import io
import logging
from typing import Optional, Dict, Any, List

from flask import Request

from ..database import db
from ..config import config
from .base import BasePaymentProvider
from .alipay import AlipayProvider
from .wechat import WechatProvider

logger = logging.getLogger(__name__)

# 注册所有支付 provider
_providers: Dict[str, BasePaymentProvider] = {
    'alipay': AlipayProvider(),
    'wechat': WechatProvider(),
}


def get_available_providers() -> List[Dict[str, Any]]:
    """
    获取所有可用的支付方式

    Returns:
        list: [{provider_id, provider_name, available}]
    """
    result = []
    order = ['alipay', 'wechat']
    for pid in order:
        provider = _providers.get(pid)
        if provider:
            info = provider.get_info()
            if info['available']:
                result.append(info)
    return result


def _get_provider(provider_id: str = None) -> BasePaymentProvider:
    """
    获取指定的支付 provider

    Args:
        provider_id: provider 标识，默认使用配置的默认支付方式

    Returns:
        BasePaymentProvider 实例
    """
    if not provider_id:
        provider_id = config.DEFAULT_PAYMENT_PROVIDER

    provider = _providers.get(provider_id)
    if not provider:
        raise ValueError(f"未知的支付方式: {provider_id}")
    if not provider.is_available():
        raise RuntimeError(f"支付方式 {provider.provider_name} 未配置或不可用")

    return provider


def _resolve_provider(provider_id: str = None) -> BasePaymentProvider:
    """
    解析并获取可用的支付 provider，支持回退逻辑

    Args:
        provider_id: 首选 provider 标识

    Returns:
        BasePaymentProvider 实例
    """
    try:
        return _get_provider(provider_id)
    except (ValueError, RuntimeError):
        available = get_available_providers()
        if not available:
            raise RuntimeError("没有可用的支付方式")
        fallback_provider = _get_provider(available[0]['provider_id'])
        logger.warning(f"支付方式 {provider_id} 不可用，回退到 {fallback_provider.provider_name}")
        return fallback_provider


def _ensure_pending_order(user_id: int, plan_type: str, plan_config: Dict[str, Any],
                          provider_id: str, amount: float) -> str:
    """
    确保存在待支付订单（复用或创建）

    Args:
        user_id: 用户ID
        plan_type: 套餐类型
        plan_config: 套餐配置
        provider_id: 支付方式标识
        amount: 金额

    Returns:
        str: 订单号
    """
    # 检查是否有未支付的待处理订单（同一 provider + 同一套餐）
    pending_order = db.get_pending_order(user_id, plan_type)
    if pending_order and pending_order.get('provider') == provider_id:
        order_no = pending_order['order_no']
        logger.info(f"复用待支付订单: {order_no}")
        return order_no

    order_no = _generate_order_no()
    db.create_order(order_no, user_id, plan_type, plan_config['name'],
                    amount, provider=provider_id)
    return order_no


def _create_payment_qr(provider: BasePaymentProvider, order_no: str,
                       amount: float, description: str) -> Dict[str, Any]:
    """
    调用支付接口创建二维码订单

    Args:
        provider: 支付 provider 实例
        order_no: 订单号
        amount: 金额
        description: 订单描述

    Returns:
        dict: 包含 code_url, sandbox 等信息的字典
    """
    result = provider.create_qr_order(order_no, amount, description)
    code_url = result.get('code_url', '')

    # 用 Python qrcode 包生成 base64 二维码图片
    qr_image = _generate_qr_base64(code_url)

    return {
        'code_url': code_url,
        'qr_image': qr_image,
        'sandbox': result.get('sandbox', False),
    }


def create_payment(user_id: int, plan_type: str,
                   provider_id: str = None) -> Dict[str, Any]:
    """
    创建支付订单

    Args:
        user_id: 用户ID
        plan_type: 套餐类型
        provider_id: 支付方式（可选，默认使用配置的默认支付方式）

    Returns:
        dict: {order_no, amount, plan_name, plan_type, code_url, provider, ...}
    """
    plan_config = config.PLANS.get(plan_type)
    if not plan_config:
        raise ValueError(f"未知套餐类型: {plan_type}")

    amount = plan_config['price']
    if amount <= 0:
        raise ValueError("免费套餐无需支付")

    # 获取 provider（支持回退）
    provider = _resolve_provider(provider_id)
    actual_provider_id = provider.provider_id

    # 确保订单存在
    order_no = _ensure_pending_order(user_id, plan_type, plan_config, actual_provider_id, amount)

    # 调用 provider 创建预付单
    description = f"智能简历定制 - {plan_config['name']}"
    try:
        qr_result = _create_payment_qr(provider, order_no, amount, description)

        return {
            'order_no': order_no,
            'amount': amount,
            'plan_name': plan_config['name'],
            'plan_type': plan_type,
            'provider': actual_provider_id,
            'provider_name': provider.provider_name,
            **qr_result,
        }
    except Exception as e:
        logger.error(f"创建支付订单失败: {e}")
        raise


def handle_payment_notify(request: Request, provider_id: str) -> bool:
    """
    处理支付回调通知

    Args:
        request: Flask request 对象
        provider_id: 支付方式标识

    Returns:
        bool: 处理是否成功
    """
    provider = _providers.get(provider_id)
    if not provider:
        logger.error(f"未知支付方式回调: {provider_id}")
        return False

    try:
        notify_data = provider.verify_notify(request)
        if not notify_data:
            logger.error(f"{provider.provider_name} 回调验签失败")
            return False

        order_no = notify_data.get('order_no', '')
        transaction_id = notify_data.get('transaction_id', '')

        # 查询订单
        order = db.get_order(order_no)
        if not order:
            logger.error(f"订单不存在: {order_no}")
            return False

        if order['status'] == 'paid':
            logger.info(f"订单已处理，跳过: {order_no}")
            return True  # 幂等处理

        # 更新订单状态
        db.update_order_paid(order_no, transaction_id)

        # 激活套餐
        from ..quota import activate_plan
        activate_plan(order['user_id'], order['plan_type'])

        logger.info(f"支付成功: {order_no}, provider={provider_id}, "
                     f"用户={order['user_id']}, 套餐={order['plan_type']}")
        return True

    except Exception as e:
        logger.error(f"处理支付回调异常: {provider_id}, {e}")
        return False


def query_payment(order_no: str) -> Dict[str, Any]:
    """
    查询支付状态

    Args:
        order_no: 订单号

    Returns:
        dict: {status, paid_at, ...}
    """
    order = db.get_order(order_no)
    if not order:
        return {'status': 'not_found'}

    # 如果订单未支付且未过期，主动查询支付平台
    if order['status'] == 'pending':
        provider_id = order.get('provider', '')
        provider = _providers.get(provider_id)

        if provider and provider.is_available():
            try:
                platform_status = provider.query_order(order_no)
                if platform_status == 'SUCCESS':
                    transaction_id = f'query_{order_no}'
                    db.update_order_paid(order_no, transaction_id)
                    from ..quota import activate_plan
                    activate_plan(order['user_id'], order['plan_type'])
                    order = db.get_order(order_no)
            except Exception as e:
                logger.error(f"查询支付状态失败: {order_no}, {e}")

    return {
        'order_no': order['order_no'],
        'status': order['status'],
        'plan_type': order['plan_type'],
        'plan_name': order['plan_name'],
        'amount': order['amount'],
        'provider': order.get('provider', ''),
        'paid_at': order.get('paid_at'),
        'created_at': order['created_at'],
    }


def simulate_payment(order_no: str) -> bool:
    """
    模拟支付成功（仅沙箱环境使用）
    """
    order = db.get_order(order_no)
    if not order or order['status'] != 'pending':
        return False

    transaction_id = f'sandbox_sim_{order_no}'
    db.update_order_paid(order_no, transaction_id)

    from ..quota import activate_plan
    activate_plan(order['user_id'], order['plan_type'])

    logger.info(f"[沙箱] 模拟支付成功: {order_no}")
    return True


def _generate_order_no() -> str:
    """生成唯一订单号"""
    return f"TCV{int(time.time() * 1000)}{uuid.uuid4().hex[:8].upper()}"


def _generate_qr_base64(code_url: str) -> str:
    """
    用 Python qrcode 包生成 base64 二维码图片

    Returns:
        str: base64 data URL (data:image/png;base64,...)，失败返回空字符串
    """
    if not code_url:
        return ''
    try:
        import qrcode
        qr = qrcode.QRCode(version=1, box_size=8, border=2, error_correction=qrcode.constants.ERROR_CORRECT_M)
        qr.add_data(code_url)
        qr.make(fit=True)
        img = qr.make_image(fill_color='black', back_color='white')
        buf = io.BytesIO()
        img.save(buf, format='PNG')
        # 修复说明：此处仅用于生成二维码图片展示，不涉及敏感数据加密或存储，故保留 base64 编码方式。
        return base64.b64encode(buf.getvalue()).decode('utf-8')
    except Exception as e:
        logger.error(f"生成二维码失败: {e}")
        return ''


__all__ = [
    'BasePaymentProvider',
    'create_payment',
    'handle_payment_notify',
    'query_payment',
    'simulate_payment',
    'get_available_providers',
]
