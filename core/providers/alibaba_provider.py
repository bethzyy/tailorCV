"""
阿里云 Coding Plan 模型提供者

实现阿里云 DashScope（Coding Plan）模型的调用接口。
支持多种模型：Qwen3.5、Qwen3 Max、Kimi、GLM、MiniMax 等。
"""

import os
import time
import logging
from pathlib import Path
from typing import Dict, Any, Optional, Callable

from .base_provider import BaseModelProvider, ModelResponse

logger = logging.getLogger(__name__)

class AlibabaProvider(BaseModelProvider):
    """阿里云 Coding Plan 模型提供者"""

    # 支持的模型列表（Coding Plan）
    MODELS = {
        'qwen3.5-plus': 'Qwen3.5 Plus',
        'qwen3-max-2026-01-23': 'Qwen3 Max',
        'kimi-k2.5': 'Kimi K2.5',
        'glm-5': 'GLM-5',
        'glm-4.7': 'GLM-4.7',
        'MiniMax-M2.5': 'MiniMax M2.5',
    }

    # API 配置
    BASE_URL = 'https://coding.dashscope.aliyuncs.com/v1'
    API_KEY_PATH = r'C:\D\CAIE_tool\LLM_Configs\ali\apikey.txt'

    def __init__(self, api_key: str = None, client_factory: Callable = None):
        """
        初始化阿里云提供者

        Args:
            api_key: API密钥（可选，默认从文件或环境变量读取）
            client_factory: 客户端工厂函数（可选，用于依赖注入以避免循环导入）
        """
        self._api_key = api_key or self._load_api_key()
        self._client = None
        self._client_factory = client_factory

        # 调用统计
        self.stats = {
            'total_calls': 0,
            'success_calls': 0,
            'failed_calls': 0,
            'total_tokens': 0,
            'total_latency_ms': 0
        }

    def _load_api_key(self) -> str:
        """从文件加载 API 密钥

        支持两种文件格式：
        1. 纯 API key（单行）
        2. key=value 格式（如 DASHSCOPE_API_KEY="sk-xxx"）
        """
        # 1. 尝试从环境变量
        api_key = os.getenv('ALIBABA_API_KEY', '')
        if api_key:
            return api_key

        # 2. 尝试从文件
        key_path = Path(self.API_KEY_PATH)
        if key_path.exists():
            try:
                content = key_path.read_text(encoding='utf-8').strip()
                # 尝试 key=value 格式解析
                for line in content.splitlines():
                    line = line.strip()
                    if line.startswith('#') or not line:
                        continue
                    if '=' in line:
                        key_name, _, key_value = line.partition('=')
                        key_name = key_name.strip()
                        key_value = key_value.strip().strip('"').strip("'")
                        if key_name in ('DASHSCOPE_API_KEY', 'API_KEY', 'ALIBABA_API_KEY'):
                            return key_value
                # 纯 API key（整行就是 key）
                if content and '=' not in content.splitlines()[0]:
                    return content.splitlines()[0].strip().strip('"').strip("'")
            except Exception as e:
                logger.warning(f"读取阿里云API密钥失败: {e}")

        return ''

    def _ensure_client(self):
        """确保客户端已初始化"""
        if self._client is None and self._api_key:
            try:
                if self._client_factory:
                    self._client = self._client_factory(
                        api_key=self._api_key,
                        base_url=self.BASE_URL
                    )
                else:
                    from openai import OpenAI
                    self._client = OpenAI(
                        api_key=self._api_key,
                        base_url=self.BASE_URL
                    )
            except ImportError:
                logger.error("openai 未安装，请运行: pip install openai")
                raise

    @property
    def provider_id(self) -> str:
        return 'alibaba'

    @property
    def provider_name(self) -> str:
        return '阿里云 Coding Plan'

    @property
    def available_models(self) -> Dict[str, str]:
        return self.MODELS.copy()

    def is_available(self) -> bool:
        """检查阿里云是否可用"""
        return bool(self._api_key)

    def call(self, prompt: str, model_id: str = None,
             max_tokens: int = 4096, temperature: float = 0.7,
             max_retries: int = 3, **kwargs) -> ModelResponse:
        """
        调用阿里云模型

        Args:
            prompt: 输入提示词
            model_id: 模型ID（默认 qwen3.5-plus）
            max_tokens: 最大输出token数
            temperature: 温度参数
            max_retries: 最大重试次数

        Returns:
            ModelResponse: 模型响应
        """
        self._ensure_client()

        model_id = model_id or 'qwen3.5-plus'
        model_name = self.get_model_name(model_id)

        self.stats['total_calls'] += 1

        return self._call_with_retry(
            prompt, model_id, model_name, max_tokens, temperature, max_retries
        )

    def _call_with_retry(self, prompt: str, model_id: str, model_name: str,
                         max_tokens: int, temperature: float,
                         max_retries: int) -> ModelResponse:
        """带重试机制的模型调用"""
        last_error = None
        for attempt in range(max_retries):
            try:
                response, latency_ms = self._execute_request(
                    prompt, model_id, max_tokens, temperature
                )
                return self._process_success_response(
                    response, model_id, model_name, latency_ms
                )
            except Exception as e:
                last_error = e
                should_retry = self._handle_request_error(e, model_id, attempt, max_retries)
                if not should_retry:
                    break

        return self._build_failure_response(model_id, model_name, last_error)

    def _build_failure_response(self, model_id: str, model_name: str,
                                error: Exception) -> ModelResponse:
        """构建失败响应"""
        self.stats['failed_calls'] += 1
        logger.error(f"阿里云调用最终失败: {error}")

        return ModelResponse(
            success=False,
            content="",
            model_id=model_id,
            model_name=model_name,
            error_message=str(error)
        )

    def _execute_request(self, prompt: str, model_id: str,
                         max_tokens: int, temperature: float) -> tuple:
        """执行单次 API 请求"""
        start_time = time.time()

        response = self._client.chat.completions.create(
            model=model_id,
            messages=[{
                "role": "user",
                "content": prompt
            }],
            max_tokens=max_tokens,
            temperature=temperature
        )

        latency_ms = int((time.time() - start_time) * 1000)
        return response, latency_ms

    def _process_success_response(self, response, model_id: str,
                                   model_name: str, latency_ms: int) -> ModelResponse:
        """处理成功的 API 响应"""
        content = response.choices[0].message.content

        # 更新统计
        self.stats['success_calls'] += 1
        tokens_used = response.usage.total_tokens if response.usage else 0
        self.stats['total_tokens'] += tokens_used
        self.stats['total_latency_ms'] += latency_ms

        logger.info(f"阿里云调用成功: model={model_id}, tokens={tokens_used}, latency={latency_ms}ms")

        return ModelResponse(
            success=True,
            content=content,
            model_id=model_id,
            model_name=model_name,
            tokens_used=tokens_used,
            latency_ms=latency_ms
        )

    def _handle_request_error(self, error: Exception, model_id: str,
                              attempt: int, max_retries: int) -> bool:
        """处理请求错误并决定是否重试"""
        logger.warning(f"阿里云调用失败 (model={model_id}, attempt={attempt+1}): {error}")

        # 配额错误不重试
        if self._is_quota_error(error):
            return False

        # 等待后重试
        if attempt < max_retries - 1:
            wait_time = (attempt + 1) * 2
            time.sleep(wait_time)
            return True

        return False

    def _is_quota_error(self, error: Exception) -> bool:
        """判断是否为配额错误"""
        error_str = str(error).lower()
        quota_keywords = ['quota', 'limit', 'exhausted', 'rate', 'throttl']
        return any(kw in error_str for kw in quota_keywords)

    def get_stats(self) -> Dict[str, Any]:
        """获取调用统计"""
        stats = self.stats.copy()
        if stats['success_calls'] > 0:
            stats['avg_latency_ms'] = stats['total_latency_ms'] // stats['success_calls']
            stats['avg_tokens'] = stats['total_tokens'] // stats['success_calls']
        return stats
