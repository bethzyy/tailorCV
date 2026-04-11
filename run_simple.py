#!/usr/bin/env python
"""
简版工具独立启动入口

单模型（智谱）快速生成简历定制工具。
访问: http://localhost:5001

启动模式（通过环境变量 FLASK_ENV 设置）：
  - 开发模式: FLASK_ENV=development  (自动重载、详细错误、全量清缓存)
  - 应用模式: FLASK_ENV=production 或不设置 (稳定运行、清过期缓存)
"""

import os
import time
import logging
import shutil
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

from core.auth import authenticate_user  # 修复循环导入问题
from core.cache_manager import CacheManager  # 修复循环导入问题
from core.config import config  # 修复循环导入问题
from core.database import db  # 修复循环导入问题
from apps.simple_app import create_app  # 修复循环导入问题

def clear_pycache(project_root: Path) -> int:
    """清理所有 __pycache__ 目录"""
    count = 0
    try:
        for pycache in project_root.rglob("__pycache__"):
            try:
                shutil.rmtree(pycache)
                count += 1
            except Exception:
                pass
    except FileNotFoundError:
        pass
    except Exception as e:
        logger.warning(f"清理 __pycache__ 时出错: {e}")
    return count


def clear_business_cache(project_root: Path) -> int:
    """清理 cache/ 目录下的业务缓存文件"""
    cache_dir = project_root / 'cache'
    count = 0
    if not cache_dir.exists():
        return count
    for cache_file in cache_dir.glob("*.json"):
        try:
            cache_file.unlink()
            count += 1
        except Exception as e:
            logger.warning(f"删除缓存文件失败 {cache_file}: {e}")
    return count


def clear_old_storage_files(project_root: Path, retention_days: int = 30) -> int:
    """清理 storage/uploads/ 和 storage/tailored/ 下超过 retention_days 天的目录"""
    threshold = time.time() - retention_days * 86400
    count = 0

    for storage_subdir in ['storage/uploads', 'storage/tailored']:
        storage_dir = project_root / storage_subdir
        if not storage_dir.exists():
            continue
        for user_dir in storage_dir.iterdir():
            if not user_dir.is_dir():
                continue
            for session_dir in user_dir.iterdir():
                if not session_dir.is_dir():
                    continue
                try:
                    if session_dir.stat().st_mtime < threshold:
                        shutil.rmtree(session_dir)
                        count += 1
                except Exception as e:
                    logger.warning(f"清理 storage 失败 {session_dir}: {e}")

    return count


def clear_all_caches(is_development: bool):
    """统一清理所有缓存

    Args:
        is_development: 是否开发模式（开发模式清理更彻底）
    """
    project_root = Path(__file__).parent
    logger.info("清理缓存...")

    # 1. 清理 __pycache__（所有模式都清理）
    pycache_count = clear_pycache(project_root)
    if pycache_count > 0:
        logger.info(f"  __pycache__: 已清理 {pycache_count} 个目录")

    # 2. 清理业务缓存 cache/
    if is_development:
        biz_count = clear_business_cache(project_root)
        if biz_count > 0:
            logger.info(f"  cache/: 已清理 {biz_count} 个文件（全量）")
    else:
        try:
            cm = CacheManager()
            biz_count = cm.clear_all()
            if biz_count > 0:
                logger.info(f"  cache/: 已清理 {biz_count} 个缓存文件（全量）")
        except Exception as e:
            logger.warning(f"  cache/: 清理失败 {e}")

    # 3. 清理过期 storage 文件（所有模式都清理）
    try:
        retention_days = config.HISTORY_RETENTION_DAYS
    except Exception:
        retention_days = 30

    storage_count = clear_old_storage_files(project_root, retention_days)
    if storage_count > 0:
        logger.info(f"  storage/: 已清理 {storage_count} 个过期目录（保留 {retention_days} 天）")

    # 4. 清理数据库过期数据（所有模式都清理）
    try:
        db_count = db.cleanup_expired()
        if db_count > 0:
            logger.info(f"  数据库: 已清理 {db_count} 条过期记录")
    except Exception as e:
        logger.warning(f"  数据库: 清理失败 {e}")

    logger.info("缓存清理完成")


if __name__ == '__main__':
    # 判断运行模式
    flask_env = os.getenv('FLASK_ENV', 'production').lower()
    is_development = flask_env == 'development'

    # 所有模式：启动时统一清理缓存
    clear_all_caches(is_development)

    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        print(f"错误: {e}")
        print("请确保已设置 ZHIPU_API_KEY 环境变量或 .env 文件")
        exit(1)

    # 创建并启动应用
    app = create_app()
    port = config.SIMPLE_APP_PORT

    mode_label = "开发模式" if is_development else "应用模式"
    print(f"\n{'='*50}")
    print(f"  tailorCV 简版工具 [{mode_label}]")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  模型: 智谱AI (GLM-5)")
    if is_development:
        print(f"  特性: 自动重载 + 详细错误 + 全量清缓存")
    else:
        print(f"  特性: 稳定运行 + 过期缓存清理")
    print(f"{'='*50}\n")

    # 开发模式：启用自动重载；应用模式：禁用自动重载
    app.run(
        host='0.0.0.0',
        port=port,
        debug=is_development,
        use_reloader=False  # Windows 上 watchdog 会误检系统文件导致频繁重启
    )
