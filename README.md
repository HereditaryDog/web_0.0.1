# web_0.0.1

当前版本：`0.0.5`

一个面向数字点卡与 Token 充值场景的 Django 商城项目，包含前台商城、订单系统、用户认证、商家后台、帮助中心、支付抽象层和供货接口抽象层。

## 亮点

- 苹果官网风格方向的首页布局，适合继续做品牌化前台展示
- 用户注册支持邮箱验证码，登录支持用户名或邮箱 + 密码 + 人机验证码
- 支付层已抽象成多网关结构，预留 `Stripe`、`支付宝`、`微信支付`、`USDT`、`银行卡转账`
- 订单、库存卡密、支付记录、发货记录、帮助文章、公告都已建模
- 商家后台已具备商品管理、库存导入、订单查看能力
- 帮助中心、公告详情、游客订单查询都已接入前台
- 数据库支持 `SQLite` 和 `PostgreSQL` 切换
- 已包含自动化测试，便于继续开发和迭代

## 当前能力

### 前台

- 首页商品展示
- 商品详情页
- 订单结算页
- 订单查询页
- 帮助中心
- 公告详情页

### 用户系统

- 注册：用户名、邮箱地址、手机号、邮箱验证码、密码
- 登录：账号（用户名或邮箱）、密码、人机验证码
- 邮箱验证状态记录

### 商家后台

- 商品管理
- 库存卡密导入
- 订单管理
- Django Admin 后台

### 支付与供货

- 默认可用：模拟支付
- 已接入：Stripe 结构
- 已预留：支付宝、微信支付、USDT、银行卡转账
- 供货方式：库存卡密 / 合作 API

## 技术栈

- Python 3.11
- Django 5
- SQLite / PostgreSQL
- Waitress
- Stripe SDK

## 目录结构

```text
accounts/     用户、认证、邮箱验证码、登录逻辑
config/       项目配置、版本号、全局设置
shop/         商城模型、订单流、支付服务、供货服务
templates/    前台页面和后台页面模板
static/       样式资源
```

## 本地启动

```powershell
cd C:\Users\Administrator\Desktop\web_test
.venv\Scripts\activate
copy .env.example .env
python manage.py migrate
python manage.py seed_demo_store
python manage.py runserver
```

也可以直接运行：

```powershell
.\Start-WebStore.ps1
```

本地访问：

- 首页：`http://127.0.0.1:8000/`
- 注册：`http://127.0.0.1:8000/accounts/signup/`
- 登录：`http://127.0.0.1:8000/accounts/login/`
- 商家后台：`http://127.0.0.1:8000/dashboard/`

## 环境变量

核心配置在 `.env` 中完成。

### 基础

```env
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
SITE_NAME=web_0.0.1
SITE_BASE_URL=
```

`SITE_BASE_URL` 用于密码重置邮件、通知邮件等需要生成外部可访问链接的场景。
本地开发不填也可以；如果要让手机或外部设备打开邮件里的链接，需要配置成你的局域网地址或正式域名，例如 `http://192.168.1.8:8010` 或 `https://example.com`。

### 邮件

```env
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
DEFAULT_FROM_EMAIL=your@gmail.com
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
EMAIL_USE_TLS=true
EMAIL_USE_SSL=false
EMAIL_TIMEOUT=20
EMAIL_CODE_EXPIRY_MINUTES=10
EMAIL_CODE_COOLDOWN_SECONDS=60
```

### 数据库

SQLite 默认可直接使用。

如果切换到 PostgreSQL：

```env
DATABASE_ENGINE=postgres
DATABASE_NAME=web_store
DATABASE_USER=postgres
DATABASE_PASSWORD=your-password
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
DATABASE_CONN_MAX_AGE=60
```

### 支付通道开关

```env
PAYMENT_ENABLE_MOCK_GATEWAY=true
PAYMENT_ENABLE_STRIPE_GATEWAY=true
PAYMENT_ENABLE_ALIPAY_GATEWAY=false
PAYMENT_ENABLE_WECHAT_GATEWAY=false
PAYMENT_ENABLE_USDT_GATEWAY=false
PAYMENT_ENABLE_BANK_GATEWAY=false
```

## 部署方式

### 开发环境

```powershell
.\Start-WebStore.ps1
```

### Windows 生产环境

```powershell
.\Start-WebStore-Prod.ps1
```

生产脚本会自动执行：

- `collectstatic`
- `migrate`
- `waitress-serve`

### 推荐生产部署方案

1. 使用 `PostgreSQL` 替换 SQLite
2. 使用反向代理提供 HTTPS
3. 开启安全相关环境变量
4. 配置真实 SMTP 发信
5. 补真实支付网关和合作 API 接口

建议开启的安全环境变量：

```env
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true
DJANGO_SECURE_HSTS_PRELOAD=true
```

## 更新日志

完整记录见 [CHANGELOG.md](CHANGELOG.md)

### 0.0.5

- 新增商家订单管理搜索、筛选和订单操作
- 新增商品搜索、上下架切换、库存导入预览与导入历史
- 新增用户中心订单筛选、再次购买、复制订单号
- 商品支持自定义低库存提醒阈值

### 0.0.4

- 新增密码找回、重置密码、修改密码完整链路
- 新增账号中心入口与账号资料展示
- 修复注册验证码发送失败后的冷却记录残留问题
- 优化商家后台总览的统计卡片与最近订单布局
- 支持通过 `SITE_BASE_URL` 生成外部可访问的密码重置链接

### 0.0.3

- 登录页支持点击刷新验证码
- 注册页发送邮箱验证码支持倒计时
- 新增客服与售后支持页面

### 0.0.2

- 重做首页视觉，风格更接近苹果官网方向
- 新增多支付网关抽象，预留支付宝、微信、USDT、银行卡
- 注册改成邮箱验证码流程
- 登录支持用户名或邮箱 + 密码 + 人机验证码
- 接入 Gmail SMTP 发信

### 0.0.1

- 初始化商城工作区
- 完成商品、订单、库存卡密、支付记录、发货记录模型
- 完成前台商城、商家后台、帮助中心、公告和订单查询
- 完成基础测试和 GitHub 首次发布

## 后续建议

- 接真实支付渠道
- 接真实合作 API 发货
- 加客服页面、售后规则、推广分站模块
- 加发布流水线和 GitHub Release 流程
