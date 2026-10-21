---
title: 测试智能体知识库建设与交互规范
module: Guidelines
tags: [规范, 方法论, Agent, RAG]
version: 1.0.0
status: Active
source: standard
owner: QA
---

# 测试智能体知识库建设与交互规范

## 1. 核心设计原则

1. **仓库即可信源 (Single Source of Truth)**：所有知识、用例与规则必须以结构化 Markdown 或明确 Schema 存储在 Git 仓库中；
2. **严格产品属性隔离 (Strict Product Boundary)**：不同终端（如移动端 APP、嵌入式设备端、云端后台）必须物理隔离语料，严禁跨域混淆；
3. **双引擎协同检索**：
   - 非结构化文本走 **0.7 向量 + 0.3 BM25 + Cross-Encoder 精排** 混合 RAG；
   - 结构化缺陷与数据统计走 **纯内存 DuckDB 结构化分析**；
4. **历史语料基线**：历史用例与测试报告默认定位为事实证据（`HistoricalEvidence`），严禁未确认前越界提升为当前版本正式需求。

## 2. 标准指令集

| 指令 | 目标 | 触发工具链 | 输出形式 |
| :--- | :--- | :--- | :--- |
| `/lookup [问题]` | 规格与规则检索 | 混合 RAG 两阶段检索 | 核心结论 + 出处文档路径 |
| `/gen-testcases [模块]` | 生成标准测试用例 | 前置闸门 + 模板渲染 | 范围声明 + 覆盖矩阵 + Markdown 表格 |
| `/bug-analysis [场景]` | 缺陷排查与根因复盘 | DuckDB 查询 + 拓扑图谱 | 现象传导 + 根因 + 防回归测试点 |
| `/ingest` | 增量建库与索引同步 | SHA-256 对比 + Chroma/BM25 更新 | 变更报告 + 索引健康度汇报 |
