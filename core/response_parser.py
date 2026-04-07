"""
AI 响应 JSON 解析工具函数

从 expert_team.py 和 multi_expert_team.py 中提取的公共逻辑。
所有函数均为纯函数，不依赖类实例。
"""
import json
import logging
import re
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)


def extract_json_from_text(text: str) -> Optional[str]:
    """从 AI 响应文本中提取 JSON 字符串

    策略：
    1. 匹配 ```json ... ``` 代码块
    2. 使用栈匹配提取平衡 JSON
    3. 正则匹配 { ... }（兜底）
    """
    if not text:
        return None

    # Level 1: ```json ... ``` 代码块
    json_pattern = r'```json\s*([\s\S]*?)\s*```'
    match = re.search(json_pattern, text)
    if match:
        candidate = match.group(1)
        try:
            json.loads(candidate)
            return candidate
        except json.JSONDecodeError:
            pass  # 继续尝试其他策略

    # Level 2: 栈匹配平衡 JSON
    balanced = extract_balanced_json(text)
    if balanced:
        try:
            json.loads(balanced)
            return balanced
        except json.JSONDecodeError:
            pass

    # Level 3: 正则兜底
    json_pattern = r'\{[\s\S]*\}'
    match = re.search(json_pattern, text)
    if match:
        return match.group(0)

    return None


def extract_balanced_json(text: str) -> Optional[str]:
    """使用栈匹配提取平衡的 JSON（最外层 {}）"""
    stack = []
    start_idx = None
    for i, char in enumerate(text):
        if char == '{':
            if not stack:
                start_idx = i
            stack.append(char)
        elif char == '}':
            if stack:
                stack.pop()
                if not stack and start_idx is not None:
                    return text[start_idx:i + 1]
    return None


def try_complete_json(text: str) -> Optional[str]:
    """尝试补全不完整的 JSON（缺少外层 {}）

    处理多种前导字符情况：
    - 以 "key": 开头但缺少外层 {}
    - 以 } 结尾但缺少开头 {
    - 提取第一个 " 和最后一个 } 之间的内容
    """
    trimmed = text.strip()
    if not trimmed:
        return None

    # 情况1：以 " 开头但不是 { 开头 → 缺少外层 {}
    if trimmed.startswith('"') and not trimmed.startswith('{'):
        completed = '{' + trimmed + '}'
        try:
            json.loads(completed)
            return completed
        except json.JSONDecodeError:
            pass

    # 情况2：以 } 结尾但缺少开头 {
    if trimmed.endswith('}') and not trimmed.startswith('{'):
        completed = '{' + trimmed
        try:
            json.loads(completed)
            return completed
        except json.JSONDecodeError:
            pass

    # 情况3：尝试查找第一个 " 和最后一个 } 之间的内容
    first_quote = trimmed.find('"')
    last_brace = trimmed.rfind('}')
    if first_quote != -1 and last_brace != -1 and first_quote < last_brace:
        inner = trimmed[first_quote:last_brace + 1]
        completed = '{' + inner + '}'
        try:
            json.loads(completed)
            return completed
        except json.JSONDecodeError:
            pass

    return None


def repair_json(json_str: str) -> Optional[str]:
    """尝试修复常见的 JSON 错误"""
    repaired = json_str
    # 1. 修复末尾多余的逗号
    repaired = re.sub(r',\s*}', '}', repaired)
    repaired = re.sub(r',\s*]', ']', repaired)
    # 2. 修复缺失的引号（只对未加引号的键）
    repaired = re.sub(r'(?<!")(\b\w+\b)(?=\s*:)', r'"\1"', repaired)
    return repaired if repaired != json_str else None


def safe_get_dict(data: dict, key: str, default: Optional[dict] = None,
                  convert_list: bool = False) -> dict:
    """安全获取字典字段

    Args:
        data: 源数据字典
        key: 字段名
        default: 默认值（默认 {}）
        convert_list: 为 True 时，如果值是 list 则包装为 {key: value}
    """
    if default is None:
        default = {}
    value = data.get(key, default)
    if isinstance(value, dict):
        return value
    if convert_list and isinstance(value, list):
        return {key: value}
    return default


def safe_get_list(data: dict, key: str, default: Optional[list] = None) -> list:
    """安全获取列表字段"""
    if default is None:
        default = []
    value = data.get(key, default)
    return value if isinstance(value, list) else default


def validate_analysis_fields(matching_strategy: dict) -> dict:
    """验证并补全分析结果的 matching_strategy 字段"""
    if not matching_strategy:
        matching_strategy = {}
    matching_strategy.setdefault('match_score', 50)
    matching_strategy.setdefault('match_level', '未知')
    matching_strategy.setdefault('strengths', [])
    matching_strategy.setdefault('gaps', [])
    return matching_strategy


def validate_generation_fields(tailored_resume: dict) -> dict:
    """验证并补全生成结果的 tailored_resume 基本字段"""
    if not tailored_resume:
        tailored_resume = {}
    for field in ['basic_info', 'education', 'work_experience', 'skills']:
        if field not in tailored_resume:
            tailored_resume[field] = [] if field != 'basic_info' else {}
    return tailored_resume
