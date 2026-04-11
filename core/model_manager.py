"""
单模型管理器模块

负责管理单个模型提供者的调用，支持主备切换和重试机制。
用于简版工具。
"""

import logging
from typing import Dict, Any, List, Optional

from .providers.base_provider import BaseModelProvider, ModelResponse
from .providers.zhipu_provider import ZhipuProvider
from .config import config

logger = logging.getLogger(__name__)


class ModelManager:
    """单模型管理器 - 使用提供者模式"""

    def __init__(self, provider: BaseModelProvider = None):
        """
        初始化模型管理器

        Args:
            provider: 模型提供者（可选，默认使用智谱）
        """
        if provider is None:
            # 默认使用智谱提供者
            provider = ZhipuProvider()

        self.provider = provider
        self.primary_model = config.PRIMARY_MODEL
        self.fallback_models = self._parse_fallback_models()

        # 调用统计
        self.stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'fallback_used': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }

    def _parse_fallback_models(self) -> List[str]:
        """解析备用模型列表"""
        fallback = config.FALLBACK_MODEL
        if isinstance(fallback, str):
            return [m.strip() for m in fallback.split(',') if m.strip()]
        return [fallback] if fallback else []

    @property
    def current_model(self) -> str:
        """获取当前使用的模型"""
        return self.primary_model

    @property
    def current_provider(self) -> str:
        """获取当前提供者ID"""
        return self.provider.provider_id

    def call(self, prompt: str, task_type: str = 'analyze',
             max_tokens: int = 4096, temperature: float = 0.7,
             max_retries: int = 3) -> ModelResponse:
        """
        调用 AI 模型（带主备切换和重试）

        Args:
            prompt: 提示词
            task_type: 任务类型 (analyze/generate/validate)
            max_tokens: 最大输出 token 数
            temperature: 温度参数
            max_retries: 最大重试次数

        Returns:
            ModelResponse: 模型响应
        """
        self.stats['total_calls'] += 1

        # 获取任务对应的模型
        preferred_model = config.get_model_for_task(task_type)

        # 模型列表：首选 -> 备选
        models_to_try = [preferred_model] + self.fallback_models
        # 去重并创建新列表副本
        models_to_try = list(dict.fromkeys(models_to_try))[:]

        last_error = None

        for model in models_to_try:
            # 检查模型是否在提供者的可用模型中
            if model not in self.provider.available_models:
                continue

            response = self.provider.call(
                prompt=prompt,
                model_id=model,
                max_tokens=max_tokens,
                temperature=temperature,
                max_retries=max_retries
            )

            if response.success:
                # 更新统计
                self.stats['success_calls'] += 1
                self.stats['total_tokens'] += response.tokens_used
                self.stats['total_latency_ms'] += response.latency_ms

                if model != preferred_model:
                    self.stats['fallback_used'] += 1
                    logger.info(f"使用备用模型: {model}")

                return response
            else:
                last_error = response.error_message
                logger.warning(f"模型调用失败: model={model}, error={response.error_message}")

        # 所有模型都失败
        self.stats['failed_calls'] += 1
        logger.error(f"所有模型调用失败: {last_error}")

        return ModelResponse(
            success=False,
            content="",
            model_id="",
            model_name="",
            error_message=str(last_error)
        )

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        if stats['success_calls'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] // stats['success_calls']
            stats['avg_tokens'] = stats['total_tokens'] // stats['success_calls']

        # 合并提供者统计
        provider_stats = self.provider.get_stats()
        stats['provider'] = provider_stats

        return stats

    def is_available(self) -> bool:
        """检查模型管理器是否可用"""
        return self.provider.is_available()
