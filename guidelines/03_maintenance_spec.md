---
title: 测试知识库维护与持续归档规范
module: Guidelines
tags: [维护, 归档, YAML, 收件箱]
version: 1.0.0
status: Active
source: standard
owner: QA
---

# 测试知识库维护与持续归档规范

## 1. 收件箱规则 (Inbox Workflow)

所有新资料（需求草稿、会议纪要、测试报告、缺陷复盘、数据表）优先放入：
```text
00_待归档新语料_Staging_Inbox/
```
通过执行 `/ingest` 指令驱动自动化入库流水线：
1. 识别资料类型、模块与版本；
2. 提取测试关注点、规则与已知风险；
3. 补齐标准化 YAML Frontmatter 元数据；
4. 移动原始文件至 `processed_archive/`，收件箱保持清空。

## 2. YAML Frontmatter 标准

每个正式入库的 Markdown 必须包含：
```yaml
---
title: 文档标题
module: 模块名
tags: [标签1, 标签2]
version: 1.0.0
updated_at: YYYY-MM-DD
status: ActiveSource / HistoricalEvidence / CandidateKnowledgeCard
source: requirement / report / manual
owner: QA
---
```
