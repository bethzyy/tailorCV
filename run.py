#!/usr/bin/env python
"""
统一启动入口（工具选择器）

访问: http://localhost:5000
点击按钮时按需启动对应服务。
"""

import logging
import subprocess
import sys
import time
import atexit
import threading
import os
import signal
from flask import Flask, render_template, jsonify, request
from pathlib import Path
from functools import wraps

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 全局状态
server_processes = {}
server_status = {
    'simple': {'running': False, 'port': 5001, 'script': 'run_simple.py'},
    'multi': {'running': False, 'port': 5002, 'script': 'run_multi.py'}
}


def require_auth(f):
    """访问控制装饰器 - 使用延迟导入避免循环依赖 (run.py <-> core.auth)"""
    @wraps(f)
    def decorated(*args, **kwargs):
        from core.auth import authenticate_request
        if not authenticate_request(request):
            return jsonify({'status': 'error', 'message': 'Unauthorized access'}), 401
        return f(*args, **kwargs)
    return decorated


def start_server(tool_id):
    """启动指定服务"""
    if tool_id not in server_status:
        return {'status': 'error', 'message': f'Unknown tool: {tool_id}'}

    if server_status[tool_id]['running']:
        return {'status': 'already_running', 'port': server_status[tool_id]['port']}

    script = server_status[tool_id]['script']
    script_path = Path(__file__).parent / script

    if not script_path.exists():
        return {'status': 'error', 'message': f'Script not found: {script}'}

    try:
        # Windows 需要特殊处理进程组
        if sys.platform == 'win32':
            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=Path(__file__).parent,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )
        else:
            proc = subprocess.Popen(
                [sys.executable, str(script_path)],
                cwd=Path(__file__).parent,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL
            )

        server_processes[tool_id] = proc
        server_status[tool_id]['running'] = True
        logger.info(f"Started {tool_id} server (PID: {proc.pid})")

        return {'status': 'starting', 'port': server_status[tool_id]['port']}

    except Exception as e:
        logger.error(f"Failed to start {tool_id}: {e}")
        return {'status': 'error', 'message': str(e)}


def check_server_health(port, timeout=15):
    """检查服务健康状态"""
    import requests

    start = time.time()
    while time.time() - start < timeout:
        try:
            response = requests.get(f'http://localhost:{port}/api/health', timeout=1)
            if response.status_code == 200:
                return True
        except Exception:
            pass
        time.sleep(0.5)
    return False


def cleanup_processes():
    """退出时清理所有子进程（增强版）"""
    for tool_id, proc in server_processes.items():
        if proc and proc.poll() is None:
            logger.info(f"Stopping {tool_id} server (PID: {proc.pid})")
            try:
                if sys.platform == 'win32':
                    # Windows 下使用 taskkill 强制终止进程树
                    import subprocess as sp
                    sp.run(['taskkill', '/F', '/T', '/PID', str(proc.pid)],
                           capture_output=True, timeout=10)
                else:
                    proc.terminate()
                    proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                logger.warning(f"Process {tool_id} did not exit gracefully, force killing")
                proc.kill()
            except Exception as e:
                logger.error(f"Error stopping {tool_id}: {e}")
                proc.kill()


# 注册清理函数
atexit.register(cleanup_processes)


