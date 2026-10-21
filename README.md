# 🚀 QA-Agent-Core: 企业级测试智能体通用双引擎中台

[![License](https://img.shields.io/badge/License-Apache_2.0-blue.svg)](LICENSE)
[![Python](https://img.shields.io/badge/Python-3.9+-green.svg)]()
[![Architecture](https://img.shields.io/badge/Architecture-Open--Core-orange.svg)]()

**QA-Agent-Core** 是专为 AI 驱动的软件测试知识库与智能体工程设计的通用双引擎中台。采用 **Open-Core** 开源核心架构，将通用算法引擎（混合检索 RAG + 内存级 DuckDB 分析）与特定业务私有数据彻底解耦。

---

## 🏛️ 核心架构体系

```text
qa-agent-core/
├── core/                        # 🧠【核心算法层】
│   ├── retriever.py             # 0.7 向量 + 0.3 BM25 两阶段混合检索器
│   ├── reranker.py              # Cross-Encoder 置信度精排器
│   ├── graph.py                 # 双向实体拓扑图谱与追溯引擎
│   ├── manifest.py              # SHA-256 增量状态管理器 (秒级建库)
│   ├── rewriter.py              # 技术实体抽取与查询重写器
│   └── config.py                # 自适应环境与存储路径适配器
│
├── db_engine/                   # 💾【结构化分析引擎】
│   ├── knowledge_db.py          # 纯内存 DuckDB 执行引擎 (零落盘、零污染)
│   └── schema_contract.sql      # 严谨 Schema 契约 (杜绝 Text-to-SQL 幻觉)
│
├── cli/                         # 🚀【命令行与工具入口】
│   ├── ingest.py                # 通用增量建库流水线 CLI
│   └── mcp_server.py            # 标准 Model Context Protocol (MCP) 服务器
│
├── guidelines/                  # 📖【测试方法论规范】
│   ├── 01_knowledge_base_standard.md
│   ├── 02_test_case_standard.md
│   └── 03_maintenance_spec.md
│
├── templates/                   # 📋【标准化 Schema 模板】
│   ├── test_case_template.md
│   └── bug_analysis_template.md
│
├── mock_data/                   # 🧪【脱敏通用体验数据集】
│   ├── docs/                    # 示例通用规格 Markdown
│   ├── cases/                   # 示例基线测试用例
│   └── bugs/                    # 示例缺陷 CSV 表
│
└── evaluation/                  # 📊【质量评测与质检基准】
    ├── dataset.json             # 黄金评测基准集
    └── evaluator.py             # 自动化 Hit Rate & MRR 评测脚本
```

---

## ⚡ 核心技术特性

1. **两阶段混合检索 (Two-Stage Hybrid Search)**:
   - 第一阶段：Google Gemini 3072 维语义向量与 BM25 倒排索引加权召回（0.7 : 0.3）；
   - 第二阶段：Cross-Encoder 精排重打分，结合实体命中、标题权重与文档密度。
2. **纯内存 DuckDB 契约分析 (In-Memory DuckDB Engine)**:
   - 历史缺陷全量数据纯内存执行，零磁盘临时文件、零 Git 二进制污染；
   - Schema 契约驱动，杜绝大模型在缺陷分析与统计时的幻觉。
3. **秒级增量更新 (Smart Incremental Ingest)**:
   - SHA-256 哈希指纹自动对比，仅对增量与修改文件触发 Embedding 生成，未修改文件 0 耗时 0 API 消耗。
4. **原生支持 MCP 协议 (Model Context Protocol)**:
   - 提供标准 STDIO 接口，可直接接入 Claude Desktop、Cursor、Gemini CLI 等任意智能体环境。

---

## 🛠️ 快速上手体验

### 1. 安装依赖
```bash
git clone https://github.com/dige520/qa-agent-core.git
cd qa-agent-core
pip install -r requirements.txt
cp .env.example .env
# 编辑 .env 填入您的 GOOGLE_API_KEY
```

### 2. 运行增量建库
```bash
# 基于内置的 mock_data 演示数据集执行建库
python cli/ingest.py --root mock_data
```

### 3. 执行混合检索
```python
from core.retriever import search_hybrid

results = search_hybrid("用户登录 Token 过期刷新机制", top_k=3)
for r in results:
    print(r["metadata"]["title"], r["rerank_score"], r["confidence"])
```

### 4. 执行内存 DuckDB 缺陷查询
```python
from db_engine.knowledge_db import KnowledgeDB

db = KnowledgeDB()
print(db.query("SELECT * FROM v_fatal_bugs"))
```

---

## 🔒 企业级 Open-Core 集成方式

在企业私有知识库中，将本项目作为 Git Submodule 引入：
```bash
# 在您的私有仓库中执行
git submodule add https://github.com/dige520/qa-agent-core.git core-engine

# 配置环境变量指向私有数据路径
export RAG_DATA_DIR=/path/to/private/data
export BUG_DATA_PATH=/path/to/private/bugs.csv
```
实现通用引擎与私有商业数据的安全物理隔离！

---

## 📄 开源许可证
本项目采用 [Apache-2.0](LICENSE) 许可证。
