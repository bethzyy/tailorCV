"""
tailorCV 配置管理模块

负责加载和管理应用配置，包括 API 密钥、模型配置等。
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 加载环境变量
load_dotenv()


class Config:
    """应用配置类"""

    # 项目根目录
    BASE_DIR = Path(__file__).resolve().parent.parent

    # API 配置
    ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY', '')

    # 模型配置
    PRIMARY_MODEL = os.getenv('PRIMARY_MODEL', 'glm-4.6')
    FALLBACK_MODEL = os.getenv('FALLBACK_MODEL', 'glm-4-flash')

    # 任务-模型映射
    TASK_MODEL_MAPPING = {
        'analyze': 'glm-4.6',      # 分析任务
        'generate': 'glm-4.6',     # 生成任务
        'validate': 'glm-4-flash'  # 验证任务（低成本）
    }

    # 处理配置
    MAX_PROCESSING_TIME = int(os.getenv('MAX_PROCESSING_TIME', 60))
    EVIDENCE_THRESHOLD = float(os.getenv('EVIDENCE_THRESHOLD', 0.7))

    # 存储配置
    DATABASE_PATH = os.getenv('DATABASE_PATH', str(BASE_DIR / 'storage' / 'tailorcv.db'))
    HISTORY_RETENTION_DAYS = int(os.getenv('HISTORY_RETENTION_DAYS', 30))

    # 验证配置
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.6))
    CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', 0.7))
    EVIDENCE_COVERAGE_TARGET = float(os.getenv('EVIDENCE_COVERAGE_TARGET', 0.90))

    # 置信度计算权重配置（可配置化）
    # 适用于有工作经验者
    CONFIDENCE_WEIGHTS_EXPERIENCED = {
        'basic_info': 0.20,        # 基本信息
        'education': 0.15,         # 教育背景
        'work_experience': 0.45,   # 工作经历
        'projects': 0.10,          # 项目经历
        'skills': 0.10,            # 技能
        'awards_bonus': 0.05,      # 奖项/证书额外加分
    }

    # 适用于无工作经验者（应届生/转行者）
    CONFIDENCE_WEIGHTS_FRESH = {
        'basic_info': 0.20,        # 基本信息
        'education': 0.40,         # 教育背景（权重更高）
        'work_experience': 0.00,   # 工作经历（可能没有）
        'projects': 0.30,          # 项目经历（权重更高）
        'skills': 0.10,            # 技能
        'awards_bonus': 0.05,      # 奖项/证书额外加分
    }

    # 可疑关键词模式（中英文）
    SUSPICIOUS_PATTERNS = [
        # 中文模式
        r'精通',
        r'专家',
        r'权威',
        r'顶级',
        r'国家级',
        r'世界级',
        r'首创',
        r'独家',
        r'业界领先',
        r'全球首创',
        r'国内首创',
        r'第一人',
        r'资深专家',
        r'顶尖',
        r'无可匹敌',
        r'完美无缺',
        # 英文模式
        r'\bexpert\b',
        r'\bmastery\b',
        r'\bworld.?class\b',
        r'\bindustry.?leading\b',
        r'\btop.?tier\b',
        r'\bunparalleled\b',
        r'\brevolutionary\b',
        r'\bpioneering\b',
    ]

    # AI验证Prompt配置
    AI_VALIDATION_CONFIG = {
        'max_context_length': 2000,    # 原版简历上下文最大长度
        'max_content_length': 500,     # 待验证内容最大长度
        'temperature': 0.1,            # 低温度确保稳定输出
        'max_tokens': 512,             # 验证响应最大token数
    }

    # Flask 配置
    SECRET_KEY = os.getenv('SECRET_KEY', 'tailorcv-secret-key-change-in-production')
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB 最大文件大小

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否有效"""
        if not cls.ZHIPU_API_KEY:
            raise ValueError("ZHIPU_API_KEY 环境变量未设置")
        return True

    @classmethod
    def get_model_for_task(cls, task_type: str) -> str:
        """获取指定任务类型的模型"""
        return cls.TASK_MODEL_MAPPING.get(task_type, cls.PRIMARY_MODEL)

    @classmethod
    def get_confidence_weights(cls, has_work_experience: bool = True) -> dict:
        """获取置信度计算权重"""
        if has_work_experience:
            return cls.CONFIDENCE_WEIGHTS_EXPERIENCED.copy()
        else:
            return cls.CONFIDENCE_WEIGHTS_FRESH.copy()

    @classmethod
    def get_suspicious_patterns(cls) -> list:
        """获取可疑关键词模式列表"""
        return cls.SUSPICIOUS_PATTERNS.copy()

    @classmethod
    def get_ai_validation_config(cls) -> dict:
        """获取AI验证配置"""
        return cls.AI_VALIDATION_CONFIG.copy()


# 创建全局配置实例
config = Config()
