"""
测试模板管理功能

运行: python scripts/test_template_manager.py
"""

import sys
import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 添加项目根目录到路径
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.template_manager import TemplateManager
from core.auth import auth
from core.database import db


def test_template_manager():
    """测试模板管理器"""
    logger.info("=" * 50)
    logger.info("测试模板管理功能")
    logger.info("=" * 50)

    manager = TemplateManager()

    # 1. 测试获取模板列表
    logger.info("\n1. 获取模板列表...")
    templates = manager.get_templates()
    logger.info(f"   找到 {len(templates)} 个模板")
    for t in templates[:3]:
        logger.info(f"   - {t['name']} ({t['template_id']})")

    # 2. 测试获取默认模板
    logger.info("\n2. 获取默认模板...")
    default = manager.get_default_template()
    if default:
        logger.info(f"   默认模板: {default['name']}")
    else:
        logger.info("   没有默认模板")

    # 3. 测试统计信息
    logger.info("\n3. 模板统计...")
    stats = manager.get_stats()
    logger.info(f"   总数: {stats['total_count']}")
    logger.info(f"   内置: {stats['builtin_count']}")
    logger.info(f"   上传: {stats['uploaded_count']}")
    logger.info(f"   提取: {stats['extracted_count']}")

    # 4. 测试推荐功能
    logger.info("\n4. 模板推荐...")
    jd_samples = [
        "招聘高级Java开发工程师，5年以上经验",
        "财务总监，负责公司财务管理",
        "UI设计师，有创意能力",
    ]
    for jd in jd_samples:
        recommendations = manager.recommend_template(jd_content=jd)
        if recommendations:
            top = recommendations[0]
            logger.info(f"   JD: {jd[:20]}...")
            logger.info(f"   推荐: {top['template']['name']} (分数: {top['score']})")

    # 5. 测试兼容性检查
    logger.info("\n5. 兼容性检查...")
    sample_resume = {
        'basic_info': {'name': '张三'},
        'work_experience': [{'company': 'ABC'}],
        'education': [{'school': '清华大学'}],
    }
    if templates:
        template_id = templates[0]['template_id']
        is_compatible, missing = manager.check_compatibility(template_id, sample_resume)
        logger.info(f"   模板: {templates[0]['name']}")
        logger.info(f"   兼容: {is_compatible}")
        logger.info(f"   缺失: {missing}")

    logger.info("\n" + "=" * 50)
    logger.info("测试完成!")
    logger.info("=" * 50)


if __name__ == '__main__':
    test_template_manager()
