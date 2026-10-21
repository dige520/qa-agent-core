#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 轻量实体拓扑与双向追溯图谱 (Graph Indexer & Traceability Engine)
解析需求矩阵、知识卡片与测试用例关联关系，支持双向影响面分析
"""

import re
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional

class KnowledgeGraphIndexer:
    """轻量实体拓扑图谱索引器"""

    def __init__(self, matrix_file: Optional[Path] = None):
        self.matrix_file = matrix_file
        self.requirements: Dict[str, dict] = {}
        self.modules: Dict[str, List[str]] = {}
        self.test_case_links: Dict[str, List[str]] = {}
        if self.matrix_file and self.matrix_file.exists():
            self._build_graph()

    def _build_graph(self):
        """解析追踪矩阵与知识卡片构建拓扑图"""
        content = self.matrix_file.read_text(encoding="utf-8")
        lines = content.splitlines()
        for line in lines:
            if not line.strip().startswith("|") or "Requirement ID" in line or "---" in line:
                continue
            cols = [c.strip() for c in line.split("|")[1:-1]]
            if len(cols) >= 6:
                req_id = cols[0].replace("**", "").strip()
                module = cols[1].strip()
                version = cols[2].strip()
                status = cols[3].strip()
                desc = cols[4].strip()
                card_path = cols[5].strip()
                test_cases = cols[6].strip() if len(cols) > 6 else ""

                parsed_cases = [tc.strip() for tc in re.split(r"[,;`\n\r]+", test_cases) if tc.strip()]

                record = {
                    "req_id": req_id,
                    "module": module,
                    "desc": desc,
                    "status": status,
                    "version": version,
                    "card_path": card_path,
                    "test_cases": parsed_cases
                }
                self.requirements[req_id] = record

                if module not in self.modules:
                    self.modules[module] = []
                self.modules[module].append(req_id)

                for tc in parsed_cases:
                    if tc not in self.test_case_links:
                        self.test_case_links[tc] = []
                    self.test_case_links[tc].append(req_id)

    def trace_requirement(self, req_id: str) -> Optional[dict]:
        """根据需求 ID 正向追踪关联用例与知识卡片"""
        clean_id = req_id.strip()
        return self.requirements.get(clean_id)

    def trace_test_case(self, case_id: str) -> List[str]:
        """根据用例 ID 反向追踪关联需求"""
        clean_id = case_id.strip()
        return self.test_case_links.get(clean_id, [])

    def get_module_requirements(self, module: str) -> List[dict]:
        """获取指定模块下的全部需求清单"""
        req_ids = self.modules.get(module, [])
        return [self.requirements[r] for r in req_ids if r in self.requirements]

    def export_graph_json(self) -> str:
        """导出 JSON 格式知识拓扑图谱"""
        nodes = []
        links = []
        for r_id, r_info in self.requirements.items():
            nodes.append({"id": r_id, "type": "requirement", "module": r_info.get("module")})
            for tc in r_info.get("test_cases", []):
                nodes.append({"id": tc, "type": "test_case"})
                links.append({"source": r_id, "target": tc, "relationship": "VERIFIES"})
        return json.dumps({"nodes": nodes, "links": links}, ensure_ascii=False, indent=2)
