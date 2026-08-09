"""Schema Compressor: Strips UI visual coordinates, system GUIDs, and empty metadata,
compressing raw ADF metadata by 90%+ into high-density semantic context.
"""

from typing import Any
from pie.graph.models import GraphNode, NodeType


class SchemaCompressor:
    """Compresses verbose JSON metadata into dense, token-minimized formats."""

    @staticmethod
    def compress_activity_node(node: GraphNode, step_num: int = 1) -> str:
        """Compress raw activity JSON into an ultra-concise token-saving line."""
        props = node.properties or {}
        act_type = props.get("type", "Unknown")
        type_props = props.get("type_properties", {}) or {}
        called_pipe = props.get("called_pipeline")
        retry_policy = props.get("retry_policy", {}) or {}
        retries = f"{retry_policy.get('count', 0)}x" if retry_policy.get("count", 0) > 0 else "0x"

        details = []
        if called_pipe:
            details.append(f"SubPipe:{called_pipe}")

        # Stored Procs / SQL
        proc = type_props.get("storedProcedureName") or type_props.get("sqlReaderQuery")
        if proc:
            proc_clean = str(proc).replace("\n", " ").strip()[:40]
            details.append(f"SQL:{proc_clean}")

        # URLs / Web Endpoints
        url = type_props.get("url") or type_props.get("accountEndpoint")
        if url:
            details.append(f"URL:{str(url)[:30]}")

        # Source -> Sink
        src = type_props.get("source", {}).get("type") if isinstance(type_props.get("source"), dict) else None
        snk = type_props.get("sink", {}).get("type") if isinstance(type_props.get("sink"), dict) else None
        if src or snk:
            details.append(f"Data Movement:{src or '?' }->{snk or '?'}")

        detail_str = f" ({','.join(details)})" if details else ""
        desc_str = f" - {node.description[:30]}" if node.description else ""

        return f"Step {step_num}: {node.name}[{act_type}] Retry:{retries}{detail_str}{desc_str}"

    @staticmethod
    def compress_dataset_node(node: GraphNode) -> str:
        """Compress dataset schemas into compact column definitions."""
        props = node.properties or {}
        ds_type = props.get("type", "Dataset")
        ls_name = props.get("linked_service_name", "None")
        schema_fields = props.get("schema_fields", []) or []

        columns_preview = []
        for f in schema_fields[:4]:  # Limit top 4 columns for token savings
            if isinstance(f, dict):
                cname = f.get("name", "")
                ctype = f.get("type", "str")
                columns_preview.append(f"{cname}({ctype})")

        cols_str = ",".join(columns_preview) if columns_preview else "Dynamic"
        if len(schema_fields) > 4:
            cols_str += f"(+{len(schema_fields) - 4} more)"

        return f"DS:{node.name}[{ds_type}](LS:{ls_name},Folder:{node.folder or 'Root'}) Cols:{cols_str}"

    @staticmethod
    def compress_linked_service_node(node: GraphNode) -> str:
        """Compress linked service connections into sanitized host descriptors."""
        props = node.properties or {}
        ls_type = props.get("type", "Service")
        conn_props = props.get("connection_properties", {}) or {}

        host = (
            conn_props.get("server")
            or conn_props.get("accountEndpoint")
            or conn_props.get("domain")
            or conn_props.get("baseUrl")
            or conn_props.get("serviceUri")
            or "Vault"
        )
        return f"LS:{node.name}[{ls_type}] Host:{str(host)[:50]}"
