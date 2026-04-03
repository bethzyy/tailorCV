# tailorCV 认证与安全系统改进方案

## Context

当前 tailorCV 的认证系统是手写的轻量实现（邮箱验证码登录 + Flask 原生 session），作为 MVP 演示够用，但商业化上线前存在多个安全漏洞：SECRET_KEY 硬编码、无 CSRF 保护、CORS 全开、Cookie 缺少安全属性、无安全响应头。同时纯验证码登录的体验在商业化场景下不够好。

本方案采用**三阶段渐进式改进**，最小改动原则，不引入 ORM 迁移，不引入 Redis，优先利用已安装的库。

---

## 第一阶段：紧急安全修复（1-2天）

> 目标：堵住 P0 安全漏洞，不改变现有功能和用户体验。

### 1.1 SECRET_KEY 安全处理

**文件**: `core/config.py` (第123行), `apps/simple_app.py`

- `config.py`: SECRET_KEY 默认值改为空字符串 `''`
- `simple_app.py` 启动时检测：如果为空则自动生成随机 key 并打印警告
- 生产环境（`FLASK_ENV=production`）如果为空则拒绝启动

### 1.2 收紧 CORS 配置

**文件**: `core/config.py`, `apps/simple_app.py` (第64行)

- `config.py` 添加 `CORS_ORIGINS` 配置项（环境变量，逗号分隔）
- `simple_app.py`: 有配置则用白名单，无配置则只允许 `localhost/127.0.0.1`

### 1.3 Cookie 安全属性

**文件**: `apps/simple_app.py`

在 `create_app()` 中设置：
- `SESSION_COOKIE_HTTPONLY = True`
- `SESSION_COOKIE_SAMESITE = 'Lax'`
- `SESSION_COOKIE_SECURE = True`（仅 production 环境）

### 1.4 安全响应头

**文件**: `apps/simple_app.py`

用 `@app.after_request` 添加：
- `X-Content-Type-Options: nosniff`
- `X-Frame-Options: DENY`
- `X-XSS-Protection: 1; mode=block`
- `Referrer-Policy: strict-origin-when-cross-origin`
- `Content-Security-Policy`（宽松模式，允许 inline style/script，因为当前 HTML 大量使用）

### 1.5 CSRF 保护（double-submit cookie，零依赖）

**文件**: `apps/simple_app.py`, `web/templates/simple/index.html`

后端：
- GET 响应时通过 `set_cookie` 写入 `csrf_token`
- 新增 `csrf_protected` 装饰器，验证 POST 请求的 `X-CSRF-Token` header 与 cookie 一致
- 替换 `login_required` 为 `login_required + csrf_protected` 组合

前端：
- 封装 `getCsrfToken()` 从 cookie 读取 token
- 所有 `fetch` POST 请求添加 `X-CSRF-Token` header
- 封装统一的 `postJSON(url, data)` 工具函数

**选型理由**：Flask-WTF 太重（需要表单类），double-submit cookie 与当前 fetch API 模式完美匹配，零依赖。

---

## 第二阶段：认证增强（2-3天）

> 目标：增加密码登录选项，加强验证码安全。

### 2.1 密码登录支持

**文件**: `core/auth.py`, `core/database.py`, `apps/simple_app.py`, `web/templates/simple/index.html`

数据库：
- `_init_tables()` 中检测 `password_hash` 列是否存在，不存在则 `ALTER TABLE` 添加
- 无需 ORM，手写迁移

`core/auth.py` 新增函数：
- `hash_password(password)` — PBKDF2 哈希（Python 标准库，零依赖）
- `verify_password(password, password_hash)` — 验证密码
- `set_password(user_id, password)` — 设置/修改密码
- `login_with_password(email, password)` — 密码登录

`apps/simple_app.py` 新增路由：
- `POST /api/auth/set-password` — 登录后设置密码（需 `login_required`）
- `POST /api/auth/login-password` — 密码登录（限流 5次/分钟）

