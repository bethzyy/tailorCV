"""
配额管理模块

管理用户套餐配额检查和使用扣减。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple

from .database import db
from .config import config

logger = logging.getLogger(__name__)


def check_quota(user_id: int) -> Tuple[bool, Dict[str, Any]]:
    """
    检查用户是否有可用配额

    Args:
        user_id: 用户ID

    Returns:
        (can_use, info): 是否可以使用，配额信息
    """
    # 开发者账号：跳过配额检查
    user = db.get_user_by_id(user_id)
    if user and user.get('email') in config.DEV_EMAILS:
        return True, {
            'can_use': True,
            'plan_type': 'developer',
            'is_developer': True,
        }

    quota_info = db.get_user_quota(user_id)
    plan_type = quota_info['plan_type']
    plan_config = config.PLANS.get(plan_type, config.PLANS['free'])

    # 月卡/季卡用户：检查日上限
    if plan_type in ('monthly', 'quarterly'):
        daily_limit = plan_config['daily_limit']
        today_count = db.get_user_usage_count(user_id)
        if today_count >= daily_limit:
            return False, {
                'can_use': False,
                'reason': f'今日已达使用上限（{daily_limit}次），明天再试',
                'plan_type': plan_type,
                'daily_used': today_count,
                'daily_limit': daily_limit,
            }
        return True, {
            'can_use': True,
            'plan_type': plan_type,
            'daily_used': today_count,
            'daily_limit': daily_limit,
        }

    # 按次用户：检查剩余配额
    remaining = quota_info['quota_remaining']
    if remaining <= 0:
        return False, {
            'can_use': False,
            'reason': '配额已用完，请购买套餐',
            'plan_type': plan_type,
            'quota_total': quota_info['quota_total'],
            'quota_used': quota_info['quota_used'],
            'quota_remaining': 0,
        }

    return True, {
        'can_use': True,
        'plan_type': plan_type,
        'quota_total': quota_info['quota_total'],
        'quota_used': quota_info['quota_used'],
        'quota_remaining': remaining,
    }


def use_quota(user_id: int, task_id: str = None,
              session_id: str = None, tokens_used: int = 0) -> bool:
    """
    扣减用户配额

    Args:
        user_id: 用户ID
        task_id: 任务ID
        session_id: 会话ID
        tokens_used: 消耗的 token 数

    Returns:
        bool: 是否成功
    """
    return db.record_usage(user_id, task_id, session_id, tokens_used)


def activate_plan(user_id: int, plan_type: str) -> bool:
    """
    激活用户套餐

    Args:
        user_id: 用户ID
        plan_type: 套餐类型 (pack5/monthly/quarterly)

    Returns:
        bool: 是否成功
    """
    plan_config = config.PLANS.get(plan_type)
    if not plan_config:
        logger.error(f"未知套餐类型: {plan_type}")
        return False

    with db._get_connection() as conn:
        cursor = conn.cursor()

        if plan_type == 'pack5':
            # 按次包：在现有配额基础上累加
            cursor.execute('''
                UPDATE users SET plan_type = 'pack5',
                quota_total = quota_total + ?,
                plan_expires_at = NULL
                WHERE id = ?
            ''', (plan_config['quota'], user_id))
        elif plan_type in ('monthly', 'quarterly'):
            # 月卡/季卡：设置到期时间和无限配额
            days = 30 if plan_type == 'monthly' else 90
            expires_at = datetime.now() + timedelta(days=days)
            cursor.execute('''
                UPDATE users SET plan_type = ?, quota_total = -1,
                quota_used = 0, plan_expires_at = ?
                WHERE id = ?
            ''', (plan_type, expires_at.isoformat(), user_id))
        else:
            logger.error(f"不支持的套餐类型: {plan_type}")
            return False

        return cursor.rowcount > 0


def get_quota_display(user_id: int) -> Dict[str, Any]:
    """
    获取用户配额展示信息（用于前端显示）

    Args:
        user_id: 用户ID

    Returns:
        dict: 配额展示信息
    """
    user = db.get_user_by_id(user_id)
    if not user:
        return {'plan_type': 'free', 'plan_name': '免费体验', 'remaining': 0, 'is_expired': False}

    # 开发者账号：显示无限额度
    if user.get('email') in config.DEV_EMAILS:
        return {
            'plan_type': 'developer',
            'plan_name': '开发者',
            'remaining': -1,  # -1 表示无限
            'is_developer': True,
            'is_expired': False,
        }

    quota_info = db.get_user_quota(user_id)
    plan_config = config.PLANS.get(quota_info['plan_type'], config.PLANS['free'])

    result = {
        'plan_type': quota_info['plan_type'],
        'plan_name': plan_config['name'],
        'is_expired': quota_info.get('is_expired', False),
    }

    if quota_info['plan_type'] in ('monthly', 'quarterly'):
        today_count = db.get_user_usage_count(user_id)
        result['daily_used'] = today_count
        result['daily_limit'] = plan_config['daily_limit']
        result['remaining'] = plan_config['daily_limit'] - today_count
        result['plan_expires_at'] = quota_info.get('plan_expires_at')
    else:
        result['quota_total'] = quota_info['quota_total']
        result['quota_used'] = quota_info['quota_used']
        result['remaining'] = quota_info['quota_remaining']

    return result
