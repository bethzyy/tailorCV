#!/usr/bin/env python
"""
多模型工具独立启动入口

多模型并行生成，结果对比。
访问: http://localhost:5002
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
        config.validate_multi()
    except ValueError as e:
        logger.error(f"配置验证失败: {e}")
        print(f"错误: {e}")
        print("请确保至少配置了一个模型提供者的 API 密钥")
        exit(1)

    # 创建并启动应用
    from apps.multi_app import create_app

    app = create_app()
    port = config.MULTI_APP_PORT

    # 显示可用提供者
    from core.multi_model_manager import MultiModelManager
    manager = MultiModelManager()
    providers = list(manager.available_providers.keys())

    print(f"\n{'='*50}")
    print(f"  tailorCV 多模型工具")
    print(f"  访问地址: http://localhost:{port}")
    print(f"  可用模型: {', '.join(providers)}")
    print(f"{'='*50}\n")

    app.run(host='0.0.0.0', port=port, debug=True)
