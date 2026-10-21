---
title: 示例用户登录基线测试用例
module: Auth_Demo
tags: [Auth, P0, MockCases]
version: 1.0.0
status: Active
source: demo
owner: QA
---

# 示例用户登录基线测试用例

| case_id | module | requirement_id | version | title | priority | type | preconditions | test_data | steps | expected_result | dynamic_assertion | regression_guard | source_role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-AUTH-001** | Auth_Demo | REQ-AUTH-01 | 1.0.0 | 正确账号密码登录成功 | **P0** | 功能 | 账号正常已激活 | user: demo, pwd: valid | 1. 提交登录请求 | 返回 200 并获取双 Token | `assert resp.status == 200` | 核心登录主链路 | Standard |
| **TC-AUTH-002** | Auth_Demo | REQ-AUTH-01 | 1.0.0 | 密码连续错误5次锁定账号 | **P1** | 安全 | 账号正常 | pwd: wrong | 1. 连续输错5次密码 | 第5次后提示账号被锁定15分钟 | `assert resp.code == 423` | 防撞库暴力破解 | Standard |
