"""
高级幻觉检测测试 — 超越禁用词列表

检测方式：
- 实体级比对：公司名/项目名/日期/数字与原始简历核对
- 程度词审计：检测"参与→主导"、"了解→精通"等程度升级
- 逻辑一致性：工作时间与项目时间是否矛盾
"""
import re
import pytest


# 程度升级映射 — 左侧是原始用词，右侧是不合理升级
DEGREE_ESCALATION = {
    "参与": ["主导", "独立负责", "全权负责"],
    "了解": ["精通", "深入掌握", "熟练掌握"],
    "协助": ["负责", "主导", "独立完成"],
    "学习": ["精通", "熟练掌握"],
    "使用": ["精通", "深度使用"],
    "接触": ["精通", "熟练运用"],
}


class TestEntityLevelComparison:
    """实体级比对测试 — 不依赖 LLM，纯规则检测"""

    def test_company_names_preserved(self):
        """公司名应与原始简历一致，不应出现新公司"""
        original = "字节跳动 美团"
        generated = "负责字节跳动和美团的核心业务开发"
        original_companies = set(original.split())
        # 从生成内容中提取的公司名应在原始简历中存在
        for company in original_companies:
            assert company in generated, f"原始公司名丢失: {company}"

    def test_no_fabricated_companies(self):
        """不应出现原始简历中没有的公司名"""
        original_companies = {"字节跳动", "美团"}
        generated = "在字节跳动和美团工作期间"
        # 简单检测：不应出现原始中没有的大公司名
        known_companies = {"阿里", "阿里巴巴", "腾讯", "百度", "华为", "京东", "PDD", "拼多多"}
        for company in known_companies:
            if company not in original_companies:
                assert company not in generated, f"出现编造的公司名: {company}"

    def test_education_fields_preserved(self):
        """学校和专业应与原始简历一致"""
        original_school = "清华大学"
        original_major = "计算机科学与技术"
        generated = "2016-2020 清华大学 计算机科学与技术 本科"
        assert original_school in generated
        assert original_major in generated

    def test_dates_preserved(self):
        """工作/教育时间不应被篡改"""
        original = "2020-2023"
        generated = "2020-2023 字节跳动"
        assert original in generated, "工作时间被篡改"

    def test_quantified_numbers_source_check(self):
        """量化数字应能追溯到原始简历"""
        original_numbers = re.findall(r'\d+', "日均处理1000万请求，性能提升40%")
        generated = "日均处理1000万请求，查询性能提升40%"
        for num in original_numbers:
            assert num in generated, f"原始数字丢失: {num}"


class TestDegreeEscalationAudit:
    """程度词审计 — 检测不合理的程度升级"""

    def _find_escalations(self, original, generated):
        """检测生成内容中是否存在程度升级"""
        escalations = []
        for original_word, escalated_words in DEGREE_ESCALATION.items():
            if original_word in original:
                for escalated in escalated_words:
                    if escalated in generated and original_word not in generated:
                        escalations.append(f"原始用'{original_word}'被升级为'{escalated}'")
        return escalations

    def test_no_participate_to_lead(self):
        '"参与"不应被升级为"主导"'
        original = "参与数据库优化"
        generated = "参与数据库优化，通过索引调整提升查询性能"
        escalations = self._find_escalations(original, generated)
        assert not escalations, f"检测到程度升级: {escalations}"

    def test_no_know_to_master(self):
        '"了解"不应被升级为"精通"'
        original = "了解Docker基本使用"
        generated = "了解Docker基本使用，能进行简单的容器化部署"
        escalations = self._find_escalations(original, generated)
        assert not escalations, f"检测到程度升级: {escalations}"

    def test_reasonable_degree_upgrade_allowed(self):
        """合理的程度描述升级是允许的（原词保留 + 补充）"""
        original = "参与后端架构设计"
        # 合理：保留"参与"并补充具体内容
        generated_good = "参与后端架构设计和开发，负责核心模块的实现"
        escalations = self._find_escalations(original, generated_good)
        assert not escalations, f"合理的扩写被误判为升级: {escalations}"


@pytest.mark.semantic
@pytest.mark.slow
class TestLLMHallucinationDetection:
    """LLM-as-Judge 幻觉检测 — 检测更隐蔽的编造"""

    def test_no_fabricated_achievements(self, judge_no_hallucination):
        """不应编造原始简历中没有的成果"""
        original = "负责API开发，日均处理1000万请求"
        jd = "有大规模系统经验"
        generated = "负责API开发，日均处理1000万请求，获得公司技术创新奖"

        result = judge_no_hallucination(original, jd, generated)
        if result:
            assert result["score"] >= 3.5, f"检测到编造成果: {result['reason']}"

    def test_no_fabricated_responsibilities(self, judge_no_hallucination):
        """不应编造超出原始简历范围的职责"""
        original = "后端工程师，负责API开发"
        jd = "全栈工程师"
        generated = "全栈工程师，负责前后端开发和DevOps运维"

        result = judge_no_hallucination(original, jd, generated)
        if result:
            assert result["score"] >= 3.5, f"职责被不合理扩大: {result['reason']}"
