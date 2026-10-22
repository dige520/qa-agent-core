#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 企业级 Model Context Protocol (MCP) 服务器
标准 STDIO JSON-RPC 协议实现，面向 AI Agent 暴露混合检索、知识图谱、DuckDB 结构化分析、质量门禁与回归规划接口
"""

import sys
import json
import re
from pathlib import Path
from typing import Dict, Any, List, Optional

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

CLI_DIR = Path(__file__).resolve().parent
MODULE_ROOT = CLI_DIR.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from core.retriever import search_hybrid
from core.graph import KnowledgeGraphIndexer
from core.config import MANIFEST_FILE
from core.manifest import ManifestManager
from db_engine.knowledge_db import KnowledgeDB

graph_indexer = KnowledgeGraphIndexer()
manifest_mgr = ManifestManager(MANIFEST_FILE)

# 内存 DuckDB 单例缓存
_db_instance: Optional[KnowledgeDB] = None


def get_knowledge_db() -> KnowledgeDB:
    """初始化并获取纯内存 DuckDB 实例 (自动识别宿主主仓或脱敏 Mock 语料)"""
    global _db_instance
    if _db_instance is None:
        host_root = MODULE_ROOT.parent
        host_csv = host_root / "00_待归档新语料_Staging_Inbox" / "processed_archive" / "软件已关闭bug单汇总_数据表.csv"
        host_tc_dir = host_root / "06_测试用例汇总目录_Test_Cases"
        host_ui_dir = host_root / "01_客户端与UI设计_Client_UI"
        host_schema = host_root / "07_知识沉淀与纯文本语料_Corpus_Summary" / "schema_contract.sql"

        if host_csv.exists():
            tc_dirs = [d for d in [host_tc_dir, host_ui_dir] if d.exists()]
            schema_p = host_schema if host_schema.exists() else None
            _db_instance = KnowledgeDB(schema_path=schema_p, bug_csv_path=host_csv, test_case_dirs=tc_dirs)
        else:
            mock_csv = MODULE_ROOT / "mock_data" / "bugs" / "mock_historical_bugs.csv"
            mock_tc_dirs = [MODULE_ROOT / "mock_data" / "cases"]
            _db_instance = KnowledgeDB(bug_csv_path=mock_csv if mock_csv.exists() else None, test_case_dirs=mock_tc_dirs)
    return _db_instance


def handle_tools_list() -> Dict[str, Any]:
    return {
        "tools": [
            {
                "name": "search_knowledge_base",
                "description": "在知识库中执行两阶段高精度混合检索 (Google Gemini 向量 + BM25 倒排 + Cross-Encoder 精排)。默认自动屏蔽历史已归档文档，包含'归档/历史'意图时自动唤醒。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "自然语言技术查询"},
                        "top_k": {"type": "integer", "description": "返回最相关切片数 (默认 4)", "default": 4},
                        "include_archived": {"type": "boolean", "description": "是否强行包含已归档/历史单次测试用例及测试报告 (默认自动识别意图)", "default": False}
                    },
                    "required": ["query"]
                }
            },
            {
                "name": "trace_requirement",
                "description": "根据需求 ID 正向追踪关联测试用例与知识卡片。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "req_id": {"type": "string", "description": "需求编号，例如 KB-REQ-PROTO-025"}
                    },
                    "required": ["req_id"]
                }
            },
            {
                "name": "get_index_status",
                "description": "获取当前知识库的增量索引状态、总切片数与文件概览。",
                "inputSchema": {"type": "object", "properties": {}}
            },
            {
                "name": "query_knowledge_db",
                "description": "使用 DuckDB 纯内存 SQL 引擎执行原生查询。可查询 historical_bugs (历史缺陷表) 与 test_cases (测试用例表)。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "sql": {"type": "string", "description": "要执行的 DuckDB SQL 查询语句，例如: SELECT severity, count(*) FROM historical_bugs GROUP BY severity"}
                    },
                    "required": ["sql"]
                }
            },
            {
                "name": "query_historical_bugs",
                "description": "按条件精确筛选历史已关闭缺陷库。可按严重级别、版本、机型、模块或关键词过滤，获取现象与防回归断言。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "severity": {"type": "string", "description": "严重程度: 致命, 严重, 一般, 轻微"},
                        "device_model": {"type": "string", "description": "设备机型，如 D4, D5, V6-US"},
                        "version": {"type": "string", "description": "版本过滤 (发现版本或修复版本)，如 1.5.0, 1.4"},
                        "module": {"type": "string", "description": "所属业务模块，如 OTA, AI, Audio, Chat"},
                        "keyword": {"type": "string", "description": "标题或描述中的搜索关键词"},
                        "limit": {"type": "integer", "description": "返回条数限制 (默认 10)", "default": 10}
                    }
                }
            },
            {
                "name": "query_test_cases",
                "description": "按产品线、模块、优先级精确检索测试用例全景库，返回执行步骤与预期判定标准。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "product": {"type": "string", "description": "产品线过滤: Codie_Device, Code27_APP"},
                        "module": {"type": "string", "description": "所属模块，如 ToolResult_v2, ClientFactSource, LanguageSplit"},
                        "priority": {"type": "string", "description": "用例优先级: P0, P1"},
                        "keyword": {"type": "string", "description": "用例标题或步骤关键词"},
                        "limit": {"type": "integer", "description": "返回条数限制 (默认 15)", "default": 15}
                    }
                }
            },
            {
                "name": "validate_knowledge_base",
                "description": "一键执行知识库质量门禁与红线审查。检查 YAML Frontmatter、产品隔离红线、Open-Core 核心仓脱敏状态及死链。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "strict": {"type": "boolean", "description": "严格模式 (警告亦视作未通过，默认 false)", "default": False},
                        "path_filter": {"type": "string", "description": "可选目录或文件名过滤"}
                    }
                }
            },
            {
                "name": "get_regression_plan",
                "description": "根据发版版本号自动生成《版本增量回归测试 Checklist》，汇总目标版本新增需求、涉及历史缺陷与关联 P0/P1 用例。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "target_version": {"type": "string", "description": "目标发布版本号，例如: 1.5.1"},
                        "base_version": {"type": "string", "description": "上一基线版本号，例如: 1.5.0"},
                        "module": {"type": "string", "description": "可选业务模块过滤"}
                    },
                    "required": ["target_version"]
                }
            }
        ]
    }


def handle_call_tool(name: str, arguments: dict) -> Dict[str, Any]:
    try:
        if name == "search_knowledge_base":
            q = arguments.get("query", "")
            top_k = arguments.get("top_k", 4)
            inc_archived = arguments.get("include_archived", None)
            results = search_hybrid(q, top_k=top_k, include_archived=inc_archived)
            formatted = []
            for r in results:
                formatted.append(f"【{r['metadata'].get('title')}】(得分: {r.get('rerank_score')})\n{r.get('text')}\n")
            return {"content": [{"type": "text", "text": "\n---\n".join(formatted)}]}

        elif name == "trace_requirement":
            req_id = arguments.get("req_id", "")
            res = graph_indexer.trace_requirement(req_id)
            return {"content": [{"type": "text", "text": json.dumps(res, ensure_ascii=False, indent=2)}]}

        elif name == "get_index_status":
            manifest_mgr.manifest_data = manifest_mgr._load_manifest()
            status = {
                "total_files": len(manifest_mgr.manifest_data),
                "total_chunks": len(manifest_mgr.get_all_active_chunk_ids())
            }
            return {"content": [{"type": "text", "text": json.dumps(status, ensure_ascii=False, indent=2)}]}

        elif name == "query_knowledge_db":
            sql = arguments.get("sql", "").strip()
            if not sql:
                return {"isError": True, "content": [{"type": "text", "text": "错误: sql 参数不能为空"}]}
            db = get_knowledge_db()
            results = db.query(sql)
            return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}]}

        elif name == "query_historical_bugs":
            severity = arguments.get("severity")
            device = arguments.get("device_model")
            version = arguments.get("version")
            module = arguments.get("module")
            keyword = arguments.get("keyword")
            limit = int(arguments.get("limit", 10))

            clauses = ["1=1"]
            if severity:
                clauses.append(f"severity = '{severity}'")
            if device:
                clauses.append(f"device_model LIKE '%{device}%'")
            if version:
                clauses.append(f"(discovered_version LIKE '%{version}%' OR fixed_version LIKE '%{version}%')")
            if module:
                clauses.append(f"module LIKE '%{module}%'")
            if keyword:
                clauses.append(f"(title LIKE '%{keyword}%' OR description LIKE '%{keyword}%')")

            sql = f"SELECT id, title, severity, device_model, discovered_version, fixed_version, description FROM historical_bugs WHERE {' AND '.join(clauses)} LIMIT {limit}"
            db = get_knowledge_db()
            results = db.query(sql)
            return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}]}

        elif name == "query_test_cases":
            product = arguments.get("product")
            module = arguments.get("module")
            priority = arguments.get("priority")
            keyword = arguments.get("keyword")
            limit = int(arguments.get("limit", 15))

            clauses = ["1=1"]
            if product:
                clauses.append(f"product LIKE '%{product}%'")
            if module:
                clauses.append(f"module LIKE '%{module}%'")
            if priority:
                clauses.append(f"priority = '{priority}'")
            if keyword:
                clauses.append(f"(title LIKE '%{keyword}%' OR steps LIKE '%{keyword}%')")

            sql = f"SELECT case_id, title, module, priority, steps, expected_result, source_file FROM test_cases WHERE {' AND '.join(clauses)} LIMIT {limit}"
            db = get_knowledge_db()
            results = db.query(sql)
            return {"content": [{"type": "text", "text": json.dumps(results, ensure_ascii=False, indent=2)}]}

        elif name == "validate_knowledge_base":
            strict = bool(arguments.get("strict", False))
            path_filter = arguments.get("path_filter", "")

            host_scripts = MODULE_ROOT.parent / "scripts"
            if host_scripts.exists() and str(host_scripts.parent) not in sys.path:
                sys.path.insert(0, str(host_scripts.parent))

            try:
                from scripts.validate_kb import run_validation
                val_res = run_validation(root_dir=MODULE_ROOT.parent, target_filter=path_filter, strict=strict)
            except Exception as e:
                val_res = {"is_healthy": False, "error": f"门禁校验器加载失败: {str(e)}"}

            return {"content": [{"type": "text", "text": json.dumps(val_res, ensure_ascii=False, indent=2)}]}

        elif name == "get_regression_plan":
            target_ver = arguments.get("target_version", "").strip()
            base_ver = arguments.get("base_version", "").strip()
            module_filter = arguments.get("module", "").strip()

            db = get_knowledge_db()
            # 1. 查找历史关键缺陷
            bug_clauses = [f"(fixed_version LIKE '%{target_ver}%' OR discovered_version LIKE '%{target_ver}%')"]
            if module_filter:
                bug_clauses.append(f"module LIKE '%{module_filter}%'")
            sql_bugs = f"""
                SELECT id, title, severity, device_model, discovered_version, fixed_version 
                FROM historical_bugs 
                WHERE {' AND '.join(bug_clauses)} 
                ORDER BY CASE severity WHEN '致命' THEN 1 WHEN '严重' THEN 2 WHEN '一般' THEN 3 ELSE 4 END 
                LIMIT 15
            """
            bugs = db.query(sql_bugs)

            # 2. 查找关联用例
            tc_clauses = ["1=1"]
            if target_ver:
                tc_clauses.append(f"(source_file LIKE '%{target_ver}%' OR title LIKE '%{target_ver}%')")
            if module_filter:
                tc_clauses.append(f"module LIKE '%{module_filter}%'")
            sql_tc = f"""
                SELECT case_id, title, module, priority, source_file 
                FROM test_cases 
                WHERE {' AND '.join(tc_clauses)}
                ORDER BY priority ASC 
                LIMIT 20
            """
            cases = db.query(sql_tc)

            # 3. 组织结构化 Markdown 响应
            report_lines = [
                f"# [回归计划] 版本增量回归测试 Checklist ({target_ver})",
                f"> 基线版本: `{base_ver or 'N/A'}` | 模块过滤: `{module_filter or '全部'}`",
                "",
                f"## 1. 需重点防回归的历史缺陷 (共收录 {len(bugs)} 条)",
            ]
            if bugs:
                report_lines.append("| 缺陷 ID | 严重级别 | 机型 | 发现/修复版本 | 缺陷标题 |")
                report_lines.append("| :--- | :---: | :---: | :---: | :--- |")
                for b in bugs:
                    report_lines.append(f"| `BUG-{b.get('id')}` | **{b.get('severity')}** | {b.get('device_model')} | {b.get('discovered_version')} ➔ {b.get('fixed_version')} | {b.get('title')} |")
            else:
                report_lines.append("未检索到直接关联的历史缺陷。")

            report_lines.append("")
            report_lines.append(f"## 2. 核心推荐回归测试用例 (共推荐 {len(cases)} 条)")
            if cases:
                report_lines.append("| 用例编号 | 优先级 | 业务模块 | 用例标题 | 来源文件 |")
                report_lines.append("| :--- | :---: | :--- | :--- | :--- |")
                for c in cases:
                    report_lines.append(f"| `{c.get('case_id')}` | **{c.get('priority')}** | {c.get('module')} | {c.get('title')} | `{c.get('source_file')}` |")
            else:
                report_lines.append("未检索到指定版本的专属用例，建议执行全量 P0 冒烟基线。")

            return {"content": [{"type": "text", "text": "\n".join(report_lines)}]}

        return {"isError": True, "content": [{"type": "text", "text": f"未知工具: {name}"}]}

    except Exception as e:
        return {"isError": True, "content": [{"type": "text", "text": f"工具执行异常: {str(e)}"}]}


def main():
    while True:
        line = sys.stdin.readline()
        if not line:
            break
        try:
            req = json.loads(line)
        except Exception:
            continue

        req_id = req.get("id")
        method = req.get("method")

        if method == "tools/list":
            resp = {"jsonrpc": "2.0", "id": req_id, "result": handle_tools_list()}
        elif method == "tools/call":
            params = req.get("params", {})
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            tool_res = handle_call_tool(tool_name, tool_args)
            resp = {"jsonrpc": "2.0", "id": req_id, "result": tool_res}
        else:
            resp = {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": "Method not found"}}

        sys.stdout.write(json.dumps(resp, ensure_ascii=False) + "\n")
        sys.stdout.flush()


if __name__ == "__main__":
    main()
