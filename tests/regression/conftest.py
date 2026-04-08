"""AI 质量回归测试公共 fixtures — 支持多场景参数化"""
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / 'fixtures'

# 所有回归场景定义
ALL_CASES = [
    "case_01_tech_writer",
    "case_02_frontend_dev",
    "case_03_fresh_grad",
    "case_04_product_manager",
    "case_05_career_change",
]


def _load_case_data(case_name):
    """加载测试场景数据"""
    case_dir = FIXTURES_DIR / case_name
    input_path = case_dir / 'input.json'
    expected_path = case_dir / 'expected.json'

    if not input_path.exists() or not expected_path.exists():
        return None, None

    return (
        json.loads(input_path.read_text(encoding='utf-8')),
        json.loads(expected_path.read_text(encoding='utf-8')),
    )


def _load_ai_output(case_name):
    """加载场景对应的 AI 输出样例（如果存在）"""
    output_path = FIXTURES_DIR / case_name / 'output.json'
    if output_path.exists():
        return json.loads(output_path.read_text(encoding='utf-8'))
    return None


# 每个场景的独立 fixture（向后兼容）
@pytest.fixture
def case_tech_writer():
    """技术岗位场景数据"""
    # 兼容旧名称: 优先尝试 case_01_tech_writer，回退到 case_tech_writer
    input_data, expected = _load_case_data('case_01_tech_writer')
    if input_data is None:
        input_data, expected = _load_case_data('case_tech_writer')
    if input_data is None:
        pytest.skip("tech_writer fixtures not found")
    return input_data, expected


@pytest.fixture
def case_frontend_dev():
    """前端开发场景数据"""
    input_data, expected = _load_case_data('case_02_frontend_dev')
    if input_data is None:
        pytest.skip("case_02_frontend_dev fixtures not found")
    return input_data, expected


@pytest.fixture
def case_fresh_grad():
    """应届生场景数据"""
    input_data, expected = _load_case_data('case_03_fresh_grad')
    if input_data is None:
        pytest.skip("case_03_fresh_grad fixtures not found")
    return input_data, expected


@pytest.fixture
def case_product_manager():
    """产品经理场景数据"""
    input_data, expected = _load_case_data('case_04_product_manager')
    if input_data is None:
        pytest.skip("case_04_product_manager fixtures not found")
    return input_data, expected


@pytest.fixture
def case_career_change():
    """转行场景数据"""
    input_data, expected = _load_case_data('case_05_career_change')
    if input_data is None:
        pytest.skip("case_05_career_change fixtures not found")
    return input_data, expected


# 参数化 fixture — 用于批量运行所有场景
@pytest.fixture(params=ALL_CASES)
def regression_case(request):
    """参数化回归场景，自动遍历所有 case"""
    input_data, expected = _load_case_data(request.param)
    if input_data is None:
        pytest.skip(f"{request.param} fixtures not found")
    return {
        "case_name": request.param,
        "input": input_data,
        "expected": expected,
    }
