---
title: 示例用户登录与身份认证规格
module: Auth_Demo
tags: [Auth, Token, SSO, Mock]
version: 1.0.0
status: Active
source: demo
owner: QA
---

# 示例用户登录与身份认证规格

## 1. 功能概述

系统提供基于 OAuth2 / JWT 的统一登录认证机制。

## 2. 核心规则

1. 用户输入账号密码后，向 `/api/v1/auth/login` 发起 POST 请求；
2. 认证成功后下发 Access Token (有效期 2 小时) 与 Refresh Token (有效期 7 天)；
3. Access Token 过期时，客户端自动静默调用 `/api/v1/auth/refresh` 刷新，用户无感知；
4. 连续密码错误 5 次，锁定账号 15 分钟。

## 3. 性能与边界

- 登录响应时间 SLA: P95 < 500ms
- 并发登录支持: 1000 QPS
