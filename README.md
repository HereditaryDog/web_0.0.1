# G-MasterToken

## 版本号

当前版本：`0.1.9`

## 项目介绍

`G-MasterToken` 是一个面向数字点卡与 Token 充值场景的 Django 商城项目。  
当前包含前台商城、用户注册登录、订单系统、商家后台、帮助中心、邮件通知、库存卡密管理，以及支付与供货接口的预留结构。

## 前后端完成程度

### 前端

- 已完成：首页、商品列表、商品详情、下单结算、订单查询、帮助中心、账号中心、密码找回
- 已完成：商家后台总览、商品管理、库存管理、订单管理、独立商家登录页
- 当前状态：基础流程可完整测试，视觉和移动端仍可继续优化

### 后端

- 已完成：用户注册/登录/找回密码/修改密码
- 已完成：商品、订单、库存卡密、发货记录、支付记录、公告、帮助文章等核心模型
- 已完成：商家后台搜索、筛选、上下架、库存导入预览、导入历史、再次购买等功能
- 已完成：卡密与发货内容应用层加密、敏感操作审计、后台可选 IP 白名单
- 已完成：上线预检命令、就绪检查接口、本地服务器运行脚本、自动同步脚本
- 当前状态：本地模拟支付可用，Stripe 真实支付第一阶段已接入，真实供应 API 仍未正式接入

## 如何使用

### 1. 本地启动

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
python manage.py migrate
python manage.py seed_demo_store
python manage.py runserver
```

上线前可执行预检：

```bash
python manage.py preflight_check
```

### 2. 默认访问地址

- 首页：`http://127.0.0.1:8000/`
- 注册：`http://127.0.0.1:8000/accounts/signup/`
- 登录：`http://127.0.0.1:8000/accounts/login/`
- 商家登录：`http://127.0.0.1:8000/accounts/merchant/login/`
- 账号中心：`http://127.0.0.1:8000/me/`
- 商家后台：`http://127.0.0.1:8000/dashboard/`

### 3. 关键配置

`.env` 至少需要关注这些字段：

```env
DJANGO_SECRET_KEY=replace-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=127.0.0.1,localhost
SITE_NAME=G-MasterToken
SITE_BASE_URL=
CARD_SECRET_KEY=
EMAIL_BACKEND=django.core.mail.backends.smtp.EmailBackend
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_HOST_USER=your@gmail.com
EMAIL_HOST_PASSWORD=your-app-password
STRIPE_SECRET_KEY=sk_test_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_CURRENCY=cny
```

说明：

- `SITE_BASE_URL`：用于密码找回邮件、提醒邮件等外部链接生成
- `CARD_SECRET_KEY`：用于卡密库存和发货内容加密，生产环境建议单独配置
- `STRIPE_SECRET_KEY`：启用真实 Stripe Checkout 所需的服务端密钥
- `STRIPE_WEBHOOK_SECRET`：用于校验 Stripe webhook，真实支付上线时建议必配
- `STRIPE_CURRENCY`：Stripe Checkout 实际结算币种，默认是 `cny`，如你的 Stripe 账户不支持可改成账户支持的币种

### 4. Stripe 真实支付接入

如果要把站点从 mock 支付切到真实 Stripe，至少需要：

```env
PAYMENT_ENABLE_MOCK_GATEWAY=false
PAYMENT_ENABLE_STRIPE_GATEWAY=true
SITE_BASE_URL=https://your-domain.example
STRIPE_SECRET_KEY=sk_live_xxx
STRIPE_WEBHOOK_SECRET=whsec_xxx
STRIPE_CURRENCY=cny
```

然后在 Stripe 后台把 webhook 指到：

```text
https://your-domain.example/webhooks/stripe/
```

建议订阅这些事件：

- `checkout.session.completed`
- `checkout.session.async_payment_succeeded`
- `checkout.session.async_payment_failed`
- `checkout.session.expired`

## 更新日志

完整记录见 [CHANGELOG.md](CHANGELOG.md)

### 0.1.9

