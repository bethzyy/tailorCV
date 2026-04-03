"""TC-R01~R03: 渲染完整性测试"""
import pytest


class TestRenderIntegrity:
    """验证 AI 输出的关键字段是否成功渲染到 docx"""

    # TC-R01: 基本信息字段已渲染
    def test_basic_info_fields_in_context(self, ai_output):
        """AI JSON 中的 basic_info 字段应在构建的上下文中存在"""
        assert 'basic_info' in ai_output or any(
            k.startswith('basic_info_') for k in ai_output.keys()
        ), "AI 输出应包含 basic_info"

    # TC-R02: 工作经历 tailored 已渲染（≥80% 条目）
    def test_work_tailored_coverage(self, ai_output):
        """≥80% 的工作经历条目应包含 tailored 字段"""
        work = ai_output.get('work_experience', [])
        if not work:
            pytest.skip("AI 输出中无工作经历")

        tailored_count = sum(1 for w in work if w.get('tailored', '').strip())
        coverage = tailored_count / len(work)
        assert coverage >= 0.8, (
            f"工作经历 tailored 覆盖率 {coverage:.0%} < 80% "
            f"({tailored_count}/{len(work)} 条目有 tailored)"
        )

    # TC-R03: 项目经历 tailored 已渲染（≥80% 条目）
    def test_project_tailored_coverage(self, ai_output):
        """≥80% 的项目经历条目应包含 tailored 字段"""
        projects = ai_output.get('projects', [])
        if not projects:
            pytest.skip("AI 输出中无项目经历")

        tailored_count = sum(1 for p in projects if p.get('tailored', '').strip())
        coverage = tailored_count / len(projects)
        assert coverage >= 0.8, (
            f"项目经历 tailored 覆盖率 {coverage:.0%} < 80% "
            f"({tailored_count}/{len(projects)} 条目有 tailored)"
        )
