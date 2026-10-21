#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 企业级 Model Context Protocol (MCP) 服务器
标准 STDIO JSON-RPC 协议实现，面向 AI Agent 暴露混合检索、知识图谱与结构化分析接口
"""

import sys
import json
from pathlib import Path

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

graph_indexer = KnowledgeGraphIndexer()
manifest_mgr = ManifestManager(MANIFEST_FILE)

def handle_tools_list():
    return {
        "tools": [
            {
                "name": "search_knowledge_base",
                "description": "在知识库中执行两阶段高精度混合检索 (Google Gemini 向量 + BM25 倒排 + Cross-Encoder 精排)。",
                "inputSchema": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "自然语言技术查询"},
                        "top_k": {"type": "integer", "description": "返回最相关切片数 (默认 4)", "default": 4}
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
                        "req_id": {"type": "string", "description": "需求编号"}
                    },
                    "required": ["req_id"]
                }
            },
            {
                "name": "get_index_status",
                "description": "获取当前知识库的索引状态与文件指纹概览。",
                "inputSchema": {"type": "object", "properties": {}}
            }
        ]
    }

def handle_call_tool(name: str, arguments: dict):
    if name == "search_knowledge_base":
        q = arguments.get("query", "")
        top_k = arguments.get("top_k", 4)
        results = search_hybrid(q, top_k=top_k)
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

    return {"isError": True, "content": [{"type": "text", "text": f"未知工具: {name}"}]}

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
