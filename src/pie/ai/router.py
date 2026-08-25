"""Query Intent Classifier and Target Asset Extraction Router."""

import difflib
import re
from pie.ai.models import QueryIntent
from pie.graph.models import NodeType, ChangeType
from pie.graph.builder import KnowledgeGraph

# Tokens that never identify an asset (generic query scaffolding). Filtered out before
# partial/fuzzy asset-name matching so "explain the invoice pipeline" targets "invoice".
_ASSET_EXTRACTION_STOP_WORDS = {
    "what", "are", "is", "was", "were", "be", "been", "the", "a", "an", "and", "or",
    "how", "does", "do", "did", "can", "could", "would", "should", "will", "why",
    "you", "your", "tell", "me", "about", "explain", "describe", "detail", "details",
    "overview", "walk", "through", "show", "list", "find", "search", "which", "where",
    "when", "this", "that", "these", "those", "there", "for", "with", "from", "into",
    "using", "use", "used", "uses", "not", "no", "yes", "pipeline", "pipelines",
    "dataset", "datasets", "linked", "service", "services", "trigger", "triggers",
    "dataflow", "dataflows", "flow", "flows", "process", "processes",
    "of", "in", "to", "for", "my", "we", "have", "has", "had", "currently", "all",
    "any", "its", "it", "as", "at", "on", "by", "if", "then", "than", "so", "each",
}

# Asset types that make sense as single-query targets (activities are nested, not targetable).
_TARGET_ASSET_TYPES = (
    NodeType.PIPELINE,
    NodeType.DATASET,
    NodeType.LINKED_SERVICE,
    NodeType.TRIGGER,
    NodeType.DATA_FLOW,
)


def normalize_pipeline_typos(text: str) -> str:
    """Fix common misspellings of 'pipeline' (e.g. 'pipline', 'piplines', 'pipe lines').

    Intent routing and keyword extraction stay robust when users type 'list out invoice piplines'.
    """
    normalized = re.sub(r"\bpipline", "pipeline", text)
    normalized = re.sub(r"\bpipe\s+lines?\b", "pipelines", normalized)
    return normalized


