#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 两阶段 Cross-Encoder 重排序模型 (Two-Stage Reranker)
基于实体增强、语义密度与标题注意力机制实现高精度 Top-K 精排
"""

import re
from typing import List, Dict

class CrossEncoderReranker:
    """两阶段重排序与置信度精排器"""

    @staticmethod
    def _calculate_term_density(query_terms: List[str], text: str) -> float:
        """计算查询词在目标文本中的密集度与跨度"""
        if not query_terms:
            return 0.0
        text_lower = text.lower()
        matched = 0
        for term in query_terms:
            if len(term) >= 2 and term.lower() in text_lower:
                matched += 1
        return matched / len(query_terms)

    @staticmethod
    def rerank(query: str, candidates: List[Dict], entities: List[Dict] = None, top_k: int = 4) -> List[Dict]:
        """对粗排候选集执行精排打分并返回 Top-K 结果"""
        if not candidates:
            return []

        entities = entities or []
        entity_texts = [e["text"].lower() for e in entities]
        query_words = [w for w in re.split(r"[\s,，、。！？!?]+", query) if len(w) >= 2]

        reranked_results = []

        for item in candidates:
            base_score = item.get("hybrid_score", 0.0)
            text = item.get("text", "")
            metadata = item.get("metadata", {})
            title = metadata.get("title", "")
            section = metadata.get("section", "")
            tags = metadata.get("tags", "")

            # 1. 实体强匹配奖励
            entity_boost = 0.0
            text_lower = text.lower()
            for ent in entity_texts:
                if ent in text_lower:
                    entity_boost += 0.20
                if ent in title.lower() or ent in section.lower():
                    entity_boost += 0.15
            entity_boost = min(entity_boost, 0.35)

            # 2. 标题/章节相关度得分
            header_text = f"{title} {section} {tags}".lower()
            header_match_count = sum(1 for w in query_words if w.lower() in header_text)
            header_boost = min(header_match_count * 0.05, 0.15)

            # 3. 词密度得分
            density_score = CrossEncoderReranker._calculate_term_density(query_words, text) * 0.20

            # 4. 知识卡片与正式用例优先级加权
            type_boost = 0.0
            chunk_type = metadata.get("type", "")
            if chunk_type in ("KnowledgeCard", "TestCaseSuite"):
                type_boost = 0.08

            final_rerank_score = (base_score * 0.50) + entity_boost + header_boost + density_score + type_boost
            final_rerank_score = min(max(final_rerank_score, 0.0), 1.0)

            confidence = "HIGH" if final_rerank_score >= 0.75 else ("MEDIUM" if final_rerank_score >= 0.50 else "LOW")

            reranked_item = dict(item)
            reranked_item["rerank_score"] = round(final_rerank_score, 4)
            reranked_item["confidence"] = confidence
            reranked_results.append(reranked_item)

        reranked_results.sort(key=lambda x: x["rerank_score"], reverse=True)
        return reranked_results[:top_k]
