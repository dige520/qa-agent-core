#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 知识库文件指纹与增量状态管理器 (Manifest Manager)
基于 SHA-256 哈希实现零冗余向量化与秒级增量同步
"""

import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Tuple

class ManifestManager:
    """知识库文件指纹与增量清单管理器"""
    
    def __init__(self, manifest_path: Path):
        self.manifest_path = manifest_path
        self.manifest_data: Dict[str, dict] = self._load_manifest()

    def _load_manifest(self) -> Dict[str, dict]:
        """加载历史 manifest.json 文件"""
        if self.manifest_path.exists():
            try:
                with open(self.manifest_path, "r", encoding="utf-8") as f:
                    return json.load(f)
            except Exception as e:
                print(f"⚠️ 读取历史 manifest.json 异常: {e}，将采用全量扫描模式。")
                return {}
        return {}

    def save_manifest(self):
        """持久化保存最新 manifest.json 文件"""
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.manifest_path, "w", encoding="utf-8") as f:
            json.dump(self.manifest_data, f, ensure_ascii=False, indent=2)

    @staticmethod
    def calculate_file_hash(file_path: Path) -> str:
        """计算单份文件的 SHA-256 哈希值"""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(65536), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()

    def detect_changes(self, current_files: List[Path], base_dir: Path) -> Tuple[List[Path], List[Path], List[str], List[Path]]:
        """
        对比当前文件列表与历史 manifest，返回变更元组：
        (added_files, modified_files, deleted_rel_paths, unmodified_files)
        """
        current_rel_map: Dict[str, Path] = {}
        for p in current_files:
            rel_path = p.relative_to(base_dir).as_posix()
            current_rel_map[rel_path] = p

        added: List[Path] = []
        modified: List[Path] = []
        unmodified: List[Path] = []
        deleted: List[str] = []

        # 检查当前存在的文件
        for rel_path, full_path in current_rel_map.items():
            current_hash = self.calculate_file_hash(full_path)
            if rel_path not in self.manifest_data:
                added.append(full_path)
            else:
                historical_hash = self.manifest_data[rel_path].get("hash", "")
                if current_hash != historical_hash:
                    modified.append(full_path)
                else:
                    unmodified.append(full_path)

        # 检查已删除的文件
        for rel_path in list(self.manifest_data.keys()):
            if rel_path not in current_rel_map:
                deleted.append(rel_path)

        return added, modified, deleted, unmodified

    def update_file_record(self, rel_path: str, file_hash: str, chunk_ids: List[str], meta: dict = None):
        """更新单个文件在清单中的记录"""
        self.manifest_data[rel_path] = {
            "hash": file_hash,
            "chunk_ids": chunk_ids,
            "metadata": meta or {}
        }

    def remove_file_record(self, rel_path: str) -> List[str]:
        """删除记录并返回该文件对应的历史 chunk_id 列表"""
        if rel_path in self.manifest_data:
            old_chunks = self.manifest_data[rel_path].get("chunk_ids", [])
            del self.manifest_data[rel_path]
            return old_chunks
        return []

    def get_all_active_chunk_ids(self) -> Set[str]:
        """获取所有当前有效文件对应的全部 chunk_id 集合"""
        chunks = set()
        for doc_info in self.manifest_data.values():
            chunks.update(doc_info.get("chunk_ids", []))
        return chunks
