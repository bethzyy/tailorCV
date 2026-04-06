"""模拟用户请求复现 KeyError('"name"') 错误"""
import requests
import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

url = 'http://localhost:6003/api/tailor/file'

files = {
    'resume': (
        'test_resume.docx',
        open('templates/extracted/c3d6868643fdf645.docx', 'rb'),
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document'
    )
}

data = {
    'jd_text': '招聘高级Python开发工程师，要求3年以上经验，熟悉Django/Flask，有分布式系统经验优先。',
    'template_mode': 'selected',
    'template_id': 'c3d6868643fdf645',
    'no_cache': 'true',
}

print('发送请求...')
try:
    resp = requests.post(url, files=files, data=data, timeout=180)
    print(f'状态码: {resp.status_code}')
    result = resp.json()
    if resp.status_code == 200:
        print(f'成功! template_used: {result.get("template_used")}')
    else:
        error = result.get('error', '')
        error_type = result.get('error_type', '')
        traceback_str = result.get('traceback', '')
        print(f'错误: {error}')
        print(f'error_type: {error_type}')
        if traceback_str:
            print(f'\n===== TRACEBACK =====')
            print(traceback_str)
            print(f'===== END =====')
        else:
            print('无 traceback 字段')
except Exception as e:
    print(f'请求异常: {type(e).__name__}: {e}')
    import traceback
    traceback.print_exc()
