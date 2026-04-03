"""
用户认证模块

邮箱验证码登录/注册，支持可选登录时长。
"""

import random
import time
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from functools import wraps
from typing import Optional, Dict, Any

from .database import db
from .config import config

logger = logging.getLogger(__name__)

# 内存存储验证码（生产环境应使用 Redis）
_verification_codes: Dict[str, Dict[str, Any]] = {}


def send_code(email: str) -> bool:
    """
    发送邮箱验证码

    Args:
        email: 邮箱地址

    Returns:
        bool: 是否发送成功
    """
    if not _validate_email(email):
        return False

    # 防止频繁发送（60秒间隔）
    if email in _verification_codes:
        last_sent = _verification_codes[email]['sent_at']
        if time.time() - last_sent < 60:
            logger.warning(f"验证码发送过于频繁: {email}")
            return False

    # 生成6位验证码
    code = str(random.randint(100000, 999999))
    _verification_codes[email] = {
        'code': code,
        'sent_at': time.time(),
        'expires_at': time.time() + config.CODE_EXPIRE_SECONDS,
        'attempts': 0
    }

    # 发送邮件
    try:
        if config.EMAIL_SMTP_USER and config.EMAIL_SMTP_PASSWORD:
            return _send_via_smtp(email, code)
        else:
            # 开发模式：打印验证码到日志
            logger.info(f"[开发模式] 验证码 {email}: {code}")
            return True
    except Exception as e:
        logger.error(f"发送验证码失败: {email}, 错误: {e}")
        return False


def verify_code(email: str, code: str) -> bool:
    """
    验证邮箱验证码

    Args:
        email: 邮箱地址
        code: 验证码

    Returns:
        bool: 是否验证成功
    """
    if email not in _verification_codes:
        return False

    record = _verification_codes[email]

    # 检查过期
    if time.time() > record['expires_at']:
        del _verification_codes[email]
        return False

    # 检查尝试次数（最多5次）
    record['attempts'] += 1
    if record['attempts'] > 5:
        del _verification_codes[email]
        return False

    # 验证码匹配
    if record['code'] == code:
        del _verification_codes[email]
        return True

    return False


def login_or_register(email: str) -> Dict[str, Any]:
    """
    登录或注册用户

    Args:
        email: 邮箱地址

    Returns:
        dict: {user_id, email, is_new_user}
    """
    user = db.get_user_by_email(email)

    if user:
        db.update_user_login(user['id'])
        return {
            'user_id': user['id'],
            'email': user['email'],
            'nickname': user.get('nickname', ''),
            'is_new_user': False
        }
    else:
        user_id = db.create_user(email=email)
        if user_id:
            return {
                'user_id': user_id,
                'email': email,
                'nickname': '',
                'is_new_user': True
            }
        else:
            raise RuntimeError("用户创建失败")


def set_login_duration(duration: str):
    """
    设置登录有效期

    Args:
        duration: 'session' / '7d' / '30d' / 'forever'
    """
    from flask import session, make_response

    option = config.LOGIN_DURATION_OPTIONS.get(duration, config.LOGIN_DURATION_OPTIONS['session'])
    seconds = option['seconds']

    if seconds > 0:
        session.permanent = True
        # Flask 的 permanent_session_lifetime 控制服务端 session 过期时间
        from datetime import timedelta
        from flask import current_app
        current_app.permanent_session_lifetime = timedelta(seconds=seconds)


def login_required(f):
    """
    登录验证装饰器
    """
    @wraps(f)
    def decorated_function(*args, **kwargs):
        from flask import request, jsonify, session

        user_id = session.get('user_id')
        if not user_id:
            return jsonify({'success': False, 'error': '请先登录', 'code': 401}), 401

        user = db.get_user_by_id(user_id)
        if not user or not user.get('is_active'):
            session.clear()
            return jsonify({'success': False, 'error': '用户不存在或已禁用', 'code': 401}), 401

        request.user_id = user_id
        request.user = user

        return f(*args, **kwargs)

    return decorated_function


def get_current_user() -> Optional[Dict[str, Any]]:
    """从 Flask session 获取当前用户"""
    from flask import session
    user_id = session.get('user_id')
    if user_id:
        return db.get_user_by_id(user_id)
    return None


def _validate_email(email: str) -> bool:
    """验证邮箱格式"""
    import re
    return bool(re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email))


def _send_via_smtp(email: str, code: str) -> bool:
    """
    通过 SMTP 发送验证码邮件

    支持 QQ邮箱、163邮箱、Gmail 等。
    """
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = f'tailorCV 登录验证码：{code}'
        msg['From'] = f'{config.EMAIL_FROM_NAME} <{config.EMAIL_SMTP_USER}>'
        msg['To'] = email

        # HTML 邮件内容
        html_content = f"""
        <div style="max-width:480px; margin:0 auto; padding:30px; font-family:'Microsoft YaHei',sans-serif;">
            <div style="background:linear-gradient(135deg,#667eea,#764ba2); padding:20px; border-radius:12px 12px 0 0; text-align:center;">
                <h2 style="color:white; margin:0;">tailorCV 智能简历</h2>
            </div>
            <div style="background:#f9f9f9; padding:30px; border-radius:0 0 12px 12px; text-align:center;">
                <p style="color:#333; font-size:15px;">您正在登录 tailorCV，验证码为：</p>
                <div style="font-size:36px; font-weight:bold; color:#667eea; letter-spacing:8px; margin:20px 0;">
                    {code}
                </div>
                <p style="color:#999; font-size:13px;">验证码 {config.CODE_EXPIRE_SECONDS // 60} 分钟内有效，请勿泄露给他人。</p>
                <p style="color:#ccc; font-size:12px; margin-top:20px;">如非本人操作，请忽略此邮件。</p>
            </div>
        </div>
        """
        msg.attach(MIMEText(html_content, 'html', 'utf-8'))

        # 发送
        if config.EMAIL_SMTP_PORT == 465:
            # SSL
            server = smtplib.SMTP_SSL(config.EMAIL_SMTP_HOST, config.EMAIL_SMTP_PORT, timeout=10)
        else:
            # STARTTLS
            server = smtplib.SMTP(config.EMAIL_SMTP_HOST, config.EMAIL_SMTP_PORT, timeout=10)
            server.starttls()

        server.login(config.EMAIL_SMTP_USER, config.EMAIL_SMTP_PASSWORD)
        server.sendmail(config.EMAIL_SMTP_USER, email, msg.as_string())
        server.quit()

        logger.info(f"验证码邮件发送成功: {email}")
        return True

    except Exception as e:
        logger.error(f"SMTP 发送失败: {e}")
        return False
