#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 知识库增量建库与向量同步 CLI 入口 (Ingest CLI)
支持通用目录扫描、智能增量指纹对比与 BM25/Chroma 倒排索引导出
"""

import os
import re
import sys
import json
import time
import argparse
import urllib.request
import urllib.error
from pathlib import Path
from typing import List, Dict, Tuple

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

from core.config import (
    GOOGLE_API_KEY,
    EMBEDDING_MODEL,
    CHROMA_DB_DIR,
    BM25_INDEX_FILE,
    MANIFEST_FILE,
    DATA_DIR
)
from core.manifest import ManifestManager
from core.retriever import tokenize_text

opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))

def get_batch_embeddings(texts: List[str], max_retries: int = 5) -> List[List[float]]:
    """批量生成 Google Gemini Embeddings"""
    if not texts or not GOOGLE_API_KEY:
        return []

    url = f"https://generativelanguage.googleapis.com/v1beta/models/{EMBEDDING_MODEL}:batchEmbedContents?key={GOOGLE_API_KEY}"
    requests_payload = [
        {
            "model": f"models/{EMBEDDING_MODEL}",
            "content": {"parts": [{"text": t}]}
        }
        for t in texts
    ]

    payload = {"requests": requests_payload}
    data_bytes = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data_bytes,
        headers={"Content-Type": "application/json"}
    )

    for attempt in range(max_retries):
        try:
            with opener.open(req, timeout=60) as resp:
                res_json = json.loads(resp.read().decode("utf-8"))
                embeddings = [e.get("values", []) for e in res_json.get("embeddings", [])]
                return embeddings
        except urllib.error.HTTPError as e:
            if e.code == 429:
                wait_sec = (attempt + 1) * 3
                time.sleep(wait_sec)
                continue
            raise
        except Exception as e:
            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))
                continue
            raise
    return []

def parse_yaml_frontmatter(content: str) -> Tuple[Dict[str, str], str]:
    """解析 Markdown 文件头部的 YAML frontmatter"""
    yaml_dict = {}
    body = content
    if content.startswith("---"):
        parts = body.split("---", 2)
        if len(parts) >= 3:
            yaml_raw = parts[1]
            body = parts[2].strip()
            for line in yaml_raw.strip().split("\n"):
                if ":" in line:
                    k, v = line.split(":", 1)
                    k = k.strip()
                    v = v.strip().strip("'\"[]")
                    yaml_dict[k] = v
    return yaml_dict, body

def chunk_markdown(file_path: Path, base_dir: Path) -> List[Dict]:
    """将单份 Markdown 切块为语义 Chunks"""
    content = file_path.read_text(encoding="utf-8")
    yaml_meta, body = parse_yaml_frontmatter(content)
    rel_path = file_path.relative_to(base_dir).as_posix()
    doc_title = yaml_meta.get("title", file_path.stem)
    module_name = yaml_meta.get("module", "General")
    version_str = yaml_meta.get("version", "1.0.0")

    chunks = []
    safe_prefix = rel_path.replace('/', '_').replace('\\', '_').replace('.', '_')

    # 按 H2 / H3 标题拆分
    sections = re.split(r'\n(?=##?\s+)', body)
    for s_idx, sec in enumerate(sections):
        sec_text = sec.strip()
        if not sec_text:
            continue
        c_id = f"{safe_prefix}_sec_{s_idx}"
        first_line = sec_text.splitlines()[0].strip("# \t")
        chunk_full_text = f"【文档: {doc_title} | 章节: {first_line}】\n\n{sec_text}"
        chunks.append({
            "chunk_id": c_id,
            "text": chunk_full_text,
            "metadata": {
                "source_path": rel_path,
                "title": doc_title,
                "module": module_name,
                "version": version_str,
                "section": first_line
            }
        })

    return chunks

def run_ingest(base_dir: Path, scan_dirs: List[str] = None, force_rebuild: bool = False):
    """执行增量建库流水线"""
    print("=" * 65)
    print("🚀 开始执行 Open-Core 知识库增量建库流水线")
    print(f"📌 根目录: {base_dir}")
    print(f"📌 数据目录: {DATA_DIR}")
    print("=" * 65)

    DATA_DIR.mkdir(parents=True, exist_ok=True)
    manifest_mgr = ManifestManager(MANIFEST_FILE)

    if force_rebuild:
        manifest_mgr.manifest_data = {}

    target_files = []
    if scan_dirs:
        for s in scan_dirs:
            p = base_dir / s
            if p.exists():
                if p.is_file() and p.suffix == ".md":
                    target_files.append(p)
                elif p.is_dir():
                    target_files.extend(list(p.rglob("*.md")))
    else:
        target_files = list(base_dir.rglob("*.md"))

    target_files = sorted(list(set(target_files)))
    print(f"📦 发现候选 Markdown 文档共 {len(target_files)} 份")

    added, modified, deleted, unmodified = manifest_mgr.detect_changes(target_files, base_dir)
    print(f"🔍 变更检测结果: 新增 {len(added)} | 修改 {len(modified)} | 删除 {len(deleted)} | 未变 {len(unmodified)}")

    files_to_process = added + modified
    if not files_to_process and not deleted:
        print("✨ 知识库无内容变更，增量建库跳过。")
        return

    # 初始化 ChromaDB
    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DB_DIR))
    collection = client.get_or_create_collection(name="code27_kb")

    # 处理删除
    for del_rel in deleted:
        old_cids = manifest_mgr.remove_file_record(del_rel)
        if old_cids:
            collection.delete(ids=old_cids)

    all_chunks_to_embed = []
    for f in files_to_process:
        rel_p = f.relative_to(base_dir).as_posix()
        old_cids = manifest_mgr.remove_file_record(rel_p)
        if old_cids:
            collection.delete(ids=old_cids)

        chunks = chunk_markdown(f, base_dir)
        cids = [c["chunk_id"] for c in chunks]
        f_hash = ManifestManager.calculate_file_hash(f)
        manifest_mgr.update_file_record(rel_p, f_hash, cids)
        all_chunks_to_embed.extend(chunks)

    print(f"⏳ 正在生成向量 Chunks 共 {len(all_chunks_to_embed)} 个...")
    batch_size = 25
    for i in range(0, len(all_chunks_to_embed), batch_size):
        batch = all_chunks_to_embed[i:i + batch_size]
        texts = [b["text"] for b in batch]
        ids = [b["chunk_id"] for b in batch]
        metas = [b["metadata"] for b in batch]
        embs = get_batch_embeddings(texts)
        if embs:
            collection.upsert(ids=ids, embeddings=embs, documents=texts, metadatas=metas)

    manifest_mgr.save_manifest()

    # 导出 BM25 倒排索引
    all_docs = collection.get()
    bm25_corpus = []
    if all_docs and "ids" in all_docs:
        for idx, cid in enumerate(all_docs["ids"]):
            text = all_docs["documents"][idx]
            bm25_corpus.append({
                "chunk_id": cid,
                "text": text,
                "metadata": all_docs["metadatas"][idx],
                "tokens": tokenize_text(text)
            })

    with open(BM25_INDEX_FILE, "w", encoding="utf-8") as f:
        json.dump(bm25_corpus, f, ensure_ascii=False)

    print("🎉 增量建库与 BM25/向量同步完成！")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Open-Core 增量建库工具")
    parser.add_argument("--root", type=str, default=".", help="扫描根目录")
    parser.add_argument("--force", action="store_true", help="强制全量清空重建")
    args = parser.parse_args()

    run_ingest(Path(args.root).resolve(), force_rebuild=args.force)
