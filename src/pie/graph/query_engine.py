"""Multi-Dimensional Asset Query Engine: Filters and discovers datasets, pipelines,
and linked services by file type (csv/parquet/json), connectivity (onprem/cloud),
schema attributes, and storage mechanisms.
"""

from typing import Any
from pie.graph.models import NodeType, EdgeType, GraphNode
from pie.graph.builder import KnowledgeGraph


class AssetQueryEngine:
    """Answers complex multi-criteria asset discovery questions across the Knowledge Graph."""

    def __init__(self, graph: KnowledgeGraph):
        self.graph = graph

    def find_datasets(
        self,
        file_type: str | None = None,
        connectivity: str | None = None,
        linked_service_name: str | None = None,
        folder: str | None = None,
        column_name: str | None = None,
    ) -> list[dict[str, Any]]:
        """Find datasets matching criteria like 'onprem', 'csv', specific folder, or column schema."""
        matches: list[dict[str, Any]] = []

        for node in self.graph.nodes.values():
            if node.type != NodeType.DATASET:
                continue

            props = node.properties or {}
            ds_type = str(props.get("type", "")).lower()
            ls_name = str(props.get("linked_service_name", ""))
            ds_folder = str(node.folder or "").lower()

            # 1. Check File Type (e.g. 'csv' matches 'delimitedtext', 'csv')
            if file_type:
                ft = file_type.lower()
                is_csv = ft in ["csv", "delimitedtext", "text"] and any(
                    x in ds_type for x in ["delimitedtext", "csv", "text"]
                )
                is_parquet = ft in ["parquet"] and "parquet" in ds_type
                is_json = ft in ["json"] and "json" in ds_type
                is_sql = ft in ["sql", "table"] and "sql" in ds_type

                if not (is_csv or is_parquet or is_json or is_sql or ft in ds_type):
                    continue

            # 2. Check Linked Service Name
            if linked_service_name and linked_service_name.lower() not in ls_name.lower():
                continue

            # 3. Check Folder
            if folder and folder.lower() not in ds_folder:
                continue

            # 4. Check Connectivity (e.g. 'onprem', 'cloud', 'adls', 'blob', 'fileserver', 'sftp')
            ls_node = self.graph.get_node(f"linked_service:{ls_name}")
            ls_props = ls_node.properties if ls_node else {}
            ls_type = str(ls_props.get("type", "")).lower()
            conn_props = ls_props.get("connection_properties", {}) or {}
            host_str = str(conn_props).lower()

            is_onprem = False
            # Check on-premises indicators: FileServer, unc path (\\\\), on-prem SQL, or self-hosted integration runtime
            if any(x in ls_type for x in ["fileserver", "sftp", "ftpserver"]) or "\\\\" in host_str:
                is_onprem = True
            elif "connect_via_integration_runtime" in ls_props and ls_props["connect_via_integration_runtime"]:
                if "shir" in str(ls_props["connect_via_integration_runtime"]).lower():
                    is_onprem = True

            if connectivity:
                c = connectivity.lower()
                if c == "onprem" and not is_onprem:
                    continue
                if c == "cloud" and is_onprem:
                    continue

            # 5. Check Column Schema
            if column_name:
                schema_fields = props.get("schema_fields", []) or []
                found_col = any(
                    column_name.lower() in str(f.get("name", "")).lower() for f in schema_fields if isinstance(f, dict)
                )
                if not found_col:
                    continue

            # Find pipelines that consume or produce this dataset
            consumer_pipelines: set[str] = set()
            producer_pipelines: set[str] = set()

            for edge in self.graph.get_incoming_edges(node.id):
                src_node = self.graph.get_node(edge.source_id)
                if src_node and src_node.type == NodeType.PIPELINE:
                    if edge.type == EdgeType.READS:
                        consumer_pipelines.add(src_node.name)
                    elif edge.type == EdgeType.WRITES:
                        producer_pipelines.add(src_node.name)

            matches.append(
                {
                    "dataset_name": node.name,
                    "dataset_type": props.get("type"),
                    "folder": node.folder or "Root",
                    "linked_service": ls_name,
                    "linked_service_type": ls_type,
                    "is_onprem": is_onprem,
                    "host_or_endpoint": host_str[:120] if host_str else "Configured",
                    "consumed_by_pipelines": sorted(list(consumer_pipelines)),
                    "produced_by_pipelines": sorted(list(producer_pipelines)),
                }
            )

        return matches

    def find_pipelines_by_criteria(
        self,
        uses_dataset: str | None = None,
        connects_to_service: str | None = None,
        has_trigger: bool | None = None,
        folder: str | None = None,
    ) -> list[dict[str, Any]]:
        """Search pipelines by connected services, dataset dependencies, or schedule state."""
        matches: list[dict[str, Any]] = []

        for node in self.graph.nodes.values():
            if node.type != NodeType.PIPELINE:
                continue

            # Check Folder
            if folder and folder.lower() not in str(node.folder or "").lower():
                continue

            # Check Datasets used
            datasets_read: list[str] = []
            datasets_written: list[str] = []
            triggers: list[str] = []
            linked_services: set[str] = set()

            for edge in self.graph.get_outgoing_edges(node.id):
                if edge.type == EdgeType.READS:
                    datasets_read.append(edge.target_id.replace("dataset:", ""))
                elif edge.type == EdgeType.WRITES:
                    datasets_written.append(edge.target_id.replace("dataset:", ""))
                elif edge.type == EdgeType.USES:
                    linked_services.add(edge.target_id.replace("linked_service:", ""))

            for edge in self.graph.get_incoming_edges(node.id):
                if edge.type == EdgeType.EXECUTES:
                    triggers.append(edge.source_id.replace("trigger:", ""))

            if uses_dataset:
                all_ds = [d.lower() for d in datasets_read + datasets_written]
                if uses_dataset.lower() not in all_ds:
                    continue

            if connects_to_service:
                all_ls = [ls.lower() for ls in linked_services]
                if connects_to_service.lower() not in all_ls:
                    continue

            if has_trigger is not None:
                if has_trigger and not triggers:
                    continue
                if not has_trigger and triggers:
                    continue

            matches.append(
                {
                    "pipeline_name": node.name,
                    "folder": node.folder or "Root",
                    "activity_count": node.properties.get("activity_count", 0),
                    "datasets_read": datasets_read,
                    "datasets_written": datasets_written,
                    "linked_services": sorted(list(linked_services)),
                    "triggers": triggers,
                }
            )

        return matches
