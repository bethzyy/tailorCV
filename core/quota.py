"""
配额管理模块

管理用户套餐配额检查和使用扣减。
"""

import logging
from datetime import datetime, timedelta
from typing import Dict, Any, Tuple, Optional

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
    if is_dev_user(user_id):
        return True, {
            'can_use': True,
            'plan_type': 'developer',
            'is_developer': True,
        }

    quota_info = get_user_quota_info(user_id)
    plan_type = quota_info['plan_type']
    plan_config = config.PLANS.get(plan_type, config.PLANS['free'])

    if is_monthly_or_quarterly_plan(plan_type):
        return check_daily_limit(user_id, plan_config)
    else:
        return check_remaining_quota(quota_info)

def is_dev_user(user_id: int) -> bool:
    try:
        user = db.get_user_by_id(user_id)
        return user and user.get('email') in config.DEV_EMAILS
    except Exception as e:
        logger.error(f"检查开发者用户时出错: {e}")
        return False

def get_user_quota_info(user_id: int) -> Dict[str, Any]:
    try:
        return db.get_user_quota(user_id)
    except Exception as e:
        logger.error(f"获取用户配额信息时出错: {e}")
        # 返回默认值以防止程序崩溃
        return {
            'plan_type': 'free',
            'quota_total': 0,
            'quota_used': 0,
            'quota_remaining': 0,
            'is_expired': False
        }

def is_monthly_or_quarterly_plan(plan_type: str) -> bool:
    return plan_type in ('monthly', 'quarterly')

def check_daily_limit(user_id: int, plan_config: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    try:
        daily_limit = plan_config['daily_limit']
        today_count = db.get_user_usage_count(user_id)
        if today_count >= daily_limit:
            return False, {
                'can_use': False,
                'reason': f'今日已达使用上限（{daily_limit}次），明天再试',
                'plan_type': plan_config['type'],
                'daily_used': today_count,
                'daily_limit': daily_limit,
            }
        return True, {
            'can_use': True,
            'plan_type': plan_config['type'],
            'daily_used': today_count,
            'daily_limit': daily_limit,
        }
    except Exception as e:
        logger.error(f"检查每日限额时出错: {e}")
        return False, {
            'can_use': False,
            'reason': '系统错误，请稍后再试',
            'plan_type': plan_config.get('type', 'unknown'),
        }

def check_remaining_quota(quota_info: Dict[str, Any]) -> Tuple[bool, Dict[str, Any]]:
    remaining = quota_info['quota_remaining']
    if remaining <= 0:
        return False, {
            'can_use': False,
            'reason': '配额已用完，请购买套餐',
            'plan_type': quota_info['plan_type'],
            'quota_total': quota_info['quota_total'],
            'quota_used': quota_info['quota_used'],
            'quota_remaining': 0,
        }
    return True, {
        'can_use': True,
        'plan_type': quota_info['plan_type'],
        'quota_total': quota_info['quota_total'],
        'quota_used': quota_info['quota_used'],
        'quota_remaining': remaining,
    }

def use_quota(user_id: int, task_id: Optional[str] = None,
              session_id: Optional[str] = None, tokens_used: int = 0) -> bool:
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
    try:
        return db.record_usage(user_id, task_id, session_id, tokens_used)
    except Exception as e:
        logger.error(f"记录使用时出错: {e}")
        return False

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

    conn = None
    try:
        conn = db._get_connection()
        cursor = conn.cursor()
        
        if plan_type == 'pack5':
            cursor.execute('''
                UPDATE users SET plan_type = 'pack5',
                quota_total = quota_total + ?,
                plan_expires_at = NULL
                WHERE id = ?
            ''', (plan_config['quota'], user_id))
        elif plan_type in ('monthly', 'quarterly'):
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

        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        logger.error(f"激活套餐时出错: {e}")
        if conn:
            try:
                conn.rollback()
            except Exception as rollback_err:
                logger.error(f"回滚事务时出错: {rollback_err}")
        return False
    finally:
        if conn:
            conn.close()

def get_quota_display(user_id: int) -> Dict[str, Any]:
    """
    获取用户配额展示信息（用于前端显示）

    Args:
        user_id: 用户ID

    Returns:
        dict: 配额展示信息
    """
    try:
        user = db.get_user_by_id(user_id)
        if not user:
            return {'plan_type': 'free', 'plan_name': '免费体验', 'remaining': 0, 'is_expired': False}

        if is_dev_user(user_id):
            return {
                'plan_type': 'developer',
                'plan_name': '开发者',
                'remaining': -1,  # -1 表示无限
                'is_developer': True,
                'is_expired': False,
            }

        quota_info = get_user_quota_info(user_id)
        plan_config = config.PLANS.get(quota_info['plan_type'], config.PLANS['free'])

        result = {
            'plan_type': quota_info['plan_type'],
            'plan_name': plan_config['name'],
            'is_expired': quota_info.get('is_expired', False),
        }

        if is_monthly_or_quarterly_plan(quota_info['plan_type']):
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
    except Exception as e:
        logger.error(f"获取配额展示信息时出错: {e}")
        return {
            'plan_type': 'free',
            'plan_name': '免费体验',
            'remaining': 0,
            'is_expired': False,
            'error': '系统错误'
        }
