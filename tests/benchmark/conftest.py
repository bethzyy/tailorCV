"""Benchmark 测试公共 fixtures"""
import json
import pytest
from pathlib import Path

FIXTURES_DIR = Path(__file__).parent / 'fixtures' / 'case_01_tech_writer'


def _load_json(name: str):
    path = FIXTURES_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding='utf-8'))
    return None


def _load_text(name: str):
    path = FIXTURES_DIR / name
    if path.exists():
        return path.read_text(encoding='utf-8')
    return ''


@pytest.fixture
def ai_output():
    """AI 生成的定制简历 JSON"""
    data = _load_json('ai_output.json')
    if data is None:
        pytest.skip(f"fixture not found: {FIXTURES_DIR / 'ai_output.json'}")
    return data


@pytest.fixture
def jd_text():
    """职位描述文本"""
    text = _load_text('jd_text.txt')
    if not text:
        pytest.skip(f"fixture not found: {FIXTURES_DIR / 'jd_text.txt'}")
    return text


@pytest.fixture
def original_resume():
    """原始简历 JSON"""
    data = _load_json('original_resume.json')
    if data is None:
        pytest.skip(f"fixture not found: {FIXTURES_DIR / 'original_resume.json'}")
    return data


@pytest.fixture
def jd_keywords(jd_text):
    """从 JD 中提取的关键词列表"""
    # 从 JD 文本中提取关键术语
    keywords = set()
    for line in jd_text.split('\n'):
        line = line.strip()
        # 提取括号/书名号内的关键词
        import re
        for match in re.findall(r'[（(]([^)）]+)[)）]', line):
            if '/' in match:
                separators = ['/', '、', ',', '，']
            else:
                separators = [',', '，', '、']
            for sep in separators:
                for kw in match.split(sep):
                    kw = kw.strip()
                    if len(kw) >= 2:
                        keywords.add(kw)
    return list(keywords)
