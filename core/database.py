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
            self._create_table_if_not_exists(cursor, 'tasks')

            # 简历定制历史表
            self._create_table_if_not_exists(cursor, 'history')

            # 分析结果缓存表
            self._create_table_if_not_exists(cursor, 'analysis_cache')

            # 用户配置表
            self._create_table_if_not_exists(cursor, 'user_config')

            # 模板表
            self._create_table_if_not_exists(cursor, 'templates')

            # 用户表
            self._create_table_if_not_exists(cursor, 'users')

            # 订单表
            self._create_table_if_not_exists(cursor, 'orders')

            # 使用记录表
            self._create_table_if_not_exists(cursor, 'usage_records')

            # 创建索引
            self._create_index_if_not_exists(cursor, 'history', 'created_at', 'DESC')
            self._create_index_if_not_exists(cursor, 'history', 'session_id')
            self._create_index_if_not_exists(cursor, 'tasks', 'status')
            self._create_index_if_not_exists(cursor, 'user_config', 'config_key')
            self._create_index_if_not_exists(cursor, 'templates', 'source')
            self._create_index_if_not_exists(cursor, 'templates', 'is_default')
            self._create_index_if_not_exists(cursor, 'users', 'phone')
            self._create_index_if_not_exists(cursor, 'users', 'email')
            self._create_index_if_not_exists(cursor, 'orders', 'user_id')
            self._create_index_if_not_exists(cursor, 'orders', 'status')
            self._create_index_if_not_exists(cursor, 'usage_records', 'user_id')

            logger.info(f"数据库初始化完成: {self.db_path}")

    def _create_table_if_not_exists(self, cursor, table_name):
        """创建表（如果不存在）"""
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {table_name} (
                {self._get_table_columns(table_name)}
            )
        ''')

    def _get_table_columns(self, table_name):
        """获取表列定义"""
        columns = {
            'tasks': '''
                task_id TEXT PRIMARY KEY,
                session_id TEXT,
                status TEXT NOT NULL DEFAULT 'pending',
                input_mode TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP,
                error_message TEXT,
                metadata TEXT
            ''',
            'history': '''
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
            ''',
            'analysis_cache': '''
                cache_key TEXT PRIMARY KEY,
                resume_hash TEXT,
                jd_hash TEXT,
                analysis_result TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                expires_at TIMESTAMP
            ''',
            'user_config': '''
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                config_key TEXT UNIQUE NOT NULL,
                config_value TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            ''',
            'templates': '''
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
            ''',
            'users': '''
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                phone TEXT DEFAULT '',
                email TEXT DEFAULT '',
                nickname TEXT DEFAULT '',
                plan_type TEXT DEFAULT 'free',
                quota_total INTEGER DEFAULT 3,
                quota_used INTEGER DEFAULT 0,
                plan_expires_at TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_login_at TIMESTAMP,
                is_active INTEGER DEFAULT 1,
                UNIQUE(email)
            ''',
            'orders': '''
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
            ''',
            'usage_records': '''
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                task_id TEXT,
                session_id TEXT,
                tokens_used INTEGER DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id)
            '''
        }
        return columns[table_name]

    def _create_index_if_not_exists(self, cursor, table_name, column_name, order):
        """创建索引（如果不存在）"""
        cursor.execute(f'''
            CREATE INDEX IF NOT EXISTS idx_{table_name}_{column_name}
            ON {table_name}({column_name} {order})
        ''')

    # ... (其他方法保持不变，仅展示修改部分)

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

    # ... (其他方法保持不变，仅展示修改部分)

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
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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

    # ... (其他方法保持不变，仅展示修改部分)

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

    # ... (其他方法保持不变，仅展示修改部分)

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
                    VALUES (?, ?, ?, 'free', 3, 0)
                ''', (phone or '', email or '', nickname))
                return cursor.lastrowid
            except sqlite3.IntegrityError:
                identifier = email or phone
                logger.warning(f"用户已存在: {identifier}")
                return None

    # ... (其他方法保持不变，仅展示修改部分)

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

    # ... (其他方法保持不变，仅展示修改部分)

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

    # ... (其他方法保持不变，仅展示修改部分)

# 创建全局数据库实例
db = Database()
