#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Open-Core 查询分析、技术实体抽取与智能重写器 (Query Rewriter & Entity Linker)
支持通用实体抽取与自定义业务同义词/扩展表动态注入
"""

import re
from typing import List, Dict, Optional, Tuple

DEFAULT_ENTITY_PATTERNS: List[Tuple[str, str]] = [
    (r"[A-Z0-9]+-[A-Z0-9]+-[0-9]+", "Standard_ID"),
    (r"\b(P0|P1|P2|P3)\b", "Priority_Level"),
    (r"\b(PASS|FAIL|BLOCK|CANCEL)\b", "Test_Status"),
    (r"\b(SLA|TTL|OOM|Crash|Timeout)\b", "Performance_Metric"),
    (r"\b(HTTP|gRPC|WebSocket|REST|TCP|UDP)\b", "Network_Protocol"),
    (r"\b(ASR|TTS|LLM|VLM|Lipsync)\b", "AI_Pipeline")
]

class QueryRewriter:
    """查询分析、实体提取与重写引擎"""
    
    def __init__(self, extra_patterns: List[Tuple[str, str]] = None, expansion_map: Dict[str, str] = None):
        self.entity_patterns = list(DEFAULT_ENTITY_PATTERNS)
        if extra_patterns:
            self.entity_patterns.extend(extra_patterns)
        self.expansion_map = expansion_map or {}

    def extract_entities(self, query: str) -> List[Dict[str, str]]:
        """从用户查询中提取高价值技术实体"""
        entities = []
        for pattern, entity_type in self.entity_patterns:
            matches = re.finditer(pattern, query, re.IGNORECASE)
            for m in matches:
                entities.append({
                    "text": m.group(0),
                    "type": entity_type,
                    "span": (m.start(), m.end())
                })
        return entities

    def rewrite_query(self, query: str, chat_history: Optional[List[Dict[str, str]]] = None) -> Dict[str, any]:
        """结合历史对话重写查询，并返回重写结果与提取的实体"""
        cleaned_query = query.strip()
        entities = self.extract_entities(cleaned_query)
        rewritten_text = cleaned_query
        
        pronoun_triggers = ["它", "这个", "那台", "上个问题", "刚才说的", "该功能", "its", "this issue", "the device"]
        has_pronoun = any(p in cleaned_query.lower() for p in pronoun_triggers)
        
        if has_pronoun and chat_history:
            recent_context = " ".join([turn.get("content", "") for turn in chat_history[-2:]])
            context_entities = self.extract_entities(recent_context)
            if context_entities:
                key_entity = context_entities[0]["text"]
                rewritten_text = f"{key_entity} {cleaned_query}"
        
        for k, exp in self.expansion_map.items():
            if k in cleaned_query and exp not in rewritten_text:
                rewritten_text = f"{rewritten_text} ({exp})"

        return {
            "original_query": query,
            "rewritten_query": rewritten_text,
            "entities": entities,
            "has_entities": len(entities) > 0
        }