class QueryIntentRouter:
    """Classifies user queries into cognitive intents and extracts target asset references."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def classify_intent(self, query: str) -> QueryIntent:
        """Deterministically classify the query into the most relevant cognitive intent."""
        q_lower = normalize_pipeline_typos(query.lower())

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
        if any(k in q_lower for k in [
            "find", "search", "list datasets", "csv", "parquet", "onprem", "on-prem", "file store",
            "list pipelines", "list of", "list of pipelines", "list me", "find pipelines",
            "search pipelines", "show pipelines", "pipelines we have", "pipelines do we have",
            "pipelines exist", "pipelines in our factory", "pipelines in the factory",
            "which pipelines", "all pipelines",
        ]):
            return QueryIntent.SEARCH

        # 5. Technical Debugging
        if any(k in q_lower for k in ["debug", "sql query", "stored proc", "procedure", "step by step", "retry count", "timeout"]):
            return QueryIntent.DEBUGGING

        # 6. Architecture & Overview
        if any(k in q_lower for k in ["explain", "overview", "how does", "what does", "architecture",
                                      "explore", "walk me through"]):
            return QueryIntent.ARCHITECTURE

        return QueryIntent.GENERAL

    def extract_target_asset(self, query: str, allow_fuzzy: bool = True) -> str | None:
        """Extract the target asset name referenced in the user query.

        Exact whole-name matches always win. When ``allow_fuzzy`` is enabled (single-asset
        intents such as explain/debug/impact/code-gen), partial and typo-tolerant matches are
        also accepted so that "explain railcarrx invoiceload" resolves to ``RailCarRx_InvoiceLoad``.
        """
        q_lower = normalize_pipeline_typos(query.lower())

        # 1. Direct match against known graph nodes
        for node in self.graph.nodes.values():
            if node.name.lower() in q_lower:
                return node.name

        # 2. Regex token equality on CamelCase / PascalCase / snake_case tokens
        tokens = re.findall(r"[A-Za-z0-9_-]{3,}", normalize_pipeline_typos(query))
        for token in tokens:
            for node in self.graph.nodes.values():
                if token.lower() == node.name.lower():
                    return node.name

        if not allow_fuzzy:
            return None

        # Prefer the asset type the user explicitly named (dataset vs pipeline, etc.).
        preferred_type = None
        if "pipeline" in q_lower:
            preferred_type = NodeType.PIPELINE
        elif "dataset" in q_lower:
            preferred_type = NodeType.DATASET
        elif "linked service" in q_lower:
            preferred_type = NodeType.LINKED_SERVICE
        elif "trigger" in q_lower:
            preferred_type = NodeType.TRIGGER
        elif "data flow" in q_lower or "dataflow" in q_lower:
            preferred_type = NodeType.DATA_FLOW

        target_nodes = [
            n for n in self.graph.nodes.values()
            if n.type in _TARGET_ASSET_TYPES and (preferred_type is None or n.type == preferred_type)
        ]

        # 3. Partial / prefix match: query token appears in a node name (e.g. "railcarrx"
        #    -> RailCarRx_InvoiceLoad, "customer ingestion" -> PL_Customer_Daily_Ingestion).
        candidates: dict[str, float] = {}
        for token in tokens:
            t = token.lower()
            if t in _ASSET_EXTRACTION_STOP_WORDS or len(t) < 3:
                continue
            for node in target_nodes:
                name_tokens = [x for x in re.split(r"[_\-\s]+", node.name.lower()) if x]
                name_norm = re.sub(r"[^a-z0-9]", "", node.name.lower())
                if t not in name_norm:
                    continue
                score = 1.0
                for nt in name_tokens:
                    if t == nt:
                        score = 3.0
                    elif nt.startswith(t):
                        score = max(score, 2.0)
                    elif t.startswith(nt):
                        score = max(score, 1.5)
                candidates[node.name] = candidates.get(node.name, 0.0) + score

        if candidates:
            best_name, best_score = max(candidates.items(), key=lambda kv: kv[1])
            if best_score >= 2.0:
                return best_name

        # 3b. Parameter / variable name match: check if any token matches a known
        #     parameter or variable name in pipeline metadata. This prevents fuzzy
        #     matching from incorrectly resolving param/var names to unrelated assets.
        pv_match = self.find_parameter_or_variable_match(query)
        if pv_match is not None:
            return pv_match

        # 4. Typo-tolerant fuzzy fallback (difflib) on normalized names and their tokens.
        best_name, best_score = None, 0.0
        for token in tokens:
            t = token.lower()
            if t in _ASSET_EXTRACTION_STOP_WORDS or len(t) < 3:
                continue
            for node in target_nodes:
                name_tokens = [x for x in re.split(r"[_\-\s]+", node.name.lower()) if len(x) >= 3]
                name_norm = re.sub(r"[^a-z0-9]", "", node.name.lower())
                score = max(
                    [difflib.SequenceMatcher(None, t, name_norm).ratio()]
                    + [difflib.SequenceMatcher(None, t, x).ratio() for x in name_tokens],
                    default=0.0,
                )
                if score > best_score:
                    best_score, best_name = score, node.name

        if best_name and best_score >= 0.6:
            return best_name
        return None

    def infer_change_type(self, query: str) -> ChangeType | None:
        """Infer the type of change from a natural language query.

        Returns the most likely ChangeType, or None if no change-type signal is detected.
        """
        q = normalize_pipeline_typos(query.lower())

        # Order matters: more specific keywords first
        if any(k in q for k in ["decommission", "retire", "retirement", "phase out"]):
            return ChangeType.DECOMMISSION
        if any(k in q for k in ["disable", "turn off", "stop", "pause", "suspend"]):
            return ChangeType.DISABLE
        if any(k in q for k in ["replace", "swap", "migrate", "switch to", "change to"]):
            return ChangeType.REPLACE
        if any(k in q for k in ["rename", "move to", "relabel"]):
            return ChangeType.RENAME
        if any(k in q for k in ["modify", "change", "update", "alter", "adjust"]):
            return ChangeType.MODIFY
        if any(k in q for k in ["delete", "remove", "drop", "eliminate", "clear"]):
            return ChangeType.REMOVE
        return None

    def detect_object_type_hint(self, query: str) -> NodeType | None:
        """Detect an explicit object type mention in the query."""
        q = normalize_pipeline_typos(query.lower())
        if "integration runtime" in q or "ir " in q:
            return NodeType.INTEGRATION_RUNTIME
        if "linked service" in q:
            return NodeType.LINKED_SERVICE
        if "data flow" in q or "dataflow" in q:
            return NodeType.DATA_FLOW
        if "trigger" in q:
            return NodeType.TRIGGER
        if "parameter" in q or "global parameter" in q:
            return NodeType.PARAMETER
        if "variable" in q:
            return NodeType.VARIABLE
        if "dataset" in q:
            return NodeType.DATASET
        if "activity" in q:
            return NodeType.ACTIVITY
        if "pipeline" in q:
            return NodeType.PIPELINE
        return None

    def find_parameter_or_variable_match(self, query: str) -> str | None:
        """Check if any known parameter or variable name appears in the query.

        Scans all pipeline metadata parameters and variables. First checks for exact
        token matches, then falls back to checking if the full parameter/variable name
        (3+ chars) appears as a substring of the query text. Returns the name if found,
        None otherwise.
        """
        q_lower = normalize_pipeline_typos(query.lower())
        tokens = re.findall(r"[A-Za-z0-9_-]{3,}", q_lower)

        # Collect all parameter and variable names from the graph
        param_var_names: set[str] = set()
        for node in self.graph.nodes.values():
            if node.type == NodeType.PIPELINE:
                params = node.properties.get("parameters", {})
                variables = node.properties.get("variables", {})
                for name in params:
                    param_var_names.add(name)
                for name in variables:
                    param_var_names.add(name)

        # 1. Exact token match (most confident)
        for token in tokens:
            t_lower = token.lower()
            for pv_name in param_var_names:
                if pv_name.lower() == t_lower:
                    return pv_name

        # 2. Full name substring in query (handles names with special chars that
        #    tokenize differently, e.g. "SAP_DS_User_SecretName" in the raw query)
        for pv_name in param_var_names:
            if len(pv_name) >= 3 and pv_name.lower() in q_lower:
                return pv_name

        return None
