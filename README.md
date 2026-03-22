# web_0.0.1

一个面向点卡和 Token 充值场景的 Django 商城工作区，已包含：

- 前台首页、商品详情、下单、支付页、订单详情
- 用户注册登录
- 商品、库存卡密、订单、支付记录、发货记录数据库模型
- 自定义商家后台总览、商品管理、库存卡密管理、订单管理
- Django Admin 管理后台
- Stripe 支付预留接入
- 合作 API 自动供货抽象层
- SQLite / PostgreSQL 双数据库配置
- Windows 生产启动脚本
- 自动化测试

## 启动方式

```powershell
cd C:\Users\Administrator\Desktop\web_test
.venv\Scripts\activate
copy .env.example .env
python manage.py makemigrations
python manage.py migrate
python manage.py seed_demo_store
python manage.py createsuperuser
python manage.py runserver
```

也可以直接运行：

```powershell
.\Start-WebStore.ps1
```

## 默认业务流

1. 用户注册或登录
2. 进入商品详情页并下单
3. 如果没配置 Stripe，则进入本地模拟支付
4. 支付成功后系统自动发货
5. 用户在订单详情中查看卡密或 Token 兑换码
6. 商家通过 `/dashboard/` 或 `/admin/` 管理商品、库存和订单

## 已准备好的本地账号

- 商家管理员：`owner`
- 密码：`ChangeMe123!`

你也可以继续在前台注册普通买家账号做下单测试。

## 数据库切换

默认使用 SQLite，本地直接可跑。

如果要切到 PostgreSQL，只需要在 `.env` 中修改：

```env
DATABASE_ENGINE=postgres
DATABASE_NAME=web_store
DATABASE_USER=postgres
DATABASE_PASSWORD=your-password
DATABASE_HOST=127.0.0.1
DATABASE_PORT=5432
```

然后执行：

```powershell
python manage.py migrate
```

## 生产启动

开发环境：

```powershell
.\Start-WebStore.ps1
```

生产环境（Windows + Waitress）：

```powershell
.\Start-WebStore-Prod.ps1
```

如果你要走 HTTPS 反向代理，请把这些环境变量改成 `true`：

```env
DJANGO_SECURE_SSL_REDIRECT=true
DJANGO_SESSION_COOKIE_SECURE=true
DJANGO_CSRF_COOKIE_SECURE=true
DJANGO_SECURE_HSTS_SECONDS=31536000
DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS=true
DJANGO_SECURE_HSTS_PRELOAD=true
```

## 真实对接时建议

- 把 SQLite 切换到 PostgreSQL
- 在 `shop/services/payment.py` 中补充正式支付渠道
- 在 `shop/services/supplier.py` 中替换成真实合作平台接口
- 对卡密做加密存储和审计日志