if __name__ == '__main__':
    from core.config import config

    # 更新端口配置
    server_status['simple']['port'] = config.SIMPLE_APP_PORT
    server_status['multi']['port'] = config.MULTI_APP_PORT

    # 创建工具选择器应用
    app = Flask(__name__,
                template_folder='web/templates',
                static_folder='web/static')

    app.config['SECRET_KEY'] = config.SECRET_KEY

    @app.route('/')
    @require_auth
    def index():
        """工具选择器主页"""
        return render_template('index.html')

    @app.route('/api/start/<tool_id>', methods=['POST'])
    @require_auth
    def api_start_tool(tool_id):
        """启动指定工具"""
        if tool_id not in server_status:
            return jsonify({'status': 'error', 'message': 'Unknown tool'}), 400

        result = start_server(tool_id)

        if result['status'] == 'error':
            return jsonify(result), 500

        if result['status'] == 'starting':
            # 等待服务就绪
            port = result['port']
            if check_server_health(port):
                return jsonify({
                    'status': 'ready',
                    'url': f'http://localhost:{port}'
                })
            else:
                server_status[tool_id]['running'] = False
                return jsonify({
                    'status': 'error',
                    'message': '服务启动超时，请检查日志'
                }), 500

        # already_running
        return jsonify({
            'status': 'ready',
            'url': f'http://localhost:{result["port"]}'
        })

    @app.route('/api/stop/<tool_id>', methods=['POST'])
    @require_auth
    def api_stop_tool(tool_id):
        """停止指定工具"""
        if tool_id not in server_status:
            return jsonify({'status': 'error', 'message': 'Unknown tool'}), 400

        if not server_status[tool_id]['running']:
            return jsonify({'status': 'already_stopped'})

        proc = server_processes.get(tool_id)
        if proc and proc.poll() is None:
            try:
                # 先尝试调用子服务的 shutdown 端点
                port = server_status[tool_id]['port']
                try:
                    import requests
                    requests.post(f'http://localhost:{port}/api/shutdown', timeout=2)
                except Exception:
                    pass

                # 强制终止进程
                proc.terminate()
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()

                logger.info(f"Stopped {tool_id} server")
            except Exception as e:
                logger.error(f"Failed to stop {tool_id}: {e}")
                return jsonify({'status': 'error', 'message': str(e)}), 500
            finally:
                if tool_id in server_processes:
                    del server_processes[tool_id]
                server_status[tool_id]['running'] = False

        return jsonify({'status': 'stopped'})

    @app.route('/api/status', methods=['GET'])
    @require_auth
    def api_status():
        """获取所有服务状态"""
        status = {}
        for tool_id, info in server_status.items():
            status[tool_id] = {
                'running': info['running'],
                'port': info['port'],
                'url': f'http://localhost:{info["port"]}'
            }
        return jsonify(status)

    @app.route('/api/tools')
    @require_auth
    def get_tools():
        """获取可用工具列表"""
        return {
            'tools': [
                {
                    'id': 'simple',
                    'name': '简版工具',
                    'description': '单模型快速生成，适合日常使用',
                    'url': f'http://localhost:{config.SIMPLE_APP_PORT}',
                    'provider': '智谱AI'
                },
                {
                    'id': 'multi',
                    'name': '多模型工具',
                    'description': '多模型并行生成，结果对比',
                    'url': f'http://localhost:{config.MULTI_APP_PORT}',
                    'providers': ['智谱AI', '阿里云']
                }
            ]
        }

    @app.route('/api/shutdown', methods=['POST'])
    @require_auth
    def api_shutdown():
        """关闭工具选择器服务器"""
        def shutdown():
            time.sleep(1)  # 等待响应发送
            os.kill(os.getpid(), signal.SIGTERM)

        threading.Thread(target=shutdown, daemon=True).start()
        logger.info("Shutting down tool selector server...")
        return jsonify({'status': 'shutting_down'})

    port = config.HUB_APP_PORT

    print(f"\n{'='*50}")
    print(f"  tailorCV 工具选择器")
    print(f"  访问地址: http://localhost:{port}")
    print(f"{'='*50}")
    print(f"\n  可用工具 (点击按钮自动启动):")
    print(f"    - 简版工具: 端口 {config.SIMPLE_APP_PORT}")
    print(f"    - 多模型工具: 端口 {config.MULTI_APP_PORT}")
    print(f"{'='*50}\n")

    try:
        # use_reloader=False 防止子服务启动时触发主服务重载
        app.run(host='0.0.0.0', port=port, debug=True, threaded=True, use_reloader=False)
    finally:
        cleanup_processes()
