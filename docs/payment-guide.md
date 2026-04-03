# 支付系统接入指南

## 架构概览

采用 **Provider 模式**，统一接口对接多个支付渠道，方便扩展。

```
core/payment/
├── __init__.py      # 统一入口（对外接口 + provider 注册）
├── base.py          # BasePaymentProvider 抽象基类
├── alipay.py        # 支付宝当面付（主力）
└── wechat.py        # 微信支付（预留）
```

### 统一对外接口

| 函数 | 说明 |
|------|------|
| `create_payment(user_id, plan_type, provider_id)` | 创建支付订单 |
| `handle_payment_notify(request, provider_id)` | 处理支付回调 |
| `query_payment(order_no)` | 查询支付状态 |
| `simulate_payment(order_no)` | 模拟支付（沙箱） |
| `get_available_providers()` | 获取可用支付方式列表 |

### API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/payment/plans` | GET | 获取套餐列表 |
| `/api/payment/providers` | GET | 获取可用支付方式 |
| `/api/payment/create` | POST | 创建支付订单 |
| `/api/payment/query/<order_no>` | GET | 查询支付状态 |
| `/api/payment/notify/alipay` | POST | 支付宝回调 |
| `/api/payment/notify/wechat` | POST | 微信支付回调 |
| `/api/payment/simulate` | POST | 模拟支付（沙箱） |

### 添加新支付方式

只需两步：

1. 在 `core/payment/` 下新建文件，继承 `BasePaymentProvider`，实现 4 个方法
2. 在 `core/payment/__init__.py` 的 `_providers` 字典中注册

```python
# core/payment/stripe.py
class StripeProvider(BasePaymentProvider):
    provider_id = 'stripe'
    provider_name = 'Stripe'

    def create_qr_order(self, order_no, amount, description): ...
    def query_order(self, order_no): ...
    def verify_notify(self, request): ...
    def is_available(self): ...
```

---

## 一、支付宝当面付接入

### 1. 注册支付宝开放平台

- 网址：https://open.alipay.com
- 资质要求：**个人可申请**（无需营业执照）
- 注册开发者账号 → 完成实名认证

### 2. 创建应用 + 签约当面付

1. 进入「控制台」→「我的应用」→「创建应用」
2. 添加能力：「当面付」
3. 提交审核（1-3 个工作日）
4. 审核通过后完成签约

### 3. 配置密钥

在「应用详情」→「开发设置」中：

| 配置项 | 说明 |
|--------|------|
| APPID | 应用唯一标识 |
| 接口加签方式 | 选择「公钥证书」或「公钥」模式 |
| 应用私钥 | 自己生成的 RSA2 私钥 |
| 支付宝公钥 | 从支付宝平台获取 |

生成密钥对：
```bash
# 使用支付宝密钥工具或 OpenSSL
openssl genrsa -out app_private_key.pem 2048
# 将公钥上传到支付宝平台，获取支付宝公钥
```

### 4. 配置 .env

```env
# 默认支付方式
DEFAULT_PAYMENT_PROVIDER=alipay

# 支付宝当面付
ALIPAY_APP_ID=你的AppID
ALIPAY_PRIVATE_KEY_PATH=./certs/alipay_private_key.pem
ALIPAY_PUBLIC_KEY_PATH=./certs/alipay_public_key.pem
ALIPAY_NOTIFY_URL=https://yourdomain.com/api/payment/notify/alipay
ALIPAY_SANDBOX=false
```

### 5. 沙箱调试

支付宝提供官方沙箱环境，无需真实签约即可测试完整流程：

1. 登录支付宝开放平台 → 「沙箱」
2. 获取沙箱 APPID、密钥
3. 下载「支付宝沙箱版」App（Android）
4. 配置 `.env`：`ALIPAY_SANDBOX=true`
5. 用沙箱 App 扫码支付（自动到账）

### 6. 开发调试

```bash
# 使用内网穿透
cpolar http 6001
# 获取公网 URL: https://xxxx.cpolar.cn

# 更新 .env
ALIPAY_NOTIFY_URL=https://xxxx.cpolar.cn/api/payment/notify/alipay
```

### 7. 测试步骤

1. 启动服务
2. 前端选择套餐 → 选择「支付宝」→ 点击购买
3. 弹出支付宝二维码
4. 用支付宝（或沙箱 App）扫码支付
5. 确认回调正常处理，套餐自动激活

---

## 二、微信支付接入（预留）

### 当前状态

代码已就绪（`core/payment/wechat.py`），但签名验证和回调解密标记为 TODO。
需微信商户号后才能正式使用。

### 前置条件

| 条件 | 说明 |
|------|------|
| 微信商户号 | https://pay.weixin.qq.com 注册（需营业执照或小微商户） |
| 关联的公众号/小程序 | 获取 APP_ID |
| API v3 密钥 | 商户平台手动设置（32位字符串） |
| 商户证书 | 商户平台下载证书工具生成 |
| 公网 HTTPS 域名 | 回调通知需要（可用内网穿透） |

### 配置 .env

```env
# 微信支付
WECHAT_APP_ID=wx1234567890
WECHAT_MCH_ID=1234567890
WECHAT_API_KEY_V3=your_api_v3_key_32chars
WECHAT_CERT_PATH=./certs/apiclient_key
WECHAT_KEY_PATH=./certs/apiclient_key.pem
WECHAT_NOTIFY_URL=https://yourdomain.com/api/payment/notify/wechat
WECHAT_SANDBOX=false
```

### 待完成项

- [ ] `core/payment/wechat.py:verify_notify()` — 签名验证
- [ ] `core/payment/wechat.py:verify_notify()` — 回调数据解密

---

## 三、数据库

### orders 表结构

```sql
CREATE TABLE orders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    order_no TEXT UNIQUE NOT NULL,          -- 订单号 (TCV{时间戳}{随机})
    user_id INTEGER NOT NULL,               -- 用户ID
    plan_type TEXT NOT NULL,                -- 套餐类型
    plan_name TEXT NOT NULL,                -- 套餐名称
    amount REAL NOT NULL,                   -- 金额（元）
    status TEXT DEFAULT 'pending',           -- pending / paid
    provider TEXT DEFAULT '',               -- 支付渠道 (alipay/wechat)
    transaction_id TEXT DEFAULT '',          -- 第三方交易号（通用）
    wechat_transaction_id TEXT,             -- 微信交易号（兼容旧数据）
    paid_at TIMESTAMP,                      -- 支付时间
    expires_at TIMESTAMP,                   -- 过期时间（30分钟）
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

---

## 四、套餐配置

在 `core/config.py` 中定义：

| 套餐 | 价格 | 配额 | 日上限 |
|------|------|------|--------|
| 免费体验 | 0 | 1 次 | 1 次 |
| 按次包 | 9.9 元 | 5 次 | 5 次 |
| 月卡 | 29.9 元 | 无限 | 10 次/天 |
| 季卡 | 59.9 元 | 无限 | 20 次/天 |

---

## 五、注意事项

- 支付宝回调返回纯文本 `success`/`fail`，微信回调返回 JSON
- 订单 30 分钟未支付自动过期
- 支付宝金额单位为**元**，微信支付金额单位为**分**（provider 内部已处理）
- 回调端点不需要登录即可访问（无 `@login_required`）
- 生产环境必须验证回调签名，防止伪造通知
- 二维码由前端 `qrcode.js` 生成，后端只返回 `code_url` 字符串

---

*Last updated: 2026-04-02*
