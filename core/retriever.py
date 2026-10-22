#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 两阶段混合检索器 (Two-Stage Hybrid Retriever)
结合 Google Gemini 3072 维语义向量检索 + BM25 倒排索引 + Cross-Encoder 精排重排序
"""

import os
import re
import sys
import time
import json
import urllib.request
from pathlib import Path
from typing import List, Dict, Optional

from .config import (
    GOOGLE_API_KEY,
    EMBEDDING_MODEL,
    CHROMA_DB_DIR,
    BM25_INDEX_FILE,
    RERANK_WEIGHT_VECTOR,
    RERANK_WEIGHT_BM25
)
from .rewriter import QueryRewriter
from .reranker import CrossEncoderReranker

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get_query_embedding(query: str, api_key: str = None, model: str = None) -> list:
    """调用 Google Gemini Embedding API 生成查询向量"""
    active_key = api_key or GOOGLE_API_KEY
    active_model = model or EMBEDDING_MODEL
    if not active_key:
        raise ValueError("未配置 GOOGLE_API_KEY，无法生成向量！")

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{active_model}:embedContent?key={active_key}"
    payload = {
        "model": f"models/{active_model}",
        "content": {
            "parts": [{"text": query}]
        }
    }
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"}
    )
    max_retries = 3
    for attempt in range(max_retries):
        try:
            with opener.open(req, timeout=20) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                return res_json.get("embedding", {}).get("values", [])
        except urllib.error.HTTPError as e:
            if e.code == 429 and attempt < max_retries - 1:
                time.sleep(3 * (attempt + 1))
                continue
            raise
        except Exception:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    return []

def tokenize_text(text: str) -> List[str]:
    """中英文混合分词分字器 (用于 BM25 倒排索引)"""
    tokens = []
    text_clean = text.lower()
    words = re.findall(r'[a-zA-Z0-9_-]+', text_clean)
    tokens.extend(words)
    chinese_chars = re.findall(r'[\u4e00-\u9fa5]', text_clean)
    tokens.extend(chinese_chars)
    return tokens

def search_bm25(query: str, bm25_file: Path = None, top_k: int = 15) -> List[Dict]:
    """基于持久化词表的轻量 BM25 检索"""
    active_bm25_file = bm25_file or BM25_INDEX_FILE
    if not active_bm25_file.exists():
        return []

    try:
        with open(active_bm25_file, "r", encoding="utf-8") as f:
            corpus_data = json.load(f)
    except Exception:
        return []

    query_tokens = tokenize_text(query)
    if not query_tokens:
        return []

    scores = []
    for doc in corpus_data:
        doc_tokens = set(doc.get("tokens", []))
        match_count = sum(1 for qt in query_tokens if qt in doc_tokens)
        if match_count > 0:
            score = match_count / (len(query_tokens) + 0.5)
            scores.append({
                "chunk_id": doc["chunk_id"],
                "text": doc["text"],
                "metadata": doc["metadata"],
                "bm25_score": score
            })

    scores.sort(key=lambda x: x["bm25_score"], reverse=True)
    return scores[:top_k]

def search_hybrid(
    query: str,
    top_k: int = 4,
    chat_history: Optional[List[Dict[str, str]]] = None,
    chroma_dir: Path = None,
    bm25_file: Path = None,
    include_archived: Optional[bool] = None
) -> List[Dict]:
    """
    两阶段生产级混合检索入口：
    1. 查询分析与技术实体提取
    2. Vector (70%) + BM25 (30%) 粗排召回
    3. 冷热知识分层路由 (日常静默屏蔽已归档/已废弃资料，显式意图自动召回)
    4. Cross-Encoder 精排重打分输出 Top-K
    """
    rewriter = QueryRewriter()
    rewrite_res = rewriter.rewrite_query(query, chat_history=chat_history)
    rewritten_query = rewrite_res["rewritten_query"]
    entities = rewrite_res["entities"]

    active_chroma_dir = chroma_dir or CHROMA_DB_DIR
    active_bm25_file = bm25_file or BM25_INDEX_FILE

    # 1. 向量粗排召回
    vector_results = []
    if active_chroma_dir.exists() and GOOGLE_API_KEY:
        try:
            import chromadb
            client = chromadb.PersistentClient(path=str(active_chroma_dir))
            collection = client.get_or_create_collection(name="code27_kb")
            q_emb = get_query_embedding(rewritten_query)
            if q_emb:
                v_res = collection.query(
                    query_embeddings=[q_emb],
                    n_results=min(top_k * 3, 20)
                )
                if v_res and v_res.get("ids") and v_res["ids"][0]:
                    for idx, c_id in enumerate(v_res["ids"][0]):
                        dist = v_res["distances"][0][idx] if "distances" in v_res else 0.5
                        v_score = 1.0 - (dist / 2.0)
                        vector_results.append({
                            "chunk_id": c_id,
                            "text": v_res["documents"][0][idx],
                            "metadata": v_res["metadatas"][0][idx],
                            "vector_score": max(v_score, 0.0)
                        })
        except Exception as e:
            print(f"⚠️ 向量召回异常，降级为 BM25 单路检索: {e}")

    # 2. BM25 粗排召回
    bm25_results = search_bm25(rewritten_query, bm25_file=active_bm25_file, top_k=top_k * 3)

    # 3. 双路归一化与加权合并
    fused_candidates = {}
    for item in vector_results:
        cid = item["chunk_id"]
        fused_candidates[cid] = {
            "chunk_id": cid,
            "text": item["text"],
            "metadata": item["metadata"],
            "vector_score": item["vector_score"],
            "bm25_score": 0.0
        }

    for item in bm25_results:
        cid = item["chunk_id"]
        if cid in fused_candidates:
            fused_candidates[cid]["bm25_score"] = item["bm25_score"]
        else:
            fused_candidates[cid] = {
                "chunk_id": cid,
                "text": item["text"],
                "metadata": item["metadata"],
                "vector_score": 0.0,
                "bm25_score": item["bm25_score"]
            }

    candidate_list = []
    for c in fused_candidates.values():
        h_score = (c["vector_score"] * RERANK_WEIGHT_VECTOR) + (c["bm25_score"] * RERANK_WEIGHT_BM25)
        c["hybrid_score"] = round(h_score, 4)
        candidate_list.append(c)

    # 4. 冷热知识分层过滤 (日常屏蔽已归档/废弃资料，显式查询自动唤醒)
    ARCHIVE_TRIGGER_KEYWORDS = [
        "归档", "历史", "测试报告", "当年", "e2e", "废弃", "已下线", "旧版", "archived", "report"
    ]
    has_archive_intent = any(kw in query.lower() for kw in ARCHIVE_TRIGGER_KEYWORDS)
    allow_archived = include_archived if include_archived is not None else has_archive_intent

    ARCHIVED_PATTERNS = [
        "测试用例_客户端事实源_E2E_服务端",
        "测试用例_客户端事实源改造_产品端回归",
        "测试用例_ToolResult_v2_设备工具调用往返_E2E_服务端",
        "测试用例_v1.5.1_历史重置机制与日记修改删除_E2E",
        "测试报告_v1.5.0",
        "测试报告_v1.5.1",
        "测试报告_v1.5.2",
        "C27_产品功能说明_飞书版",
        "以往功能说明分类沉淀汇总",
        "knowledge_base_implementation_blueprint"
    ]

    filtered_candidates = []
    for c in candidate_list:
        meta = c.get("metadata", {}) or {}
        st = meta.get("status", "")
        role = meta.get("source_role", "")
        title = meta.get("title", "")
        source_path = meta.get("source_path", "")
        is_archived = (
            st in ["Archived", "Deprecated", "TestEvidenceOnly", "HistoricalEvidence"]
            or role in ["ArchiveEvidence", "HistoricalEvidence", "TestReportEvidence"]
            or "测试报告" in title
            or any(pat in source_path or pat in title for pat in ARCHIVED_PATTERNS)
        )
        if not allow_archived and is_archived:
            continue
        filtered_candidates.append(c)

    # 5. Cross-Encoder 精排
    reranked = CrossEncoderReranker.rerank(
        query=query,
        candidates=filtered_candidates if filtered_candidates else candidate_list,
        entities=entities,
        top_k=top_k
    )

    return reranked
