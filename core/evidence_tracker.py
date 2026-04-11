"""
依据追踪器模块

实现混合验证机制：
1. 本地文本比对（快速，无AI成本）
2. 关键词验证（规则引擎）
3. AI验证（仅对可疑内容）
"""

import re
import json
import logging
from typing import Dict, Any, List, Optional, Tuple, Protocol
from dataclasses import dataclass, field
from difflib import SequenceMatcher

from .config import config

logger = logging.getLogger(__name__)

class ValidationResult:
    """验证结果"""
    def __init__(self, item_id: str, valid: bool, confidence: float, action: str, reason: str = "", details: Dict[str, Any] = None):
        self.item_id = item_id
        self.valid = valid
        self.confidence = confidence
        self.action = action  # pass / needs_review / reject
        self.reason = reason
        self.details = details if details is not None else {}

class EvidenceReport:
    """依据报告"""
    def __init__(self):
        self.total_items = 0
        self.validated = 0
        self.needs_review = 0
        self.rejected = 0
        self.coverage = 0.0
        self.items: List[ValidationResult] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            'total_items': self.total_items,
            'validated': self.validated,
            'needs_review': self.needs_review,
            'rejected': self.rejected,
            'coverage': round(self.coverage, 2),
            'details': [
                {
                    'item_id': item.item_id,
                    'validation_status': item.action,
                    'confidence': item.confidence,
                    'reason': item.reason
                }
                for item in self.items
            ]
        }

class TextAnalyzer:
    """文本分析器：负责相似度计算和关键词检查"""
    
    def __init__(self, similarity_threshold: float, suspicious_patterns: List[str]):
        self.similarity_threshold = similarity_threshold
        self.suspicious_patterns = suspicious_patterns

    def fuzzy_match(self, text1: str, text2: str) -> float:
        """
        模糊匹配两个文本的相似度

        Args:
            text1: 文本1
            text2: 文本2

        Returns:
            float: 相似度 (0.0 - 1.0)
        """
        if not text1 or not text2:
            return 0.0

        # 使用 SequenceMatcher 计算相似度
        matcher = SequenceMatcher(None, text1, text2)
        base_similarity = matcher.ratio()

        # 关键词重叠检查
        keywords1 = set(self._extract_keywords(text1))
        keywords2 = set(self._extract_keywords(text2))

        if keywords1 and keywords2:
            keyword_overlap = len(keywords1 & keywords2) / max(len(keywords1), len(keywords2))
        else:
            keyword_overlap = 0.0

        # 综合相似度
        final_similarity = base_similarity * 0.6 + keyword_overlap * 0.4
        return final_similarity

    def _extract_keywords(self, text: str) -> List[str]:
        """提取文本关键词"""
        # 简单的关键词提取（可以后续优化）
        # 移除标点和数字
        text = re.sub(r'[^\u4e00-\u9fa5a-zA-Z\s]', ' ', text)
        # 分词
        words = text.split()
        # 过滤短词
        keywords = [w for w in words if len(w) >= 2]
        return keywords

    def check_suspicious_keywords(self, text: str) -> List[str]:
        """
        检查可疑关键词

        Args:
            text: 待检查文本

        Returns:
            List[str]: 可疑关键词列表
        """
        suspicious = []
        for pattern in self.suspicious_patterns:
            if re.search(pattern, text):
                suspicious.append(pattern)

        return suspicious

class ConfidenceCalculator:
    """置信度计算器"""

    @staticmethod
    def calculate(base_confidence: float,
                  similarity: float,
                  suspicious: List[str]) -> float:
        """
        计算最终置信度

        Args:
            base_confidence: 基础置信度
            similarity: 相似度
            suspicious: 可疑关键词列表

        Returns:
            float: 最终置信度
        """
        # 基础置信度权重 40%
        confidence = base_confidence * 0.4

        # 相似度权重 40%
        confidence += similarity * 0.4

        # 可疑关键词扣分权重 20%
        suspicious_penalty = len(suspicious) * 0.1
        confidence += max(0, 0.2 - suspicious_penalty)

        return min(1.0, max(0.0, confidence))

