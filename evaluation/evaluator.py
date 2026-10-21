#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core RAG 自动化质量评测基准引擎 (Automated Benchmark Evaluator)
基于 Hit Rate @ K 与 MRR (Mean Reciprocal Rank) 标准衡量检索精准度
"""

import sys
import json
import time
from pathlib import Path
from typing import Optional

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

EVAL_DIR = Path(__file__).resolve().parent
MODULE_ROOT = EVAL_DIR.parent
if str(MODULE_ROOT) not in sys.path:
    sys.path.insert(0, str(MODULE_ROOT))

from core.retriever import search_hybrid

DEFAULT_DATASET_FILE = EVAL_DIR / "dataset.json"

def run_benchmark(dataset_file: Optional[Path] = None, top_k: int = 5) -> dict:
    active_dataset_file = dataset_file or DEFAULT_DATASET_FILE
    if not active_dataset_file.exists():
        print(f"❌ 找不到评测数据集: {active_dataset_file}")
        return {}

    with open(active_dataset_file, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    print("=" * 65)
    print(f"📊 开始执行 RAG 自动化质量基准评测 (共 {len(dataset)} 个黄金用例)")
    print("=" * 65)

    hit_top1_count = 0
    hit_top3_count = 0
    hit_top5_count = 0
    reciprocal_ranks = []
    latencies_ms = []

    for idx, item in enumerate(dataset, 1):
        q_id = item["id"]
        query = item["query"]
        target_sub = item.get("expected_target_substring", "").lower()

        t0 = time.time()
        try:
            results = search_hybrid(query, top_k=top_k)
            elapsed_ms = (time.time() - t0) * 1000
            latencies_ms.append(elapsed_ms)
        except Exception as e:
            print(f"[{idx:02d}] ❌ 执行异常: {e}")
            continue

        hit_rank = 0
        for r_idx, res in enumerate(results, 1):
            text_lower = res.get("text", "").lower()
            if target_sub and target_sub in text_lower:
                hit_rank = r_idx
                break

        if hit_rank == 1:
            hit_top1_count += 1
            hit_top3_count += 1
            hit_top5_count += 1
            reciprocal_ranks.append(1.0)
            tag = "🟢 Top-1"
        elif 1 < hit_rank <= 3:
            hit_top3_count += 1
            hit_top5_count += 1
            reciprocal_ranks.append(1.0 / hit_rank)
            tag = f"🟡 Top-{hit_rank}"
        elif 3 < hit_rank <= 5:
            hit_top5_count += 1
            reciprocal_ranks.append(1.0 / hit_rank)
            tag = f"🟠 Top-{hit_rank}"
        else:
            reciprocal_ranks.append(0.0)
            tag = "🔴 Miss"

        print(f"[{idx:02d}/{len(dataset)}] {tag} | {elapsed_ms:5.0f}ms | [{q_id}] {query[:35]}...")

    total = len(dataset)
    hit_rate_top1 = (hit_top1_count / total) * 100 if total else 0
    hit_rate_top3 = (hit_top3_count / total) * 100 if total else 0
    hit_rate_top5 = (hit_top5_count / total) * 100 if total else 0
    mrr = sum(reciprocal_ranks) / total if total else 0
    avg_latency = sum(latencies_ms) / len(latencies_ms) if latencies_ms else 0

    print("=" * 65)
    print("🏆 评测指标汇总报告 (Benchmark Summary):")
    print(f"  🎯 Hit Rate @ 1: {hit_rate_top1:.2f}% ({hit_top1_count}/{total})")
    print(f"  🎯 Hit Rate @ 3: {hit_rate_top3:.2f}% ({hit_top3_count}/{total})")
    print(f"  🎯 Hit Rate @ 5: {hit_rate_top5:.2f}% ({hit_top5_count}/{total})")
    print(f"  📈 MRR 得分:     {mrr:.4f}")
    print(f"  ⚡ 平均耗时:      {avg_latency:.1f} ms")
    print("=" * 65)

    return {
        "hit_rate_top1": hit_rate_top1,
        "hit_rate_top3": hit_rate_top3,
        "hit_rate_top5": hit_rate_top5,
        "mrr": mrr,
        "avg_latency_ms": avg_latency
    }

if __name__ == "__main__":
    run_benchmark()
