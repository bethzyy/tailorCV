"""
模型提供者抽象基类

定义所有模型提供者必须实现的接口。
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, Optional


@dataclass
class ModelResponse:
    """模型响应数据结构"""
    success: bool
    content: str
    model_id: str
    model_name: str
    tokens_used: int = 0
    latency_ms: int = 0
    error_message: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            'success': self.success,
            'content': self.content,
            'model_id': self.model_id,
            'model_name': self.model_name,
            'tokens_used': self.tokens_used,
            'latency_ms': self.latency_ms,
            'error_message': self.error_message
        }


class BaseModelProvider(ABC):
    """模型提供者抽象基类"""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """提供者唯一标识"""
        pass

    @property
    @abstractmethod
    def provider_name(self) -> str:
        """提供者显示名称"""
        pass

    @property
    @abstractmethod
    def available_models(self) -> Dict[str, str]:
        """
        可用模型列表

        Returns:
            Dict[str, str]: 模型ID -> 模型名称的映射
        """
        pass

    @abstractmethod
    def call(self, prompt: str, model_id: str = None, **kwargs) -> ModelResponse:
        """
        调用模型

        Args:
            prompt: 输入提示词
            model_id: 指定模型ID（可选，使用默认模型）
            **kwargs: 额外参数
                - max_tokens: 最大输出token数
                - temperature: 温度参数
                - max_retries: 最大重试次数

        Returns:
            ModelResponse: 模型响应
        """
        pass

    @abstractmethod
    def is_available(self) -> bool:
        """
        检查提供者是否可用

        Returns:
            bool: 是否可用（API密钥已配置等）
        """
        pass

    def get_default_model(self) -> str:
        """获取默认模型ID"""
        models = self.available_models
        if models:
            return list(models.keys())[0]
        return ""

    def get_model_name(self, model_id: str) -> str:
        """获取模型显示名称"""
        return self.available_models.get(model_id, model_id)
