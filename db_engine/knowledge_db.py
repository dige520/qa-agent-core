#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 结构化测试知识库引擎 (Knowledge DB Engine)
基于纯内存 DuckDB 执行引擎 (零落盘、零 Git 二进制污染) + 契约化 Schema
"""

import os
import sys
import glob
import re
import csv
import argparse
from pathlib import Path
from typing import Optional, List

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

try:
    import duckdb
except ImportError:
    print("Error: duckdb 模块未安装，请执行: pip install duckdb", file=sys.stderr)
    sys.exit(1)

MODULE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SCHEMA_PATH = Path(__file__).resolve().parent / "schema_contract.sql"

class KnowledgeDB:
    """纯内存测试知识库结构化分析引擎"""
    
    def __init__(
        self,
        schema_path: Optional[Path] = None,
        bug_csv_path: Optional[Path] = None,
        test_case_dirs: Optional[List[Path]] = None
    ):
        self.con = duckdb.connect(":memory:")
        self.schema_path = schema_path or DEFAULT_SCHEMA_PATH
        self.bug_csv_path = bug_csv_path
        self.test_case_dirs = test_case_dirs or []

        self._init_schema()
        if self.bug_csv_path and self.bug_csv_path.exists():
            self._load_bugs()
        if self.test_case_dirs:
            self._load_test_cases()
        self._apply_views()

    def _init_schema(self):
        """执行标准 Schema 契约创建表结构"""
        if self.schema_path and self.schema_path.exists():
            ddl = self.schema_path.read_text(encoding="utf-8")
            statements = ddl.split(";")
            for stmt in statements:
                stmt_clean = stmt.strip()
                if stmt_clean and not stmt_clean.startswith("CREATE OR REPLACE VIEW"):
                    self.con.execute(stmt_clean)

    def _load_bugs(self):
        """载入历史缺陷 CSV 数据"""
        bugs_data = []
        with open(self.bug_csv_path, "r", encoding="utf-8-sig", errors="replace") as f:
            reader = csv.reader(f)
            header = next(reader, None)
            row_id = 1
            for row in reader:
                if not row or not any(row):
                    continue
                while len(row) < 14:
                    row.append("")
                title, desc, device, disc_ver, fix_ver = row[0].strip(), row[1].strip(), row[2].strip(), row[3].strip(), row[4].strip()
                attach, prio, sev, mod, owner = row[5].strip(), row[6].strip(), row[7].strip(), row[8].strip(), row[9].strip()
                occ_at, prog, stat, verif = row[10].strip(), row[11].strip(), row[12].strip(), row[13].strip()

                bugs_data.append((
                    row_id, title, desc, device, disc_ver, fix_ver,
                    attach, prio, sev, mod, owner, occ_at, prog, stat, verif
                ))
                row_id += 1

        self.con.executemany("""
            INSERT INTO historical_bugs VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, bugs_data)

    def _load_test_cases(self):
        """从测试用例文档中提取结构化数据"""
        cases_data = []
        md_files = []
        for d in self.test_case_dirs:
            if d.exists():
                md_files.extend(list(d.glob("*.md")))

        for md_path in md_files:
            try:
                content = md_path.read_text(encoding="utf-8")
            except Exception:
                continue

            lines = content.splitlines()
            for line in lines:
                if not line.strip().startswith("|") or "case_id" in line.lower() or "---" in line:
                    continue
                cols = [c.strip() for c in line.split("|")[1:-1]]
                if len(cols) >= 6:
                    c_id = cols[0]
                    c_title = cols[1] if len(cols) > 1 else ""
                    c_mod = cols[2] if len(cols) > 2 else ""
                    c_prod = "General"
                    c_prio = cols[3] if len(cols) > 3 else "P1"
                    c_steps = cols[4] if len(cols) > 4 else ""
                    c_exp = cols[5] if len(cols) > 5 else ""
                    c_act = cols[6] if len(cols) > 6 else ""
                    c_stat = "Active"
                    c_notes = cols[7] if len(cols) > 7 else ""
                    cases_data.append((
                        c_id, c_title, c_mod, c_prod, c_prio,
                        c_steps, c_exp, c_act, c_stat, c_notes, md_path.name
                    ))

        if cases_data:
            self.con.executemany("""
                INSERT INTO test_cases VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, cases_data)

    def _apply_views(self):
        """执行视图创建"""
        if self.schema_path and self.schema_path.exists():
            ddl = self.schema_path.read_text(encoding="utf-8")
            statements = ddl.split(";")
            for stmt in statements:
                stmt_clean = stmt.strip()
                if stmt_clean.startswith("CREATE OR REPLACE VIEW"):
                    try:
                        self.con.execute(stmt_clean)
                    except Exception:
                        pass

    def query(self, sql: str) -> List[dict]:
        """执行 SQL 并返回字典数组"""
        try:
            rel = self.con.sql(sql)
            if rel is None:
                return []
            cols = rel.columns
            rows = rel.fetchall()
            return [dict(zip(cols, r)) for r in rows]
        except Exception as e:
            return [{"error": str(e)}]
