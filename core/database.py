"""
数据库存储模块

使用 SQLite 实现历史记录和任务状态的持久化存储。
"""

import sqlite3
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Optional
from contextlib import contextmanager

from .config import config

logger = logging.getLogger(__name__)


class Database:
    """SQLite 数据库管理器"""

    def __init__(self, db_path: str = None):
        """
        初始化数据库

        Args:
            db_path: 数据库文件路径，默认使用配置中的路径
        """
        self.db_path = db_path or config.DATABASE_PATH
        self._ensure_db_dir()
        self._init_tables()

    def _ensure_db_dir(self):
        """确保数据库目录存在"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

    @contextmanager
    def _get_connection(self):
        """获取数据库连接（上下文管理器）"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        except Exception as e:
            conn.rollback()
            logger.error(f"数据库操作失败: {e}")
            raise
        finally:
            conn.close()

    def _init_tables(self):
        """初始化数据库表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 任务表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    session_id TEXT,
                    status TEXT NOT NULL DEFAULT 'pending',
                    input_mode TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    completed_at TIMESTAMP,
                    error_message TEXT,
                    metadata TEXT
                )
            ''')

            # 简历定制历史表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS history (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT UNIQUE NOT NULL,
                    task_id TEXT,
                    candidate_name TEXT,
                    candidate_type TEXT DEFAULT 'experienced',
                    job_title TEXT,
                    company TEXT,
                    match_score INTEGER,
                    match_level TEXT,
                    original_resume TEXT,
                    tailored_resume TEXT,
                    jd_content TEXT,
                    evidence_report TEXT,
                    optimization_summary TEXT,
                    model_used TEXT,
                    tokens_used INTEGER,
                    processing_time_ms INTEGER,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                )
            ''')

            # 分析结果缓存表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS analysis_cache (
                    cache_key TEXT PRIMARY KEY,
                    resume_hash TEXT,
                    jd_hash TEXT,
                    analysis_result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    expires_at TIMESTAMP
                )
            ''')

            # 用户配置表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS user_config (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    config_key TEXT UNIQUE NOT NULL,
                    config_value TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 模板表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS templates (
                    template_id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    source TEXT NOT NULL,
                    file_path TEXT NOT NULL,
                    content_hash TEXT,
                    structure_confidence REAL,
                    sections TEXT,
                    variables TEXT,
                    description TEXT,
                    tags TEXT,
                    preview_image TEXT,
                    use_count INTEGER DEFAULT 0,
                    is_default INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')

            # 用户表（支持邮箱和手机号两种登录方式）
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    phone TEXT DEFAULT '',
                    email TEXT DEFAULT '',
                    nickname TEXT DEFAULT '',
                    plan_type TEXT DEFAULT 'free',
                    quota_total INTEGER DEFAULT 1,
                    quota_used INTEGER DEFAULT 0,
                    plan_expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    last_login_at TIMESTAMP,
                    is_active INTEGER DEFAULT 1,
                    UNIQUE(email)
                )
            ''')

            # 手机号唯一约束：仅对非空手机号生效
            cursor.execute('''
                CREATE UNIQUE INDEX IF NOT EXISTS idx_users_phone
                ON users(phone) WHERE phone != ''
            ''')

            # 订单表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS orders (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    order_no TEXT UNIQUE NOT NULL,
                    user_id INTEGER NOT NULL,
                    plan_type TEXT NOT NULL,
                    plan_name TEXT NOT NULL,
                    amount REAL NOT NULL,
                    status TEXT DEFAULT 'pending',
                    provider TEXT DEFAULT '',
                    transaction_id TEXT DEFAULT '',
                    wechat_transaction_id TEXT,
                    paid_at TIMESTAMP,
                    expires_at TIMESTAMP,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # 订单表迁移：新增字段
            cursor.execute("PRAGMA table_info(orders)")
            existing_columns = [col[1] for col in cursor.fetchall()]
            if 'provider' not in existing_columns:
                cursor.execute("ALTER TABLE orders ADD COLUMN provider TEXT DEFAULT ''")
                logger.info("订单表新增 provider 字段")
            if 'transaction_id' not in existing_columns:
                cursor.execute("ALTER TABLE orders ADD COLUMN transaction_id TEXT DEFAULT ''")
                logger.info("订单表新增 transaction_id 字段")
                # 迁移旧数据
                cursor.execute('''
                    UPDATE orders SET transaction_id = wechat_transaction_id
                    WHERE transaction_id = '' AND wechat_transaction_id IS NOT NULL
                ''')

            # 使用记录表
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS usage_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER NOT NULL,
                    task_id TEXT,
                    session_id TEXT,
                    tokens_used INTEGER DEFAULT 0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (user_id) REFERENCES users(id)
                )
            ''')

            # 创建索引
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_history_created_at
                ON history(created_at DESC)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_history_session_id
                ON history(session_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_tasks_status
                ON tasks(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_user_config_key
                ON user_config(config_key)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_templates_source
                ON templates(source)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_templates_is_default
                ON templates(is_default)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_phone
                ON users(phone)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_users_email
                ON users(email)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_orders_user_id
                ON orders(user_id)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_orders_status
                ON orders(status)
            ''')
            cursor.execute('''
                CREATE INDEX IF NOT EXISTS idx_usage_records_user_id
                ON usage_records(user_id)
            ''')

            logger.info(f"数据库初始化完成: {self.db_path}")

    # ==================== 任务状态管理 ====================

    def create_task(self, task_id: str, session_id: str,
                    input_mode: str = 'file', metadata: dict = None) -> bool:
        """
        创建新任务

        Args:
            task_id: 任务ID
            session_id: 会话ID
            input_mode: 输入模式 (file/guided)
            metadata: 额外元数据

        Returns:
            bool: 是否创建成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO tasks (task_id, session_id, input_mode, status, metadata)
                VALUES (?, ?, ?, 'pending', ?)
            ''', (task_id, session_id, input_mode, json.dumps(metadata or {})))
            return cursor.rowcount > 0

    def update_task_status(self, task_id: str, status: str,
                           error_message: str = None) -> bool:
        """
        更新任务状态

        Args:
            task_id: 任务ID
            status: 新状态
            error_message: 错误信息（可选）

        Returns:
            bool: 是否更新成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            completed_at = 'CURRENT_TIMESTAMP' if status == 'completed' else 'NULL'

            if error_message:
                cursor.execute('''
                    UPDATE tasks
                    SET status = ?, updated_at = CURRENT_TIMESTAMP,
                        error_message = ?
                    WHERE task_id = ?
                ''', (status, error_message, task_id))
            else:
                cursor.execute('''
                    UPDATE tasks
                    SET status = ?, updated_at = CURRENT_TIMESTAMP
                    WHERE task_id = ?
                ''', (status, task_id))
            return cursor.rowcount > 0

    def get_task(self, task_id: str) -> Optional[Dict[str, Any]]:
        """获取任务信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM tasks WHERE task_id = ?', (task_id,))
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None

    def get_pending_tasks(self) -> List[Dict[str, Any]]:
        """获取所有待处理任务"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM tasks
                WHERE status = 'pending'
                ORDER BY created_at ASC
            ''')
            return [dict(row) for row in cursor.fetchall()]

    # ==================== 历史记录管理 ====================

    def save_history(self, session_id: str, data: Dict[str, Any]) -> bool:
        """
        保存定制历史记录

        Args:
            session_id: 会话ID
            data: 历史记录数据

        Returns:
            bool: 是否保存成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO history (
                    session_id, task_id, candidate_name, candidate_type,
                    job_title, company, match_score, match_level,
                    original_resume, tailored_resume, jd_content,
                    evidence_report, optimization_summary,
                    model_used, tokens_used, processing_time_ms
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                session_id,
                data.get('task_id'),
                data.get('candidate_name', ''),
                data.get('candidate_type', 'experienced'),
                data.get('job_title', ''),
                data.get('company', ''),
                data.get('match_score'),
                data.get('match_level', ''),
                data.get('original_resume', ''),
                json.dumps(data.get('tailored_resume', {}), ensure_ascii=False) if isinstance(data.get('tailored_resume'), dict) else data.get('tailored_resume', ''),
                data.get('jd_content', ''),
                json.dumps(data.get('evidence_report', {}), ensure_ascii=False),
                json.dumps(data.get('optimization_summary', {}), ensure_ascii=False),
                data.get('model_used', ''),
                data.get('tokens_used', 0),
                data.get('processing_time_ms', 0)
            ))
            return cursor.rowcount > 0

    def get_history(self, session_id: str) -> Optional[Dict[str, Any]]:
        """获取指定会话的历史记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM history WHERE session_id = ?', (session_id,))
            row = cursor.fetchone()
            if row:
                result = dict(row)
                # 解析JSON字段
                if result.get('evidence_report'):
                    result['evidence_report'] = json.loads(result['evidence_report'])
                if result.get('optimization_summary'):
                    result['optimization_summary'] = json.loads(result['optimization_summary'])
                if result.get('tailored_resume'):
                    try:
                        result['tailored_resume'] = json.loads(result['tailored_resume'])
                    except (json.JSONDecodeError, TypeError):
                        pass  # 保持原值（可能是字符串）
                return result
            return None

    def get_history_list(self, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """
        获取历史记录列表

        Args:
            limit: 返回数量限制
            offset: 偏移量

        Returns:
            List: 历史记录列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT session_id, candidate_name, candidate_type, job_title,
                       company, match_score, match_level, model_used,
                       tokens_used, processing_time_ms, created_at
                FROM history
                ORDER BY created_at DESC
                LIMIT ? OFFSET ?
            ''', (limit, offset))
            return [dict(row) for row in cursor.fetchall()]

    def get_history_count(self) -> int:
        """获取历史记录总数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) as count FROM history')
            return cursor.fetchone()['count']

    def delete_history(self, session_id: str) -> bool:
        """删除指定历史记录"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM history WHERE session_id = ?', (session_id,))
            return cursor.rowcount > 0

    # ==================== 缓存管理 ====================

    def save_config(self, key: str, value: str) -> bool:
        """
        保存用户配置

        Args:
            key: 配置键
            value: 配置值

        Returns:
            bool: 是否保存成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO user_config (config_key, config_value, updated_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (key, value))
            return cursor.rowcount > 0

    def get_config(self, key: str, default: str = '') -> str:
        """
        获取用户配置

        Args:
            key: 配置键
            default: 默认值

        Returns:
            str: 配置值
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT config_value FROM user_config WHERE config_key = ?', (key,))
            row = cursor.fetchone()
            if row:
                return row['config_value'] or default
            return default

    def get_all_config(self) -> Dict[str, str]:
        """
        获取所有用户配置

        Returns:
            Dict[str, str]: 配置字典
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT config_key, config_value FROM user_config')
            return {row['config_key']: row['config_value'] or '' for row in cursor.fetchall()}

    def delete_config(self, key: str) -> bool:
        """
        删除用户配置

        Args:
            key: 配置键

        Returns:
            bool: 是否删除成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('DELETE FROM user_config WHERE config_key = ?', (key,))
            return cursor.rowcount > 0

    def save_analysis_cache(self, cache_key: str, resume_hash: str,
                            jd_hash: str, analysis_result: dict) -> bool:
        """保存分析结果缓存"""
        expires_at = datetime.now() + timedelta(days=config.HISTORY_RETENTION_DAYS)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO analysis_cache
                (cache_key, resume_hash, jd_hash, analysis_result, expires_at)
                VALUES (?, ?, ?, ?, ?)
            ''', (cache_key, resume_hash, jd_hash,
                  json.dumps(analysis_result, ensure_ascii=False), expires_at))
            return cursor.rowcount > 0

    def get_analysis_cache(self, cache_key: str) -> Optional[Dict[str, Any]]:
        """获取分析结果缓存"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT analysis_result FROM analysis_cache
                WHERE cache_key = ? AND expires_at > CURRENT_TIMESTAMP
            ''', (cache_key,))
            row = cursor.fetchone()
            if row:
                return json.loads(row['analysis_result'])
            return None

    # ==================== 维护操作 ====================

    def cleanup_expired(self) -> int:
        """清理过期数据"""
        deleted_count = 0
        with self._get_connection() as conn:
            cursor = conn.cursor()

            # 清理过期缓存
            cursor.execute('DELETE FROM analysis_cache WHERE expires_at < CURRENT_TIMESTAMP')
            deleted_count += cursor.rowcount

            # 清理过期历史记录
            retention_date = datetime.now() - timedelta(days=config.HISTORY_RETENTION_DAYS)
            cursor.execute('DELETE FROM history WHERE created_at < ?', (retention_date,))
            deleted_count += cursor.rowcount

            # 清理孤儿任务
            cursor.execute('''
                DELETE FROM tasks
                WHERE status = 'completed'
                AND created_at < ?
            ''', (retention_date,))
            deleted_count += cursor.rowcount

        if deleted_count > 0:
            logger.info(f"清理过期数据: {deleted_count} 条")

        return deleted_count

    # ==================== 模板管理 ====================

    def save_template(self, template_data: Dict[str, Any]) -> bool:
        """
        保存模板

        Args:
            template_data: 模板数据字典，包含 template_id, name, source, file_path 等字段

        Returns:
            bool: 是否保存成功
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO templates (
                    template_id, name, source, file_path, content_hash,
                    structure_confidence, sections, variables, description,
                    tags, preview_image, use_count, is_default
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                template_data.get('template_id'),
                template_data.get('name'),
                template_data.get('source'),
                template_data.get('file_path'),
                template_data.get('content_hash'),
                template_data.get('structure_confidence'),
                json.dumps(template_data.get('sections', []), ensure_ascii=False),
                json.dumps(template_data.get('variables', []), ensure_ascii=False),
                template_data.get('description', ''),
                json.dumps(template_data.get('tags', []), ensure_ascii=False),
                template_data.get('preview_image'),
                template_data.get('use_count', 0),
                1 if template_data.get('is_default') else 0
            ))
            return cursor.rowcount > 0

    def get_template(self, template_id: str) -> Optional[Dict[str, Any]]:
        """获取指定模板"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM templates WHERE template_id = ?', (template_id,))
            row = cursor.fetchone()
            if row:
                return self._row_to_template(row)
            return None

    def get_templates(self, source: str = None, include_builtin: bool = True) -> List[Dict[str, Any]]:
        """
        获取模板列表

        Args:
            source: 模板来源过滤 (builtin/uploaded/extracted)
            include_builtin: 是否包含内置模板

        Returns:
            List[Dict]: 模板列表
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            if source:
                cursor.execute(
                    'SELECT * FROM templates WHERE source = ? ORDER BY is_default DESC, use_count DESC, created_at DESC',
                    (source,)
                )
            elif not include_builtin:
                cursor.execute(
                    "SELECT * FROM templates WHERE source != 'builtin' ORDER BY is_default DESC, use_count DESC, created_at DESC"
                )
            else:
                cursor.execute(
                    'SELECT * FROM templates ORDER BY is_default DESC, use_count DESC, created_at DESC'
                )
            return [self._row_to_template(row) for row in cursor.fetchall()]

    def get_default_template(self) -> Optional[Dict[str, Any]]:
        """获取默认模板"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM templates WHERE is_default = 1 LIMIT 1')
            row = cursor.fetchone()
            if row:
                return self._row_to_template(row)
            return None

    def set_default_template(self, template_id: str) -> bool:
        """设置默认模板"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 先清除所有默认
            cursor.execute('UPDATE templates SET is_default = 0')
            # 设置新的默认
            cursor.execute('UPDATE templates SET is_default = 1 WHERE template_id = ?', (template_id,))
            return cursor.rowcount > 0

    def increment_template_use_count(self, template_id: str) -> bool:
        """增加模板使用次数"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                'UPDATE templates SET use_count = use_count + 1 WHERE template_id = ?',
                (template_id,)
            )
            return cursor.rowcount > 0

    def delete_template(self, template_id: str) -> bool:
        """删除模板"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            # 不允许删除内置模板
            cursor.execute(
                "DELETE FROM templates WHERE template_id = ? AND source != 'builtin'",
                (template_id,)
            )
            return cursor.rowcount > 0

    def get_template_by_hash(self, content_hash: str) -> Optional[Dict[str, Any]]:
        """根据内容哈希获取模板（用于去重）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM templates WHERE content_hash = ?', (content_hash,))
            row = cursor.fetchone()
            if row:
                return self._row_to_template(row)
            return None

    def _row_to_template(self, row) -> Dict[str, Any]:
        """将数据库行转换为模板字典"""
        result = dict(row)
        # 解析JSON字段
        if result.get('sections'):
            result['sections'] = json.loads(result['sections'])
        if result.get('variables'):
            result['variables'] = json.loads(result['variables'])
        if result.get('tags'):
            result['tags'] = json.loads(result['tags'])
        result['is_default'] = bool(result.get('is_default'))
        return result

    def get_stats(self) -> Dict[str, Any]:
        """获取数据库统计信息"""
        with self._get_connection() as conn:
            cursor = conn.cursor()

            stats = {}

            # 历史记录统计
            cursor.execute('SELECT COUNT(*) as count FROM history')
            stats['history_count'] = cursor.fetchone()['count']

            # 任务统计
            cursor.execute('''
                SELECT status, COUNT(*) as count
                FROM tasks
                GROUP BY status
            ''')
            stats['tasks_by_status'] = {row['status']: row['count'] for row in cursor.fetchall()}

            # 缓存统计
            cursor.execute('SELECT COUNT(*) as count FROM analysis_cache')
            stats['cache_count'] = cursor.fetchone()['count']

            # 平均匹配分数
            cursor.execute('SELECT AVG(match_score) as avg_score FROM history WHERE match_score > 0')
            result = cursor.fetchone()
            stats['avg_match_score'] = round(result['avg_score'] or 0, 1)

            # 总Token消耗
            cursor.execute('SELECT SUM(tokens_used) as total_tokens FROM history')
            stats['total_tokens'] = cursor.fetchone()['total_tokens'] or 0

            # 用户统计
            cursor.execute('SELECT COUNT(*) as count FROM users')
            stats['user_count'] = cursor.fetchone()['count']

            # 收入统计
            cursor.execute("SELECT COALESCE(SUM(amount), 0) as total FROM orders WHERE status = 'paid'")
            stats['total_revenue'] = cursor.fetchone()['total']

            return stats

    # ==================== 用户管理 ====================

    def create_user(self, phone: str = '', email: str = '', nickname: str = '') -> Optional[int]:
        """
        创建新用户（支持手机号或邮箱）

        Args:
            phone: 手机号（可选）
            email: 邮箱（可选）
            nickname: 昵称

        Returns:
            用户ID，失败返回None
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute('''
                    INSERT INTO users (phone, email, nickname, plan_type, quota_total, quota_used)
                    VALUES (?, ?, ?, 'free', 1, 0)
                ''', (phone or '', email or '', nickname))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                identifier = email or phone
                logger.warning(f"用户已存在: {identifier}")
                return None

    def get_user_by_phone(self, phone: str) -> Optional[Dict[str, Any]]:
        """根据手机号获取用户"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE phone = ? AND phone != ""', (phone,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_email(self, email: str) -> Optional[Dict[str, Any]]:
        """根据邮箱获取用户"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE email = ? AND email != ""', (email,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def get_user_by_id(self, user_id: int) -> Optional[Dict[str, Any]]:
        """根据ID获取用户"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_user_login(self, user_id: int):
        """更新用户最后登录时间"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE users SET last_login_at = CURRENT_TIMESTAMP WHERE id = ?
            ''', (user_id,))

    def get_user_quota(self, user_id: int) -> Dict[str, Any]:
        """
        获取用户配额信息

        Returns:
            dict: {plan_type, quota_total, quota_used, quota_remaining, plan_expires_at, is_expired}
        """
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE id = ?', (user_id,))
            row = cursor.fetchone()
            if not row:
                return {'plan_type': 'free', 'quota_total': 0, 'quota_used': 0, 'quota_remaining': 0}

            user = dict(row)
            plan_type = user['plan_type']
            quota_total = user['quota_total']
            quota_used = user['quota_used']

            # 月卡到期检查
            is_expired = False
            if plan_type == 'monthly' and user['plan_expires_at']:
                expires_at = datetime.fromisoformat(user['plan_expires_at'])
                if datetime.now() > expires_at:
                    is_expired = True
                    # 自动降级为免费用户
                    cursor.execute('''
                        UPDATE users SET plan_type = 'free', quota_total = 1,
                        quota_used = 0, plan_expires_at = NULL WHERE id = ?
                    ''', (user_id,))
                    plan_type = 'free'
                    quota_total = 1
                    quota_used = 0

            # 月卡用户配额为无限（但有日上限，在 quota 模块处理）
            if plan_type == 'monthly':
                return {
                    'plan_type': plan_type,
                    'quota_total': -1,  # -1 表示无限
                    'quota_used': quota_used,
                    'quota_remaining': -1,
                    'plan_expires_at': user['plan_expires_at'],
                    'is_expired': False
                }

            return {
                'plan_type': plan_type,
                'quota_total': quota_total,
                'quota_used': quota_used,
                'quota_remaining': max(0, quota_total - quota_used),
                'plan_expires_at': user.get('plan_expires_at'),
                'is_expired': is_expired
            }

    # ==================== 订单管理 ====================

    def create_order(self, order_no: str, user_id: int, plan_type: str,
                     plan_name: str, amount: float, provider: str = '') -> bool:
        """
        创建订单

        Args:
            order_no: 订单号
            user_id: 用户ID
            plan_type: 套餐类型 (pack5/monthly)
            plan_name: 套餐名称
            amount: 金额（元）
            provider: 支付渠道 ('alipay'/'wechat')

        Returns:
            bool
        """
        # 订单30分钟过期
        expires_at = datetime.now() + timedelta(minutes=30)
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO orders (order_no, user_id, plan_type, plan_name, amount, provider, expires_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (order_no, user_id, plan_type, plan_name, amount, provider, expires_at))
            return cursor.rowcount > 0

    def get_order(self, order_no: str) -> Optional[Dict[str, Any]]:
        """获取订单"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM orders WHERE order_no = ?', (order_no,))
            row = cursor.fetchone()
            return dict(row) if row else None

    def update_order_paid(self, order_no: str, transaction_id: str):
        """更新订单为已支付"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE orders SET status = 'paid', transaction_id = ?,
                wechat_transaction_id = ?, paid_at = CURRENT_TIMESTAMP
                WHERE order_no = ?
            ''', (transaction_id, transaction_id, order_no))

    def get_user_orders(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户订单列表"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM orders WHERE user_id = ?
                ORDER BY created_at DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]

    def get_pending_order(self, user_id: int, plan_type: str) -> Optional[Dict[str, Any]]:
        """获取用户未支付的待处理订单（30分钟内）"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT * FROM orders WHERE user_id = ? AND plan_type = ?
                AND status = 'pending' AND expires_at > CURRENT_TIMESTAMP
                ORDER BY created_at DESC LIMIT 1
            ''', (user_id, plan_type))
            row = cursor.fetchone()
            return dict(row) if row else None

    # ==================== 使用记录 ====================

    def record_usage(self, user_id: int, task_id: str = None,
                     session_id: str = None, tokens_used: int = 0) -> bool:
        """记录一次使用"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT INTO usage_records (user_id, task_id, session_id, tokens_used)
                VALUES (?, ?, ?, ?)
            ''', (user_id, task_id, session_id, tokens_used))
            # 更新用户已用配额
            cursor.execute('''
                UPDATE users SET quota_used = quota_used + 1 WHERE id = ?
            ''', (user_id,))
            return cursor.rowcount > 0

    def get_user_usage_count(self, user_id: int) -> int:
        """获取用户今日使用次数"""
        today = datetime.now().strftime('%Y-%m-%d')
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT COUNT(*) as count FROM usage_records
                WHERE user_id = ? AND DATE(created_at) = ?
            ''', (user_id, today))
            return cursor.fetchone()['count']

    def get_user_usage_history(self, user_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """获取用户使用历史"""
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT ur.*, h.candidate_name, h.job_title, h.company, h.match_score
                FROM usage_records ur
                LEFT JOIN history h ON ur.session_id = h.session_id
                WHERE ur.user_id = ?
                ORDER BY ur.created_at DESC LIMIT ?
            ''', (user_id, limit))
            return [dict(row) for row in cursor.fetchall()]


# 创建全局数据库实例
db = Database()
