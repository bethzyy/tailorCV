"""
tailorCV 一键测试运行脚本

用法:
    python tests/run_all.py
    python tests/run_all.py -v           # 详细输出
    python tests/run_all.py -k test_api_auth  # 只运行认证测试
"""

import sys
from pathlib import Path

# 确保项目根目录在 sys.path 中
PROJECT_ROOT = Path(__file__).parent.parent
sys.path.insert(0, str(PROJECT_ROOT))


def main():
    import pytest

    tests_dir = str(Path(__file__).parent)
    args = [tests_dir, '-v', '--tb=short']
    args.extend(sys.argv[1:])

    exit_code = pytest.main(args)

    if exit_code == 0:
        print("\n" + "=" * 50)
        print("All tests passed!")
        print("=" * 50)
    else:
        print("\n" + "=" * 50)
        print(f"Tests failed with exit code {exit_code}")
        print("=" * 50)

    return exit_code


if __name__ == '__main__':
    sys.exit(main())
