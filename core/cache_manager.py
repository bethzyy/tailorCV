"""
缓存管理器模块

基于 MD5 的缓存机制，避免重复处理相同的简历-JD组合。
参考 jobMatchTool 的缓存实现。
"""

import os
import json
import hashlib
import logging
import shutil
from typing import Dict, Any, Optional
from pathlib import Path
from datetime import datetime, timedelta

from .config import config

logger = logging.getLogger(__name__)


class CacheManager:
    """缓存管理器 - MD5 哈希缓存"""

    def __init__(self, cache_dir: Optional[str] = None):
        """
        初始化缓存管理器

        Args:
            cache_dir: 缓存目录（可选）
        """
        self.cache_dir = Path(cache_dir) if cache_dir else config.BASE_DIR / 'cache'
        self.cache_dir.mkdir(exist_ok=True)

        # 缓存过期时间（天）
        self.expiry_days = config.HISTORY_RETENTION_DAYS

        # 统计信息
        self.stats = {
            'hits': 0,
            'misses': 0,
            'evictions': 0
        }

    def _get_code_version_hash(self) -> str:
        """
        计算关键文件的版本指纹

        当 prompt 或核心处理逻辑变更时，版本指纹自动变化，
        导致缓存 key 变化，旧缓存自然失效。
        """
        version_files = [
            'prompts/rewrite_content_prompt.txt',
            'prompts/revise_content_prompt.txt',
            'core/expert_team.py',
            'core/cache_manager.py',
        ]
        h = hashlib.md5()
        for f in version_files:
            path = config.BASE_DIR / f
            if path.exists():
                h.update(path.read_bytes())
        return h.hexdigest()[:8]

    def get_cache_key(self, resume_content: str, jd_content: str) -> str:
        """
        生成缓存键（包含代码版本指纹）

        Args:
            resume_content: 简历内容
            jd_content: JD内容

        Returns:
            str: MD5 哈希键
        """
        combined = resume_content + jd_content + self._get_code_version_hash()
        return hashlib.md5(combined.encode('utf-8')).hexdigest()

    def get(self, resume_content: str, jd_content: str) -> Optional[Dict[str, Any]]:
        """
        获取缓存结果

        Args:
            resume_content: 简历内容
            jd_content: JD内容

        Returns:
            Optional[Dict]: 缓存结果（如果存在且未过期）
        """
        cache_key = self.get_cache_key(resume_content, jd_content)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if not cache_file.exists():
            self.stats['misses'] += 1
            return None

        try:
            with open(cache_file, 'r', encoding='utf-8') as f:
                cached = json.load(f)

            # 检查是否过期
            cached_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
            if datetime.now() - cached_time > timedelta(days=self.expiry_days):
                # 过期，删除缓存
                cache_file.unlink()
                self.stats['evictions'] += 1
                self.stats['misses'] += 1
                logger.info(f"缓存过期: {cache_key}")
                return None

            self.stats['hits'] += 1
            logger.info(f"缓存命中: {cache_key}")
            return cached.get('result')

        except Exception as e:
            logger.warning(f"缓存读取失败: {e}")
            self.stats['misses'] += 1
            return None

    def set(self, resume_content: str, jd_content: str,
            result: Dict[str, Any]) -> None:
        """
        设置缓存

        Args:
            resume_content: 简历内容
            jd_content: JD内容
            result: 缓存结果
        """
        cache_key = self.get_cache_key(resume_content, jd_content)
        cache_file = self.cache_dir / f"{cache_key}.json"

        try:
            cached = {
                'cache_key': cache_key,
                'timestamp': datetime.now().isoformat(),
                'result': result
            }

            with open(cache_file, 'w', encoding='utf-8') as f:
                json.dump(cached, f, ensure_ascii=False, indent=2)

            logger.info(f"缓存已保存: {cache_key}")

        except Exception as e:
            logger.warning(f"缓存保存失败: {e}")

    def delete(self, resume_content: str, jd_content: str) -> bool:
        """
        删除缓存

        Args:
            resume_content: 简历内容
            jd_content: JD内容

        Returns:
            bool: 是否成功删除
        """
        cache_key = self.get_cache_key(resume_content, jd_content)
        cache_file = self.cache_dir / f"{cache_key}.json"

        if cache_file.exists():
            cache_file.unlink()
            logger.info(f"缓存已删除: {cache_key}")
            return True

        return False

    def clear_expired(self) -> int:
        """
        清理过期缓存

        Returns:
            int: 清理的缓存数量
        """
        cleared = 0
        expiry_threshold = datetime.now() - timedelta(days=self.expiry_days)

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                with open(cache_file, 'r', encoding='utf-8') as f:
                    cached = json.load(f)

                cached_time = datetime.fromisoformat(cached.get('timestamp', '2000-01-01'))
                if cached_time < expiry_threshold:
                    cache_file.unlink()
                    cleared += 1
                    self.stats['evictions'] += 1

            except Exception as e:
                logger.warning(f"清理缓存失败 {cache_file}: {e}")

        logger.info(f"清理过期缓存: {cleared} 个")
        return cleared

    def clear_all(self) -> int:
        """
        清理所有缓存

        Returns:
            int: 清理的缓存数量
        """
        cleared = 0

        for cache_file in self.cache_dir.glob("*.json"):
            try:
                cache_file.unlink()
                cleared += 1
            except Exception as e:
                logger.warning(f"删除缓存失败 {cache_file}: {e}")

        logger.info(f"清理所有缓存: {cleared} 个")
        return cleared

    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            Dict: 统计信息
        """
        total_requests = self.stats['hits'] + self.stats['misses']
        hit_rate = self.stats['hits'] / total_requests if total_requests > 0 else 0

        # 计算缓存大小
        cache_size = 0
        cache_count = 0
        for cache_file in self.cache_dir.glob("*.json"):
            cache_size += cache_file.stat().st_size
            cache_count += 1

        return {
            'hits': self.stats['hits'],
            'misses': self.stats['misses'],
            'evictions': self.stats['evictions'],
            'hit_rate': round(hit_rate, 2),
            'cache_count': cache_count,
            'cache_size_mb': round(cache_size / (1024 * 1024), 2)
        }