前端 UI：
- 登录弹窗增加「验证码登录」和「密码登录」两个 tab
- 验证码登录成功后，如果用户未设密码，提示"设置密码以便下次快速登录"

### 2.2 验证码存储接口抽象

**文件**: `core/auth.py`

- 定义 `CodeStore` 抽象基类（`set/get/delete`）
- 实现 `MemoryCodeStore` 替换当前的 `_verification_codes` dict
- 添加过期条目自动清理（解决内存泄漏）
- 未来需要 Redis 时只需实现 `RedisCodeStore`

### 2.3 验证码 IP 频率限制

**文件**: `core/auth.py`, `apps/simple_app.py`

- `auth.py` 新增 `check_ip_rate_limit(ip)` — 同一 IP 每小时最多发 5 次验证码
- `simple_app.py` 的 `api_send_code` 路由中调用

---

## 第三阶段：生产化准备（3-5天）

> 目标：支付安全加固，审计日志。

### 3.1 支付回调签名验证

**文件**: `core/payment.py`

- 实现 `_verify_notify_signature()` 和 `_decrypt_notify()`
- 使用 `wechatpayv3` SDK 的验签工具

### 3.2 安全审计日志

**文件**: `core/auth.py`

- 登录成功/失败、密码设置/修改、支付操作记录审计日志
- 写入文件（`storage/logs/audit.log`），不影响主数据库性能

### 3.3 文件上传安全加固

**文件**: `apps/simple_app.py`

- 模板上传验证文件确实是 ZIP 格式（docx 本质是 ZIP）
- 限制上传文件大小

---

## 不做的事情（及原因）

| 不做 | 原因 |
|------|------|
| 迁移到 Flask-Login | 手写方案够用，迁移成本高收益低 |
| 引入 Redis | 单进程部署，内存够用，已有接口抽象 |
| 引入 Flask-WTF 做 CSRF | 依赖太重，double-submit cookie 更轻量 |
| OAuth/第三方登录 | 开发量大，当前用户量不需要 |
| CSP 严格模式 | 当前 HTML 全是 inline style，会破坏页面 |

---

## 改动文件清单

| 文件 | 阶段 | 改动内容 |
|------|------|----------|
| `core/config.py` | 1 | SECRET_KEY 处理、CORS_ORIGINS 配置 |
| `apps/simple_app.py` | 1+2 | CSRF 保护、CORS 收紧、Cookie 安全、安全头、密码登录路由 |
| `web/templates/simple/index.html` | 1+2 | CSRF token 传递、密码登录 tab、设置密码提示 |
| `core/auth.py` | 2 | 密码函数、验证码存储抽象、IP 限流、审计日志 |
| `core/database.py` | 2 | password_hash 列迁移 |
| `core/payment.py` | 3 | 支付签名验证 |

---

## 验证方式

### 第一阶段验证
1. 启动应用，确认无报错
2. 检查响应头是否包含安全头（浏览器 F12 → Network → 查看任意请求的 Response Headers）
3. 检查 Cookie 是否有 `HttpOnly` 和 `SameSite=Lax` 属性
4. 测试跨域请求被拒绝（用另一个端口或域名调用 API）
5. 测试不带 CSRF token 的 POST 请求返回 403
6. 测试正常登录流程不受影响

### 第二阶段验证
1. 验证码登录 → 成功 → 提示设置密码 → 设置密码 → 退出 → 密码登录 → 成功
2. 未设密码的用户用密码登录 → 失败
3. 同一 IP 发送 6 次验证码 → 第 6 次被拒绝
4. 重启应用后验证码存储正常工作（MemoryCodeStore 自动清理过期条目）

### 第三阶段验证
1. 沙箱模式下模拟支付流程正常
2. 检查 `storage/logs/audit.log` 是否记录了登录/支付操作
