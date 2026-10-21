---
title: 通用测试用例输出模板
module: Templates
tags: [模板, 测试用例, Schema]
version: 1.0.0
status: Active
source: standard
owner: QA
---

# 通用测试用例输出模板

## 1. 引用来源与范围声明

- **需求/规格来源**：
- **涉及系统组件/模块**：
- **测试环境与命名空间**：
- **本次包含范围**：
- **本次排除范围**：

## 2. 覆盖矩阵

| 覆盖维度 | 状态 | 依据 | 说明 |
| :--- | :--- | :--- | :--- |
| 主流程功能 | Must / Optional / Excluded | | 核心正向业务流程 |
| 异常与容灾 | Must / Optional / Excluded | | 网络超时、依赖故障、错误重试 |
| 边界极限值 | Must / Optional / Excluded | | 数据长度、并发阈值、容量上限 |
| 历史防回归 | Must / Optional / Excluded | | 已知关联缺陷防回归断言 |

## 3. 测试用例清单

| case_id | module | requirement_id | version | title | priority | type | preconditions | test_data | steps | expected_result | dynamic_assertion | regression_guard | source_role |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **TC-001** | ModuleName | REQ-001 | 1.0.0 | 示例主流程用例 | **P0** | 功能 | 前置配置正常 | 正常参数 | 1. 步骤一<br>2. 步骤二 | 预期成功返回 | `assert status == "success"` | 防历史回归点 | Standard |