# 定义 ModelManager 协议以避免循环导入
class ModelManagerProtocol(Protocol):
    """模型管理器协议"""
    
    def call(self, prompt: str, task_type: str, max_tokens: int, temperature: float) -> Any:
        """调用模型"""
        ...

class AIValidator:
    """AI验证器：负责调用模型进行验证"""

    def __init__(self, model_manager: Optional[ModelManagerProtocol], ai_validation_config: Dict[str, Any]):
        self.model_manager = model_manager
        self.ai_validation_config = ai_validation_config

    def validate(self, tailored_text: str, original_resume: str) -> Dict[str, Any]:
        """
        AI 验证（对可疑内容）- 优化版

        Args:
            tailored_text: 定制文本
            original_resume: 原版简历

        Returns:
            Dict: 验证结果
        """
        if not self.model_manager:
            return {'valid': True, 'confidence': 0.5, 'reason': '无AI验证器'}

        # 使用配置化的上下文长度
        max_context = self.ai_validation_config['max_context_length']
        max_content = self.ai_validation_config['max_content_length']

        # 截取适当长度的上下文
        original_context = original_resume[:max_context]
        tailored_context = tailored_text[:max_content]

        # 优化的验证Prompt
        prompt = f"""你是一个专业的简历验证专家。请仔细验证以下定制简历内容的真实性。

## 任务说明
你需要判断【定制内容】中的描述是否可以在【原版简历】中找到依据，是否存在夸大或虚构。

## 原版简历（摘要）
{original_context}

## 待验证的定制内容
{tailored_context}

## 验证标准
1. **通过 (valid=true, confidence≥0.7)**：内容完全来自原文，仅有表达方式的优化
2. **需人工确认 (valid=true, confidence<0.7)**：内容基于原文，但有关联性较弱的扩展
3. **拒绝 (valid=false)**：内容在原文中找不到任何依据，或存在明显编造

## 验证要点
- 检查技能、成就、数据是否有原文支持
- 识别是否有"精通"、"专家"等夸大词汇
- 判断时间线是否合理
- 评估职责描述是否与原文相符

请以JSON格式回复（不要包含其他内容）：
{{
    "valid": true或false,
    "confidence": 0.0到1.0之间的数值,
    "reason": "简要说明判断依据"
}}
"""

        try:
            response = self.model_manager.call(
                prompt=prompt,
                task_type='validate',
                max_tokens=self.ai_validation_config['max_tokens'],
                temperature=self.ai_validation_config['temperature']
            )

            if response.success:
                # 解析结果
                json_match = re.search(r'\{[\s\S]*\}', response.content)
                if json_match:
                    result = json.loads(json_match.group())
                    logger.info(f"AI验证完成: valid={result.get('valid')}, confidence={result.get('confidence')}")
                    return result
        except Exception as e:
            logger.warning(f"AI 验证失败: {e}")

        # 默认返回
        return {'valid': True, 'confidence': 0.5, 'reason': '验证异常，默认通过'}

