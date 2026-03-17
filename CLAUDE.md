# tailorCV - 智能简历定制工具

基于 AI 的智能简历定制工具，帮助求职者根据目标职位 JD 快速生成定制化简历。

## 核心原则

- **零编造**：所有生成内容必须有据可依（90%+依据覆盖）
- **依据追踪**：透明的修改来源展示

## 快速启动

```bash
python run.py          # 启动工具选择器 http://localhost:5000
python run_simple.py   # 直接启动简版工具 http://localhost:5001
python run_multi.py    # 直接启动多模型工具 http://localhost:5002
```

## 架构概览

### 三层服务架构

| 服务 | 端口 | 说明 |
|------|------|------|
| 工具选择器 (run.py) | 5000 | 按需启动子服务 |
| 简版工具 (run_simple.py) | 5001 | 单模型 GLM-4.6 |
| 多模型工具 (run_multi.py) | 5002 | 多模型并行对比 |

### 核心模块

```
core/
├── config.py           # 配置管理（端口、API密钥、权重配置）
├── database.py         # SQLite 持久化
├── model_manager.py    # 单模型管理（GLM-4.6）
├── multi_model_manager.py  # 多模型管理（智谱+阿里云）
├── expert_team.py      # 单模型专家团队
├── multi_expert_team.py    # 多模型专家团队
├── resume_parser.py    # 简历解析器
├── resume_generator.py # 简历生成器
├── evidence_tracker.py # 依据追踪器
├── template_processor.py   # 模板处理器
├── structure_detector.py   # 结构检测器
└── providers/          # AI 提供商适配器
    ├── zhipu_provider.py   # 智谱AI
    └── alibaba_provider.py # 阿里云
```

### 应用入口

```
apps/
├── simple_app.py   # 简版工具 Flask 应用
└── multi_app.py    # 多模型工具 Flask 应用
```

### Web 界面

```
web/templates/
├── index.html      # 工具选择器主页
├── simple/         # 简版工具页面
└── multi/          # 多模型工具页面
```

## 环境配置

### 必需环境变量

```bash
# .env 文件
ZHIPU_API_KEY=your_api_key_here      # 智谱AI (必需)
ALIBABA_API_KEY=your_api_key_here    # 阿里云 (可选，多模型需要)
```

### 端口配置 (core/config.py)

```python
HUB_APP_PORT = 5000      # 工具选择器
SIMPLE_APP_PORT = 5001   # 简版工具
MULTI_APP_PORT = 5002    # 多模型工具
```

## 技术栈

- **后端**: Flask 2.x
- **AI 模型**: ZhipuAI GLM-4.6 / GLM-4-flash, 阿里云 Qwen
- **文档处理**: pdfplumber, PyPDF2, python-docx
- **数据存储**: SQLite
- **模板引擎**: Jinja2

## API 端点

### 工具选择器 (端口 5000)

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/start/<tool_id>` | POST | 启动指定工具 |
| `/api/stop/<tool_id>` | POST | 停止指定工具 |
| `/api/status` | GET | 获取所有服务状态 |
| `/api/shutdown` | POST | 关闭管理器 |

### 简版/多模型工具

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/health` | GET | 健康检查 |
| `/api/tailor/file` | POST | 文件上传模式 |
| `/api/tailor/form` | POST | 引导输入模式 |
| `/api/shutdown` | POST | 关闭服务 |

## 开发注意事项

1. **端口冲突**: 如果端口被占用，检查 `netstat -an | findstr :5000`
2. **API 密钥**: 确保环境变量已设置，或 .env 文件存在
3. **子服务管理**: 工具选择器会自动管理子服务的启动和停止

---

## Version History

| Date | Change |
|------|--------|
| 2026-03-16 | 统一关闭按钮样式（工具选择器与简版工具风格一致） |
| 2026-03-16 | 添加 CLAUDE.md 项目文档 |

---

*Last updated: 2026-03-16*
