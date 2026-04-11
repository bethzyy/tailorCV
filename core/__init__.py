"""
tailorCV 核心模块

包含简历解析、AI专家团队、依据追踪等核心功能。
"""

from .config import config, Config

# 提供者
from .providers import (
    BaseModelProvider,
    ModelResponse,
    ZhipuProvider,
    AlibabaProvider,
)

# 模型管理
from .model_manager import ModelManager
from .multi_model_manager import MultiModelManager, MultiModelResult

# AI 处理
from .expert_team import ExpertTeam, AnalysisResult, GenerationResult
from .multi_expert_team import MultiExpertTeam, MultiModelAnalysisResult, MultiModelGenerationResult

__all__ = [
    'config',
    'Config',
    # 提供者
    'BaseModelProvider',
    'ModelResponse',
    'ZhipuProvider',
    'AlibabaProvider',
    # 模型管理
    'ModelManager',
    'MultiModelManager',
    'MultiModelResult',
    # AI 处理
    'ExpertTeam',
    'AnalysisResult',
    'GenerationResult',
    'MultiExpertTeam',
    'MultiModelAnalysisResult',
    'MultiModelGenerationResult',
]