class EvidenceTracker:
    """依据追踪器 - 混合验证机制"""

    SIMILARITY_THRESHOLD = config.SIMILARITY_THRESHOLD
    CONFIDENCE_THRESHOLD = config.CONFIDENCE_THRESHOLD

    # 从配置加载可疑关键词模式
    SUSPICIOUS_PATTERNS = config.get_suspicious_patterns()

    def __init__(self, model_manager: Optional[ModelManagerProtocol] = None):
        """
        初始化依据追踪器

        Args:
            model_manager: 模型管理器（用于AI验证）
        """
        self.model_manager = model_manager
        self.ai_validation_config = config.get_ai_validation_config()
        self.validation_stats = {
            'local_checks': 0,
            'ai_checks': 0,
            'passed': 0,
            'needs_review': 0,
            'rejected': 0
        }
        
        # 初始化组件
        self.text_analyzer = TextAnalyzer(self.SIMILARITY_THRESHOLD, self.SUSPICIOUS_PATTERNS)
        self.ai_validator = AIValidator(model_manager, self.ai_validation_config)

    def validate_content(self, original_resume: str,
                         tailored_content: Dict[str, Any]) -> ValidationResult:
        """
        验证定制内容

        Args:
            original_resume: 原版简历文本
            tailored_content: 定制内容（包含 original, tailored, evidence）

        Returns:
            ValidationResult: 验证结果
        """
        return self._validate_content(original_resume, tailored_content)

    def validate_resume(self, original_resume: str,
                        tailored_resume: Dict[str, Any]) -> EvidenceReport:
        """
        验证整个定制简历

        Args:
            original_resume: 原版简历文本
            tailored_resume: 定制简历结构

        Returns:
            EvidenceReport: 依据报告
        """
        return self._validate_resume(original_resume, tailored_resume)

    def _validate_content(self, original_resume: str,
                          tailored_content: Dict[str, Any]) -> ValidationResult:
        item_id = tailored_content.get('id', 'unknown')
        evidence = tailored_content.get('evidence', {})
        original = tailored_content.get('original', '')
        tailored = tailored_content.get('tailored', '')

        self.validation_stats['local_checks'] += 1

        # 第一重：本地文本相似度
        similarity = self.text_analyzer.fuzzy_match(original, tailored)
        if similarity < self.SIMILARITY_THRESHOLD:
            self.validation_stats['rejected'] += 1
            return ValidationResult(
                item_id=item_id,
                valid=False,
                confidence=evidence.get('confidence', 0.5),
                action='reject',
                reason=f'原文匹配度{similarity:.0%}低于阈值{self.SIMILARITY_THRESHOLD:.0%}',
                details={'similarity': similarity}
            )

        # 第二重：可疑关键词检查
        suspicious = self.text_analyzer.check_suspicious_keywords(tailored)

        # 第三重：AI验证（仅对可疑内容）
        if suspicious and evidence.get('confidence', 1.0) < self.CONFIDENCE_THRESHOLD:
            ai_result = self.ai_validator.validate(tailored, original_resume)
            if not ai_result['valid']:
                self.validation_stats['rejected'] += 1
                return ValidationResult(
                    item_id=item_id,
                    valid=False,
                    confidence=ai_result['confidence'],
                    action='reject',
                    reason=ai_result['reason'],
                    details={'suspicious_keywords': suspicious}
                )

        # 计算最终置信度
        final_confidence = ConfidenceCalculator.calculate(
            evidence.get('confidence', 0.8),
            similarity,
            suspicious
        )

        # 判断是否需要人工确认
        if final_confidence < self.CONFIDENCE_THRESHOLD:
            self.validation_stats['needs_review'] += 1
            return ValidationResult(
                item_id=item_id,
                valid=True,
                confidence=final_confidence,
                action='needs_review',
                reason='置信度较低，建议人工确认',
                details={'similarity': similarity, 'suspicious_keywords': suspicious}
            )

        self.validation_stats['passed'] += 1
        return ValidationResult(
            item_id=item_id,
            valid=True,
            confidence=final_confidence,
            action='pass',
            details={'similarity': similarity}
        )

    def _validate_resume(self, original_resume: str,
                         tailored_resume: Dict[str, Any]) -> EvidenceReport:
        report = EvidenceReport()

        # 验证工作经历
        self._validate_section(tailored_resume.get('work_experience', []), original_resume, report)
        
        # 验证项目经历
        self._validate_section(tailored_resume.get('projects', []), original_resume, report)
        
        # 验证技能
        self._validate_section(tailored_resume.get('skills', []), original_resume, report)
        
        # 验证教育背景
        self._validate_section(tailored_resume.get('education', []), original_resume, report)

        # 统计结果
        for item in report.items:
            if item.action == 'pass':
                report.validated += 1
            elif item.action == 'needs_review':
                report.needs_review += 1
            else:
                report.rejected += 1

        # 计算覆盖率
        if report.total_items > 0:
            report.coverage = report.validated / report.total_items

        logger.info(f"验证完成: 总数={report.total_items}, 通过={report.validated}, "
                   f"需确认={report.needs_review}, 拒绝={report.rejected}, "
                   f"覆盖率={report.coverage:.0%}")

        return report

    def _validate_section(self, items: List[Dict[str, Any]], original_resume: str, report: EvidenceReport):
        """验证简历中的某个章节"""
        for item in items:
            result = self._validate_content(original_resume, item)
            report.items.append(result)
            report.total_items += 1

    def get_stats(self) -> Dict[str, int]:
        """获取验证统计"""
        return self.validation_stats.copy()
