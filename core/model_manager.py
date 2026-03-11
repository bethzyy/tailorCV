"""
模型管理器模块

负责管理 ZhipuAI 模型调用，包括主备切换和重试机制。
"""

import os
import time
import json
import logging
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from zhipuai import ZhipuAI

from .config import config

logger = logging.getLogger(__name__)


@dataclass
class ModelResponse:
    """模型响应数据结构"""
    success: bool
    content: str
    model_used: str
    tokens_used: int = 0
    latency_ms: int = 0
    error_message: str = ""


class ModelManager:
    """模型管理器 - 主备切换和重试机制"""

    def __init__(self):
        self.api_key = config.ZHIPU_API_KEY
        if not self.api_key:
            raise ValueError("ZHIPU_API_KEY 未配置")

        self.client = ZhipuAI(api_key=self.api_key)
        self.primary_model = config.PRIMARY_MODEL
        self.fallback_models = config.FALLBACK_MODEL.split(',') if isinstance(config.FALLBACK_MODEL, str) else [config.FALLBACK_MODEL]

        # 调用统计
        self.stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'fallback_used': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }

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
        # 去重
        models_to_try = list(dict.fromkeys(models_to_try))

        last_error = None

        for model in models_to_try:
            for attempt in range(max_retries):
                try:
                    start_time = time.time()

                    response = self.client.chat.completions.create(
                        model=model,
                        messages=[{
                            "role": "user",
                            "content": prompt
                        }],
                        max_tokens=max_tokens,
                        temperature=temperature
                    )

                    latency_ms = int((time.time() - start_time) * 1000)

                    # 提取内容
                    content = response.choices[0].message.content

                    # 统计
                    self.stats['success_calls'] += 1
                    self.stats['total_tokens'] += response.usage.total_tokens
                    self.stats['total_latency_ms'] += latency_ms

                    if model != preferred_model:
                        self.stats['fallback_used'] += 1
                        logger.info(f"使用备用模型: {model}")

                    logger.info(f"模型调用成功: {model}, tokens={response.usage.total_tokens}, latency={latency_ms}ms")

                    return ModelResponse(
                        success=True,
                        content=content,
                        model_used=model,
                        tokens_used=response.usage.total_tokens,
                        latency_ms=latency_ms
                    )

                except Exception as e:
                    last_error = e
                    logger.warning(f"模型调用失败 (model={model}, attempt={attempt+1}): {e}")

                    # 如果是配额错误，立即切换模型
                    if self._is_quota_error(e):
                        logger.info(f"检测到配额错误，切换模型")
                        break

                    # 其他错误，等待后重试
                    if attempt < max_retries - 1:
                        wait_time = (attempt + 1) * 2  # 指数退避
                        time.sleep(wait_time)

        # 所有模型都失败
        self.stats['failed_calls'] += 1
        logger.error(f"所有模型调用失败: {last_error}")

        return ModelResponse(
            success=False,
            content="",
            model_used="",
            error_message=str(last_error)
        )

    def _is_quota_error(self, error: Exception) -> bool:
        """判断是否为配额错误"""
        error_str = str(error).lower()
        quota_keywords = ['quota', 'limit', 'exhausted', 'rate', '1310']
        return any(kw in error_str for kw in quota_keywords)

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        if stats['success_calls'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] // stats['success_calls']
            stats['avg_tokens'] = stats['total_tokens'] // stats['success_calls']
        return stats