- 全站项目名称统一调整为 `G-MasterToken`
- 新增 `verify_stripe_setup` 命令，支持直接检查 Stripe 配置与 API 连通性
- 订单详情页把长串支付标识改成独立信息块展示，并统一改名为“支付参考号 / Stripe 会话编号”
- 修复真实 Stripe Checkout 跳转链接过长导致落库失败的问题

### 0.1.8

- 首页 Hero 的按钮与搜索区重做为专用控件组，尺寸和节奏更统一
- 登录页站点名测试改为跟随实际 `SITE_NAME` 配置，避免环境相关误报
- 本地 Playwright 审查产物加入忽略规则，发布工作树更干净

### 0.1.7

- 对齐并确认本地项目与当前工作树一致
- 修复首页隐形分类筛选问题
- 修复首页 Hero 标题样式误伤订单详情页和结算页的问题

### 0.1.6

- 修复首页删除分类区后仍残留隐形筛选的问题
- 修复首页标题样式误伤订单页和结算页的问题
- 修复订单详情页和结算页长订单号挤压状态按钮区的问题
- 当前基础检查已通过

### 0.1.5

- 首页继续做减法，删掉分类快捷浏览和帮助文章入口，公告区下移到商品区后
- 关闭 `UI 调试` 面板，并把当前确认的 UI 参数正式固化
- 演示商品补充 200 / 300 美元套餐，方便展示更高价位商品
- 当前基础检查已通过

### 0.1.4

- 新增独立商家登录页，商家账号不再和普通用户账号共用登录入口
- Stripe 真实支付第一阶段接入完成，支持更完整的 Checkout / webhook 状态同步
- 结算页、环境变量与就绪检查继续补齐真实支付上线所需配置
- 当前全量测试已通过

### 0.1.3

- 统一品牌名为 `G-MasterToken`
- 首页、商品卡、页脚与关键页面视觉继续重构，并补齐更稳定的排版细节
- 新增本地 `UI 调试` 面板，可直接在浏览器里实时微调样式变量
- 当前全量测试已通过

### 0.1.2

- 商家后台新增已支付失败订单的“重试自动发货”能力
- 补库存后可直接恢复完成订单，未支付订单不会误触发重试
- 当前全量测试已通过

### 0.1.1

- 修复支付成功页串单、后台 IP 白名单绕过、发货失败回滚未支付等高优先级问题
- 新增 `TRUSTED_PROXY_IPS` 配置项，并补齐关键安全回归测试
- 修复生产模式静态资源测试异常，当前全量测试已通过

### 0.0.10

- 新增服务健康巡检、Quick Tunnel 恢复脚本与健康任务注册脚本
- 商品目录统一为人民币售价与美元充值面值展示
- 修复 Docker / Waitress 模式下静态资源加载问题

### 0.0.8

- 商品管理页标题区与筛选区重新分层，新增商品按钮位置更稳定
- 全站字体栈与排版细节继续优化，按钮与导航可读性更好

### 0.0.9

- 新增上线预检命令和 `/health/readiness/` 接口
- 新增 Docker / Compose 部署骨架
- 新增本地服务器模式运行脚本、自动同步脚本和 Cloudflare Tunnel 配置骨架

### 0.0.7

- 新增客服工单系统，支持用户提交工单与商家后台处理
- 继续优化后台页面自适应布局，减少中等宽度下的拥挤和溢出
- 重写 README，保留版本号、更新日志、项目介绍、完成度和使用方式

### 0.0.6

- 新增卡密与发货内容应用层加密
- 新增敏感操作审计日志
- 新增后台可选 IP 白名单
- 商家库存页、订单页、访客查单页改为默认掩码显示
- 商家邮件重发改为发送查看提醒
- 首页商品区与商品详情页继续优化，并补充更多演示商品

### 0.0.5

- 商家订单管理新增搜索、筛选和订单操作
- 商品管理新增搜索、上下架切换、库存导入预览与导入历史
- 用户中心新增订单筛选、再次购买、复制订单号
- 商品支持自定义低库存提醒阈值

### 0.0.4

- 新增密码找回、重置密码、修改密码完整链路
- 新增账号中心入口与账号资料展示
- 修复注册验证码发送失败后的冷却记录残留问题

### 0.0.3

- 登录页验证码点击刷新
- 注册页邮箱验证码发送倒计时
- 新增客服与售后支持页面
