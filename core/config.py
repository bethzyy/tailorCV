"""
tailorCV 配置管理模块

负责加载和管理应用配置，包括 API 密钥、模型配置等。
支持多模型配置。
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

    # ==================== 智谱AI 配置 ====================
    ZHIPU_API_KEY = os.getenv('ZHIPU_API_KEY', '')

    # ==================== 阿里云 配置 ====================
    ALIBABA_API_KEY = os.getenv('ALIBABA_API_KEY', '')

    # ==================== 模型配置 ====================
    # 智谱模型（使用 Anthropic 兼容端点）
    PRIMARY_MODEL = os.getenv('PRIMARY_MODEL', 'glm-5')
    FALLBACK_MODEL = os.getenv('FALLBACK_MODEL', 'glm-4.6')

    # 阿里云模型
    ALIBABA_PRIMARY_MODEL = os.getenv('ALIBABA_PRIMARY_MODEL', 'qwen3.5-plus')

    # 任务-模型映射（智谱）
    TASK_MODEL_MAPPING = {
        'analyze': 'glm-5',          # 分析任务
        'generate': 'glm-5',         # 生成任务
        'validate': 'glm-4-flash'    # 验证任务（低成本）
    }

    # 任务-模型映射（阿里云）
    ALIBABA_TASK_MODEL_MAPPING = {
        'analyze': 'qwen3.5-plus',
        'generate': 'qwen3-max-2026-01-23',
        'validate': 'qwen3.5-plus'
    }

    # ==================== 处理配置 ====================
    MAX_PROCESSING_TIME = int(os.getenv('MAX_PROCESSING_TIME', 60))
    EVIDENCE_THRESHOLD = float(os.getenv('EVIDENCE_THRESHOLD', 0.7))

    # ==================== 存储配置 ====================
    DATABASE_PATH = os.getenv('DATABASE_PATH', str(BASE_DIR / 'storage' / 'tailorcv.db'))
    HISTORY_RETENTION_DAYS = int(os.getenv('HISTORY_RETENTION_DAYS', 30))

    # ==================== 验证配置 ====================
    SIMILARITY_THRESHOLD = float(os.getenv('SIMILARITY_THRESHOLD', 0.6))
    CONFIDENCE_THRESHOLD = float(os.getenv('CONFIDENCE_THRESHOLD', 0.7))
    EVIDENCE_COVERAGE_TARGET = float(os.getenv('EVIDENCE_COVERAGE_TARGET', 0.90))

    # ==================== 置信度计算权重配置 ====================
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

    # ==================== 可疑关键词模式 ====================
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

    # ==================== AI验证Prompt配置 ====================
    AI_VALIDATION_CONFIG = {
        'max_context_length': 2000,    # 原版简历上下文最大长度
        'max_content_length': 500,     # 待验证内容最大长度
        'temperature': 0.1,            # 低温度确保稳定输出
        'max_tokens': 512,             # 验证响应最大token数
    }

    # ==================== Flask 配置 ====================
    SECRET_KEY = os.getenv('SECRET_KEY', '')  # 生产环境必须通过环境变量设置
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB 最大文件大小

    # ==================== 认证配置 ====================
    # 邮箱验证码
    EMAIL_SMTP_HOST = os.getenv('EMAIL_SMTP_HOST', 'smtp.qq.com')  # QQ邮箱SMTP
    EMAIL_SMTP_PORT = int(os.getenv('EMAIL_SMTP_PORT', 465))
    EMAIL_SMTP_USER = os.getenv('EMAIL_SMTP_USER', '')  # 发件邮箱
    EMAIL_SMTP_PASSWORD = os.getenv('EMAIL_SMTP_PASSWORD', '')  # SMTP授权码（不是邮箱密码）
    EMAIL_FROM_NAME = os.getenv('EMAIL_FROM_NAME', 'tailorCV 智能简历')
    CODE_EXPIRE_SECONDS = int(os.getenv('CODE_EXPIRE_SECONDS', 300))  # 验证码5分钟过期

    # 登录有效期选项（秒）
    LOGIN_DURATION_OPTIONS = {
        'session': {'label': '本次有效', 'seconds': 0},        # 浏览器关闭即失效
        '7d': {'label': '7天内免登录', 'seconds': 7 * 86400},
        '30d': {'label': '30天内免登录', 'seconds': 30 * 86400},
        'forever': {'label': '永久登录', 'seconds': 365 * 86400},  # 1年cookie
    }

    # ==================== 支付配置 ====================
    # 默认支付方式（优先使用）
    DEFAULT_PAYMENT_PROVIDER = os.getenv('DEFAULT_PAYMENT_PROVIDER', 'alipay')

    # 支付宝当面付
    ALIPAY_APP_ID = os.getenv('ALIPAY_APP_ID', '')
    ALIPAY_PRIVATE_KEY_PATH = os.getenv('ALIPAY_PRIVATE_KEY_PATH', '')
    ALIPAY_PUBLIC_KEY_PATH = os.getenv('ALIPAY_PUBLIC_KEY_PATH', '')
    ALIPAY_NOTIFY_URL = os.getenv('ALIPAY_NOTIFY_URL', '')
    ALIPAY_SANDBOX = os.getenv('ALIPAY_SANDBOX', 'true').lower() == 'true'

    # 微信支付
    WECHAT_APP_ID = os.getenv('WECHAT_APP_ID', '')
    WECHAT_MCH_ID = os.getenv('WECHAT_MCH_ID', '')
    WECHAT_API_KEY_V3 = os.getenv('WECHAT_API_KEY_V3', '')
    WECHAT_CERT_PATH = os.getenv('WECHAT_CERT_PATH', '')
    WECHAT_KEY_PATH = os.getenv('WECHAT_KEY_PATH', '')
    WECHAT_NOTIFY_URL = os.getenv('WECHAT_NOTIFY_URL', '')
    WECHAT_SANDBOX = os.getenv('WECHAT_SANDBOX', 'true').lower() == 'true'

    # ==================== 套餐配置 ====================
    PLANS = {
        'free': {'name': '免费体验', 'price': 0, 'quota': 3, 'daily_limit': 3},
        'pack5': {'name': '按次包', 'price': 9.9, 'quota': 5, 'daily_limit': 5},
        'monthly': {'name': '月卡', 'price': 29.9, 'quota': -1, 'daily_limit': 10},  # -1 = 无限
        'quarterly': {'name': '季卡', 'price': 59.9, 'quota': -1, 'daily_limit': 20},
    }

    # ==================== 开发者配置 ====================
    # 开发者邮箱列表（不受配额限制，用于开发测试）
    DEV_EMAILS = [e.strip() for e in os.getenv('DEV_EMAILS', '').split(',') if e.strip()]

    # ==================== 限流配置 ====================
    RATE_LIMIT_DEFAULT = os.getenv('RATE_LIMIT_DEFAULT', '30 per hour')
    RATE_LIMIT_ANON = os.getenv('RATE_LIMIT_ANON', '10 per hour')

    # ==================== AntiGravity 代理配置 ====================
    ANTIGRAVITY_BASE_URL = os.getenv('ANTIGRAVITY_BASE_URL', 'http://127.0.0.1:8045/v1')

    # ==================== Writer-Reviewer 闭环配置 ====================
    WRITER_REVIEWER_ENABLED = os.getenv('WRITER_REVIEWER_ENABLED', 'false').lower() == 'true'
    WRITER_REVIEWER_MAX_ITERATIONS = int(os.getenv('WRITER_REVIEWER_MAX_ITERATIONS', '3'))
    WRITER_REVIEWER_SCORE_THRESHOLD = float(os.getenv('WRITER_REVIEWER_SCORE_THRESHOLD', '85.0'))
    WRITER_REVIEWER_MIN_DIFF_THRESHOLD = float(os.getenv('WRITER_REVIEWER_MIN_DIFF_THRESHOLD', '0.05'))
    WRITER_REVIEWER_REVIEWER_MODELS = os.getenv('WRITER_REVIEWER_REVIEWER_MODELS', 'qwen3.5-plus')

    # ==================== AI 模板校验配置 ====================
    TEMPLATE_AI_VALIDATE_ENABLED = os.getenv('TEMPLATE_AI_VALIDATE_ENABLED', 'true').lower() == 'true'
    TEMPLATE_AI_VALIDATE_MODEL = os.getenv('TEMPLATE_AI_VALIDATE_MODEL', 'glm-4-flash')

    # ==================== 端口配置 ====================
    SIMPLE_APP_PORT = int(os.getenv('SIMPLE_APP_PORT', 6003))
    MULTI_APP_PORT = int(os.getenv('MULTI_APP_PORT', 5002))
    HUB_APP_PORT = int(os.getenv('HUB_APP_PORT', 5000))

    @classmethod
    def validate(cls) -> bool:
        """验证配置是否有效"""
        if not cls.ZHIPU_API_KEY:
            raise ValueError("ZHIPU_API_KEY 环境变量未设置")
        return True

    @classmethod
    def validate_multi(cls) -> bool:
        """验证多模型配置是否有效"""
        if not cls.ZHIPU_API_KEY and not cls.ALIBABA_API_KEY:
            raise ValueError("至少需要配置一个模型提供者的 API 密钥")
        return True

    @classmethod
    def get_model_for_task(cls, task_type: str, provider: str = 'zhipu') -> str:
        """获取指定任务类型的模型"""
        if provider == 'alibaba':
            return cls.ALIBABA_TASK_MODEL_MAPPING.get(task_type, cls.ALIBABA_PRIMARY_MODEL)
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

    @classmethod
    def get_available_providers(cls) -> list:
        """获取可用的提供者列表"""
        providers = []
        if cls.ZHIPU_API_KEY:
            providers.append('zhipu')
        if cls.ALIBABA_API_KEY or Path(r'C:\D\CAIE_tool\LLM_Configs\ali\apikey.txt').exists():
            providers.append('alibaba')
        providers.append('antigravity')  # 本地代理，始终列入（运行时检测在线状态）
        return providers


# 创建全局配置实例
config = Config()
