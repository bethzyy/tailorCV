"""
模型提供者模块

提供统一的模型调用抽象，支持多种 AI 模型提供商。
"""

from .base_provider import BaseModelProvider, ModelResponse
from .zhipu_provider import ZhipuProvider
from .alibaba_provider import AlibabaProvider
from .antigravity_provider import AntiGravityProvider

__all__ = [
    'BaseModelProvider',
    'ModelResponse',
    'ZhipuProvider',
    'AlibabaProvider',
    'AntiGravityProvider',
]

# 延迟导入以避免循环导入
def get_provider(provider_name: str, config: dict) -> BaseModelProvider:
    """
    工厂函数：根据配置获取对应的模型提供者实例
    
    Args:
        provider_name: 提供者名称
        config: 配置字典
        
    Returns:
        BaseModelProvider: 模型提供者实例
    """
    providers = {
        'zhipu': ZhipuProvider,
        'alibaba': AlibabaProvider,
        'antigravity': AntiGravityProvider,
    }
    
    provider_class = providers.get(provider_name.lower())
    if not provider_class:
        raise ValueError(f"Unknown provider: {provider_name}")
    
    return provider_class(config)
