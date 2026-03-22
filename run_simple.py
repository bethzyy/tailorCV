#!/usr/bin/env python
"""
简版工具独立启动入口

单模型（智谱）快速生成简历定制工具。
访问: http://localhost:5001
"""

import logging
from pathlib import Path

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == '__main__':
    from core.config import config

    # 验证配置
    try:
        config.validate()
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        print(f"错误: {e}")
        print("请确保已设置 ZHIPU_API_KEY 环境变量或 .env 文件")
        exit(1)

    # 创建并启动应用
    from apps.simple_app import create_app

    app = create_app()
    port = config.SIMPLE_APP_PORT

    print(f"\n{'='*50}")
    print(f"  tailorCV 简版工具")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  模型: 智谱AI (GLM-5)")
    print(f"{'='*50}\n")

    # use_reloader=False: 禁用自动重载，避免长时间AI请求被文件变化中断导致 ERR_CONNECTION_RESET
    # 注意：修改代码后需手动重启，或使用 restart.bat 脚本
    app.run(host='0.0.0.0', port=port, debug=True, use_reloader=False)
