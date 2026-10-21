#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 引擎全局配置与环境适配器 (Config & Adapter)
支持独立运行模式与作为私有知识库子模块 (Submodule) 运行模式
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# 根目录自适应推导
MODULE_ROOT = Path(__file__).resolve().parent.parent
PARENT_ROOT = MODULE_ROOT.parent

# 优先加载父目录（宿主私有仓）的 .env，其次加载本核心模块的 .env
if (PARENT_ROOT / ".env").exists():
    load_dotenv(PARENT_ROOT / ".env")
if (MODULE_ROOT / ".env").exists():
    load_dotenv(MODULE_ROOT / ".env")

# 核心算法与 API 配置
GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
EMBEDDING_MODEL = os.getenv("EMBEDDING_MODEL", "gemini-embedding-2")
RERANK_WEIGHT_VECTOR = float(os.getenv("RERANK_WEIGHT_VECTOR", "0.7"))
RERANK_WEIGHT_BM25 = float(os.getenv("RERANK_WEIGHT_BM25", "0.3"))

# 持久化数据存储路径 (支持环境变量重定向至宿主私有仓)
DATA_DIR = Path(os.getenv("RAG_DATA_DIR", MODULE_ROOT / "data"))
CHROMA_DB_DIR = Path(os.getenv("CHROMA_DB_DIR", DATA_DIR / "chroma_db"))
BM25_INDEX_FILE = Path(os.getenv("BM25_INDEX_FILE", DATA_DIR / "bm25_corpus.json"))
MANIFEST_FILE = Path(os.getenv("MANIFEST_FILE", DATA_DIR / "manifest.json"))

# 结构化数据库与 Schema 路径
DEFAULT_SCHEMA_PATH = MODULE_ROOT / "db_engine" / "schema_contract.sql"
SCHEMA_SQL_PATH = Path(os.getenv("SCHEMA_SQL_PATH", DEFAULT_SCHEMA_PATH))
BUG_DATA_PATH = Path(os.getenv("BUG_DATA_PATH", MODULE_ROOT / "mock_data" / "bugs" / "mock_historical_bugs.csv"))

# 确保数据目录存在
DATA_DIR.mkdir(parents=True, exist_ok=True)
