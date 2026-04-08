"""response_parser 工具函数单元测试"""
import json
import pytest
from core.response_parser import (
    extract_json_from_text, extract_balanced_json,
    try_complete_json, repair_json, safe_get_dict,
    safe_get_list, validate_analysis_fields, validate_generation_fields,
)


class TestExtractJsonFromText:
    def test_json_code_block(self):
        text = '```json\n{"name": "test"}\n```'
        result = extract_json_from_text(text)
        assert result is not None
        data = json.loads(result)
        assert data["name"] == "test"

    def test_balanced_json(self):
        text = '分析结果：\n{"match_score": 85}\n其他内容'
        result = extract_json_from_text(text)
        assert result is not None
        data = json.loads(result)
        assert data["match_score"] == 85

    def test_regex_fallback(self):
        text = 'Response: {"key": "value"}'
        result = extract_json_from_text(text)
        assert result is not None
        assert '"key"' in result

    def test_empty_text(self):
        assert extract_json_from_text('') is None
        assert extract_json_from_text(None) is None

    def test_no_json(self):
        assert extract_json_from_text('这是纯文本，没有JSON') is None


class TestExtractBalancedJson:
    def test_nested_json(self):
        text = 'prefix {"outer": {"inner": [1, 2, 3]}} suffix'
        result = extract_balanced_json(text)
        assert '"inner"' in result

    def test_multiple_braces(self):
        text = '{"a": {"b": 1}, "c": 2}'
        result = extract_balanced_json(text)
        assert result == text

    def test_unbalanced(self):
        text = '{"key": "value"'
        result = extract_balanced_json(text)
        assert result is None

    def test_empty(self):
        assert extract_balanced_json('') is None


class TestTryCompleteJson:
    def test_missing_opening_brace(self):
        text = '"name": "test", "age": 30}'
        result = try_complete_json(text)
        assert result is not None
        json.loads(result)  # 应该是有效 JSON

    def test_starting_with_quote(self):
        text = '"key": "value"}'
        result = try_complete_json(text)
        assert result is not None
        json.loads(result)

    def test_empty(self):
        assert try_complete_json('') is None

    def test_already_valid(self):
        text = '{"key": "value"}'
        # try_complete_json 不会修改已经是有效的 JSON
        result = try_complete_json(text)
        # 这种情况应该返回 None（不以 " 开头，且以 { 开头）
        assert result is None


class TestRepairJson:
    def test_trailing_comma_in_object(self):
        text = '{"items": [1, 2, 3,],}'
        result = repair_json(text)
        assert result is not None
        json.loads(result)

    def test_trailing_comma_in_array(self):
        text = '{"items": [1, 2, 3,]}'
        result = repair_json(text)
        assert result is not None
        json.loads(result)

    def test_no_repair_needed(self):
        text = '{"key": "value"}'
        assert repair_json(text) is None

    def test_unquoted_keys(self):
        text = '{name: "test", age: 30}'
        result = repair_json(text)
        assert result is not None
        json.loads(result)


class TestSafeGetDict:
    def test_normal_dict(self):
        assert safe_get_dict({"a": {"b": 1}}, "a") == {"b": 1}

    def test_missing_key(self):
        assert safe_get_dict({"a": 1}, "b") == {}

    def test_wrong_type_string(self):
        assert safe_get_dict({"a": "not_dict"}, "a") == {}

    def test_list_to_dict_conversion(self):
        result = safe_get_dict({"a": [1, 2]}, "a", convert_list=True)
        assert result == {"a": [1, 2]}

    def test_list_no_conversion(self):
        result = safe_get_dict({"a": [1, 2]}, "a", convert_list=False)
        assert result == {}

    def test_custom_default(self):
        result = safe_get_dict({"a": "str"}, "a", default={"fallback": True})
        assert result == {"fallback": True}


class TestSafeGetList:
    def test_normal_list(self):
        assert safe_get_list({"a": [1, 2]}, "a") == [1, 2]

    def test_missing_key(self):
        assert safe_get_list({"a": 1}, "b") == []

    def test_wrong_type(self):
        assert safe_get_list({"a": "not_list"}, "a") == []

    def test_custom_default(self):
        assert safe_get_list({"a": "str"}, "a", default=[99]) == [99]


class TestValidateAnalysisFields:
    def test_empty_dict(self):
        result = validate_analysis_fields({})
        assert result["match_score"] == 50
        assert result["match_level"] == "未知"
        assert result["strengths"] == []
        assert result["gaps"] == []

    def test_partial_fields(self):
        result = validate_analysis_fields({"match_score": 85})
        assert result["match_score"] == 85
        assert result["match_level"] == "未知"  # 补全
        assert result["strengths"] == []

    def test_none_input(self):
        result = validate_analysis_fields(None)
        assert result["match_score"] == 50

    def test_existing_fields_preserved(self):
        result = validate_analysis_fields({
            "match_score": 90,
            "match_level": "优秀",
            "strengths": ["Python"],
            "gaps": ["管理经验"],
        })
        assert result["match_score"] == 90
        assert result["match_level"] == "优秀"
        assert result["strengths"] == ["Python"]
        assert result["gaps"] == ["管理经验"]


class TestValidateGenerationFields:
    def test_empty_dict(self):
        result = validate_generation_fields({})
        assert "basic_info" in result
        assert result["education"] == []
        assert result["work_experience"] == []
        assert result["skills"] == []

    def test_none_input(self):
        result = validate_generation_fields(None)
        assert "basic_info" in result

    def test_existing_fields_preserved(self):
        result = validate_generation_fields({
            "basic_info": {"name": "张三"},
            "education": [{"school": "清华"}],
        })
        assert result["basic_info"]["name"] == "张三"
        assert len(result["education"]) == 1
        assert result["work_experience"] == []  # 补全
