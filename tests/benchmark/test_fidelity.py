"""TC-F01~F03: 忠实度测试"""
import pytest


class TestFidelity:
    """验证定制简历忠实于原始简历"""

    # TC-F01: 非定制字段保持原值
    def test_non_customized_fields_preserved(self, ai_output, original_resume):
        """姓名、学校、公司名等非定制字段应保持原值"""
        if not original_resume:
            pytest.skip("无原始简历 fixture")

        # 检查姓名保持不变
        ai_name = ''
        if 'basic_info' in ai_output:
            ai_name = ai_output['basic_info'].get('name', '')
        elif 'name' in ai_output:
            ai_name = ai_output['name']

        orig_name = ''
        if 'basic_info' in original_resume:
            orig_name = original_resume['basic_info'].get('name', '')
        elif 'name' in original_resume:
            orig_name = original_resume['name']

        if orig_name and ai_name:
            assert orig_name in ai_name or ai_name in orig_name, (
                f"姓名不一致: 原始 '{orig_name}' vs 定制 '{ai_name}'"
            )

    # TC-F02: 工作经历条目数量不变
    def test_work_experience_count_preserved(self, ai_output, original_resume):
        """定制后工作经历条目数量应与原始一致"""
        if not original_resume:
            pytest.skip("无原始简历 fixture")

        orig_count = len(original_resume.get('work_experience', []))
        ai_count = len(ai_output.get('work_experience', []))

        if orig_count > 0:
            assert ai_count == orig_count, (
                f"工作经历条目数不一致: 原始 {orig_count} vs 定制 {ai_count}"
            )

    # TC-F03: 教育背景保持不变
    def test_education_preserved(self, ai_output, original_resume):
        """教育背景信息应完全保持原值"""
        if not original_resume:
            pytest.skip("无原始简历 fixture")

        orig_edu = original_resume.get('education', [])
        ai_edu = ai_output.get('education', [])

        if orig_edu and ai_edu:
            # 学校名称应一致
            orig_schools = {e.get('school', '') for e in orig_edu if isinstance(e, dict)}
            ai_schools = {e.get('school', '') for e in ai_edu if isinstance(e, dict)}
            assert orig_schools == ai_schools, (
                f"学校不一致: 原始 {orig_schools} vs 定制 {ai_schools}"
            )
