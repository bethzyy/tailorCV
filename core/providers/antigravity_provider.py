"""
AntiGravity 模型提供者

使用 OpenAI 兼容端点调用 AntiGravity 本地代理服务。
端点: http://127.0.0.1:8045/v1
支持模型: gpt-4o, claude-sonnet-4-5, gemini-2.5-pro 等
"""

import time
import logging
import urllib.request
import urllib.error
from typing import Dict, Any

from .base_provider import BaseModelProvider, ModelResponse

logger = logging.getLogger(__name__)


class AntiGravityProvider(BaseModelProvider):
    """AntiGravity 本地代理模型提供者"""

    # 支持的模型列表
    MODELS = {
        'gpt-4o': 'GPT-4o',
        'gpt-4-turbo': 'GPT-4 Turbo',
        'claude-sonnet-4-5': 'Claude Sonnet 4.5',
        'claude-3-5-sonnet': 'Claude 3.5 Sonnet',
        'gemini-2.5-pro': 'Gemini 2.5 Pro',
        'gemini-2.0-flash-exp': 'Gemini 2.0 Flash',
        'gemini-1.5-pro': 'Gemini 1.5 Pro',
        'gemini-1.5-flash': 'Gemini 1.5 Flash',
    }

    BASE_URL = 'http://127.0.0.1:8045/v1'

    def __init__(self, base_url: str = None):
        self._base_url = (base_url or self.BASE_URL).rstrip('/')
        self._client = None
        self._available = None  # None = 未检测

        self.stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }

    def _ensure_client(self):
        if self._client is None:
            try:
                from openai import OpenAI
                self._client = OpenAI(
                    api_key='not-needed',
                    base_url=self._base_url
                )
            except ImportError:
                logger.error("openai 未安装，请运行: pip install openai")
                raise

    @property
    def provider_id(self) -> str:
        return 'antigravity'

    @property
    def provider_name(self) -> str:
        return 'AntiGravity 代理'

    @property
    def available_models(self) -> Dict[str, str]:
        return self.MODELS.copy()

    def is_available(self) -> bool:
        """通过探测 /models 端点检测代理是否在线"""
        if self._available is not None:
            return self._available
        try:
            url = f"{self._base_url}/models"
            req = urllib.request.Request(url, method='GET')
            with urllib.request.urlopen(req, timeout=3) as resp:
                self._available = resp.status == 200
        except Exception:
            self._available = False
        if not self._available:
            logger.debug("AntiGravity 代理不可用")
        return self._available

    def call(self, prompt: str, model_id: str = None,
             max_tokens: int = 4096, temperature: float = 0.7,
             max_retries: int = 2, **kwargs) -> ModelResponse:
        self._ensure_client()

        model_id = model_id or 'gpt-4o'
        model_name = self.get_model_name(model_id)

        self.stats['total_calls'] += 1
        last_error = None

        for attempt in range(max_retries):
            try:
                start_time = time.time()

                response = self._client.chat.completions.create(
                    model=model_id,
                    messages=[{"role": "user", "content": prompt}],
                    max_tokens=max_tokens,
                    temperature=temperature
                )

                latency_ms = int((time.time() - start_time) * 1000)
                content = response.choices[0].message.content

                self.stats['success_calls'] += 1
                tokens_used = response.usage.total_tokens if response.usage else 0
                self.stats['total_tokens'] += tokens_used
                self.stats['total_latency_ms'] += latency_ms

                logger.info(f"AntiGravity 调用成功: model={model_id}, tokens={tokens_used}, latency={latency_ms}ms")

                return ModelResponse(
                    success=True,
                    content=content,
                    model_id=model_id,
                    model_name=model_name,
                    tokens_used=tokens_used,
                    latency_ms=latency_ms
                )

            except Exception as e:
                last_error = e
                logger.warning(f"AntiGravity 调用失败 (model={model_id}, attempt={attempt+1}): {e}")
                if self._is_quota_error(e):
                    break
                if attempt < max_retries - 1:
                    time.sleep((attempt + 1) * 2)

        self.stats['failed_calls'] += 1
        logger.error(f"AntiGravity 调用最终失败: {last_error}")

        return ModelResponse(
            success=False,
            content="",
            model_id=model_id,
            model_name=model_name,
            error_message=str(last_error)
        )

    def _is_quota_error(self, error: Exception) -> bool:
        error_str = str(error).lower()
        return any(kw in error_str for kw in ['quota', 'limit', 'exhausted', 'rate', '429'])

    def get_stats(self) -> Dict[str, Any]:
        stats = self.stats.copy()
        if stats['success_calls'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] // stats['success_calls']
            stats['avg_tokens'] = stats['total_tokens'] // stats['success_calls']
        return stats
