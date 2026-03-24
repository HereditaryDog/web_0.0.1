# Colleague Testing Guide

## 目标

让同事在不同地点也能访问这台测试机上的项目，并参与联调测试。

## 当前推荐访问方式

优先使用 `Tailscale` 访问。

测试地址：

- 主站首页：`http://rog-i7-2070.tailfada64.ts.net:8001/`
- 登录页：`http://rog-i7-2070.tailfada64.ts.net:8001/accounts/login/`
- 就绪检查：`http://rog-i7-2070.tailfada64.ts.net:8001/health/readiness/`

也可以直接使用 Tailscale IP：

- `http://100.75.27.67:8001/`

## 同事接入步骤

### 1. 安装 Tailscale

官网：

- [https://tailscale.com/download](https://tailscale.com/download)

### 2. 登录到同一个 Tailnet

请同事使用和当前测试网络相同的 Tailscale 账号体系登录。

### 3. 打开网站

登录成功后，在浏览器打开：

```text
http://rog-i7-2070.tailfada64.ts.net:8001/
```

### 4. 基础检查

先确认这几个页面都能打开：

- 首页
- 注册页
- 登录页
- 帮助中心
- 订单查询
- 客服支持

## GitHub 协作方式

你和同事当前共用同一个 GitHub 仓库：

- [https://github.com/HereditaryDog/web_0.0.1](https://github.com/HereditaryDog/web_0.0.1)

当前测试机已经配置：

- 每 30 分钟自动检查 `main`
- 如果有新提交，自动拉取并重启服务

这意味着：

- 同事在别的电脑开发并 push 到 GitHub 后
- 这台测试机会自动同步最新版本

## 注意事项

- 如果刚 push 完还没看到更新，最多等 30 分钟
- 也可以在测试机上手动运行：

```powershell
.\scripts\sync-and-redeploy.ps1
```

- 如果浏览器打不开页面，先检查：
  - `Tailscale` 是否已连接
  - 测试机服务是否在线
  - `health/readiness/` 是否返回正常 JSON
