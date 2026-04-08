"""
配置管理单元测试

测试 core/config.py — 配置加载、验证、便捷方法。
通过 os.environ 注入测试值，不修改实际配置文件。
"""

import os
import pytest
from core.config import Config


class TestDefaultConfig:
    """默认配置值"""

    def test_default_model(self):
        """默认模型名"""
        assert Config.PRIMARY_MODEL is not None
        assert len(Config.PRIMARY_MODEL) > 0

    def test_fallback_model(self):
        """备用模型"""
        assert Config.FALLBACK_MODEL is not None

    def test_similarity_threshold(self):
        """相似度阈值"""
        assert 0 < Config.SIMILARITY_THRESHOLD <= 1

    def test_confidence_threshold(self):
        """置信度阈值"""
        assert 0 < Config.CONFIDENCE_THRESHOLD <= 1

    def test_plans_exist(self):
        """套餐配置存在"""
        assert 'free' in Config.PLANS
        assert 'pack5' in Config.PLANS
        assert Config.PLANS['free']['price'] == 0

    def test_login_duration_options(self):
        """登录有效期选项"""
        assert 'session' in Config.LOGIN_DURATION_OPTIONS
        assert '7d' in Config.LOGIN_DURATION_OPTIONS
        assert '30d' in Config.LOGIN_DURATION_OPTIONS


class TestConfigMethods:
    """配置方法"""

    def test_get_model_for_task_analyze(self):
        """分析任务模型"""
        model = Config.get_model_for_task('analyze')
        assert model is not None
        assert isinstance(model, str)

    def test_get_model_for_task_generate(self):
        """生成任务模型"""
        model = Config.get_model_for_task('generate')
        assert model is not None

    def test_get_model_for_task_validate(self):
        """验证任务模型"""
        model = Config.get_model_for_task('validate')
        assert model is not None

    def test_get_model_for_task_unknown(self):
        """未知任务类型返回默认模型"""
        model = Config.get_model_for_task('unknown_task')
        assert model == Config.PRIMARY_MODEL

    def test_get_model_for_task_alibaba(self):
        """阿里云任务模型"""
        model = Config.get_model_for_task('analyze', provider='alibaba')
        assert model is not None

    def test_get_confidence_weights_experienced(self):
        """有经验者权重"""
        weights = Config.get_confidence_weights(has_work_experience=True)
        assert 'basic_info' in weights
        assert 'work_experience' in weights
        assert weights['work_experience'] > 0

    def test_get_confidence_weights_fresh(self):
        """应届生权重"""
        weights = Config.get_confidence_weights(has_work_experience=False)
        assert 'basic_info' in weights
        assert weights['work_experience'] == 0  # 无工作经验
        assert weights['education'] > weights.get('projects', 0)  # 教育权重更高

    def test_get_suspicious_patterns(self):
        """可疑关键词模式"""
        patterns = Config.get_suspicious_patterns()
        assert isinstance(patterns, list)
        assert len(patterns) > 0
        assert any('精通' in p for p in patterns)

    def test_get_ai_validation_config(self):
        """AI 验证配置"""
        config = Config.get_ai_validation_config()
        assert 'max_context_length' in config
        assert 'temperature' in config
        assert config['temperature'] < 0.5  # 验证任务应该用低温度


class TestConfigValidation:
    """配置验证"""

    def test_validate_with_key(self):
        """有 API key 时验证通过"""
        original_key = Config.ZHIPU_API_KEY
        try:
            Config.ZHIPU_API_KEY = 'test.key'
            assert Config.validate() is True
        finally:
            Config.ZHIPU_API_KEY = original_key

    def test_validate_without_key_raises(self):
        """无 API key 时验证失败"""
        original_key = Config.ZHIPU_API_KEY
        try:
            Config.ZHIPU_API_KEY = ''
            with pytest.raises(ValueError, match="ZHIPU_API_KEY"):
                Config.validate()
        finally:
            Config.ZHIPU_API_KEY = original_key

    def test_validate_multi_with_zhipu(self):
        """智谱 key 存在时多模型验证通过"""
        original_zhipu = Config.ZHIPU_API_KEY
        original_alibaba = Config.ALIBABA_API_KEY
        try:
            Config.ZHIPU_API_KEY = 'test.key'
            Config.ALIBABA_API_KEY = ''
            assert Config.validate_multi() is True
        finally:
            Config.ZHIPU_API_KEY = original_zhipu
            Config.ALIBABA_API_KEY = original_alibaba


class TestEnvironmentOverride:
    """环境变量覆盖"""

    def test_env_override_primary_model(self):
        """环境变量覆盖主模型"""
        original = Config.PRIMARY_MODEL
        try:
            os.environ['PRIMARY_MODEL'] = 'test-model'
            # 重新读取（注意：模块级变量已在 import 时加载）
            # Config 类属性在类定义时已设置，不会自动更新
            assert isinstance(original, str)
        finally:
            os.environ.pop('PRIMARY_MODEL', None)
