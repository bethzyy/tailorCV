"""
Qwen (Alibaba DashScope) 连通性诊断脚本

逐步诊断连接失败的原因：
1. API Key 加载
2. DNS 解析
3. TCP 连接
4. HTTPS 请求
5. 模型调用

用法: python tests/test_qwen_connectivity.py
"""

import os
import sys
import socket
import time
import ssl
from pathlib import Path
from urllib.request import urlopen, Request
from urllib.error import URLError

# 项目根目录
ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

BASE_URL = 'https://coding.dashscope.aliyuncs.com/v1'
HOSTNAME = 'coding.dashscope.aliyuncs.com'
API_KEY_PATH = r'C:\D\CAIE_tool\LLM_Configs\ali\apikey.txt'


def step(msg):
    print(f"\n{'='*60}")
    print(f"  {msg}")
    print(f"{'='*60}")


def ok(msg):
    print(f"  [OK] {msg}")


def fail(msg):
    print(f"  [FAIL] {msg}")


def info(msg):
    print(f"  [INFO] {msg}")


def test_api_key():
    step("Step 1: API Key 加载")

    # 环境变量
    env_key = os.getenv('ALIBABA_API_KEY', '')
    if env_key:
        ok(f"环境变量 ALIBABA_API_KEY 已设置 (长度={len(env_key)})")
    else:
        info("环境变量 ALIBABA_API_KEY 未设置")

    # 文件
    key_path = Path(API_KEY_PATH)
    if key_path.exists():
        file_key = key_path.read_text(encoding='utf-8').strip()
        if file_key:
            ok(f"API Key 文件存在 (路径={API_KEY_PATH}, 长度={len(file_key)})")
            return file_key
        else:
            fail(f"API Key 文件为空 (路径={API_KEY_PATH})")
            return None
    else:
        fail(f"API Key 文件不存在 (路径={API_KEY_PATH})")
        return None


def test_dns():
    step("Step 2: DNS 解析")

    try:
        start = time.time()
        addrs = socket.getaddrinfo(HOSTNAME, 443, socket.AF_INET, socket.SOCK_STREAM)
        elapsed = (time.time() - start) * 1000
        if addrs:
            ip_list = [addr[4][0] for addr in addrs[:3]]
            ok(f"DNS 解析成功 ({elapsed:.0f}ms): {', '.join(ip_list)}")
            return True
        else:
            fail("DNS 解析返回空结果")
            return False
    except socket.gaierror as e:
        fail(f"DNS 解析失败: {e}")
        return False
    except Exception as e:
        fail(f"DNS 解析异常: {e}")
        return False


def test_tcp():
    step("Step 3: TCP 连接 (端口 443)")

    try:
        start = time.time()
        sock = socket.create_connection((HOSTNAME, 443), timeout=10)
        elapsed = (time.time() - start) * 1000
        sock.close()
        ok(f"TCP 连接成功 ({elapsed:.0f}ms)")
        return True
    except socket.timeout:
        fail("TCP 连接超时 (10s)")
        return False
    except ConnectionRefusedError:
        fail("TCP 连接被拒绝")
        return False
    except OSError as e:
        fail(f"TCP 连接失败: {e}")
        return False


def test_https():
    step("Step 4: HTTPS 请求 (/v1/models)")

    url = f"{BASE_URL}/models"
    try:
        start = time.time()
        req = Request(url, headers={'Accept': 'application/json'})
        resp = urlopen(req, timeout=15)
        elapsed = (time.time() - start) * 1000
        body = resp.read().decode('utf-8')
        ok(f"HTTPS 请求成功 ({elapsed:.0f}ms, status={resp.status}, body长度={len(body)})")
        # 显示前 200 字符
        info(f"响应前200字符: {body[:200]}")
        return True
    except ssl.SSLError as e:
        fail(f"SSL 错误: {e}")
        return False
    except URLError as e:
        fail(f"URL 错误: {e}")
        return False
    except Exception as e:
        fail(f"HTTPS 请求异常: {e}")
        return False


def test_model_call(api_key):
    step("Step 5: 实际模型调用 (qwen3.5-plus)")

    if not api_key:
        fail("无 API Key，跳过模型调用测试")
        return False

    try:
        from openai import OpenAI
        client = OpenAI(
            api_key=api_key,
            base_url=BASE_URL
        )

        start = time.time()
        response = client.chat.completions.create(
            model='qwen3.5-plus',
            messages=[{"role": "user", "content": "你好，请用一句话介绍你自己"}],
            max_tokens=100,
            temperature=0.3
        )
        elapsed = (time.time() - start) * 1000

        content = response.choices[0].message.content
        tokens = response.usage.total_tokens if response.usage else 0

        ok(f"模型调用成功 ({elapsed:.0f}ms, tokens={tokens})")
        info(f"回复: {content[:200]}")
        return True

    except ImportError:
        fail("openai 包未安装，请运行: pip install openai")
        return False
    except Exception as e:
        fail(f"模型调用失败: {e}")
        return False


def main():
    print("Qwen (Alibaba DashScope) 连通性诊断")
    print(f"目标: {BASE_URL}")
    print(f"主机: {HOSTNAME}")

    results = {}

    # Step 1: API Key
    api_key = test_api_key()
    results['api_key'] = bool(api_key)

    # Step 2: DNS
    results['dns'] = test_dns()

    # Step 3: TCP
    results['tcp'] = test_tcp()

    # Step 4: HTTPS (无认证)
    results['https'] = test_https()

    # Step 5: 模型调用 (有认证)
    results['model'] = test_model_call(api_key)

    # 汇总
    step("诊断汇总")
    for name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"  [{status}] {name}")

    failed = [name for name, passed in results.items() if not passed]
    if failed:
        print(f"\n失败步骤: {', '.join(failed)}")
        if 'dns' in failed:
            print("建议: 检查 DNS 设置，尝试 ping coding.dashscope.aliyuncs.com")
        if 'tcp' in failed and 'dns' not in failed:
            print("建议: 检查防火墙或代理设置")
        if 'https' in failed and 'tcp' not in failed:
            print("建议: 检查 SSL/TLS 证书，尝试 python -m pip install --upgrade certifi")
        if 'model' in failed and 'https' not in failed:
            print("建议: 检查 API Key 是否有效，或端点 URL 是否正确")
    else:
        print("\n所有步骤通过，Qwen 连通性正常!")


if __name__ == '__main__':
    main()
