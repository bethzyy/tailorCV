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
                data.get('tailored_resume', ''),
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

            return stats


# 创建全局数据库实例
db = Database()
