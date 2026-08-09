"""Query Intent Classifier and Target Asset Extraction Router."""

import re
from pie.ai.models import QueryIntent
from pie.graph.builder import KnowledgeGraph


class QueryIntentRouter:
    """Classifies user queries into cognitive intents and extracts target asset references."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def classify_intent(self, query: str) -> QueryIntent:
        """Deterministically classify the query into the most relevant cognitive intent."""
        q_lower = query.lower()

        # 1. What-If Deletion & Blast Radius
        if any(k in q_lower for k in ["delete", "remove", "what if", "what happens", "blast radius", "break", "impact"]):
            return QueryIntent.IMPACT

        # 2. Modernization & Code Generation
        if any(k in q_lower for k in ["pyspark", "dbt", "python", "spark", "generate code", "write script", "migrate", "modernize"]):
            return QueryIntent.CODE_GEN

        # 3. Security, Audit & Technical Debt
        if any(k in q_lower for k in ["orphan", "debt", "retry", "retries", "saas", "vendor", "concurrency", "collide", "collision", "audit"]):
            return QueryIntent.SECURITY_AUDIT

        # 4. Multi-Criteria Asset Search
        if any(k in q_lower for k in ["find", "search", "list datasets", "csv", "parquet", "onprem", "on-prem", "file store",
                                       "list pipelines", "find pipelines", "search pipelines", "show pipelines"]):
            return QueryIntent.SEARCH

        # 5. Technical Debugging
        if any(k in q_lower for k in ["debug", "sql query", "stored proc", "procedure", "step by step", "retry count", "timeout"]):
            return QueryIntent.DEBUGGING

        # 6. Architecture & Overview
        if any(k in q_lower for k in ["explain", "overview", "how does", "what does", "architecture", "know"]):
            return QueryIntent.ARCHITECTURE

        return QueryIntent.GENERAL

    def extract_target_asset(self, query: str) -> str | None:
        """Extract the exact target asset name referenced in the user query."""
        # 1. Direct match against known graph nodes
        for node_id, node in self.graph.nodes.items():
            if node.name.lower() in query.lower():
                return node.name

        # 2. Regex match on CamelCase or PascalCase or snake_case tokens
        tokens = re.findall(r"[A-Za-z0-9_-]{3,}", query)
        for token in tokens:
            for node in self.graph.nodes.values():
                if token.lower() == node.name.lower():
                    return node.name

        return None
