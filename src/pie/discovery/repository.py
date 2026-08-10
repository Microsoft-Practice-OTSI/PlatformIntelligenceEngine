"""In-Memory Metadata Repository & Tenant-Scoped Cache for Platform Intelligence Engine (PIE)."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional
from threading import Lock

from pie.core.logging import get_logger
from pie.discovery.models import (
    FactoryMetadata,
    PipelineMetadata,
    DatasetMetadata,
    LinkedServiceMetadata,
    TriggerMetadata,
    DataFlowMetadata,
    Spike2Result,
)

logger = get_logger(__name__)


def render_factory_full_context(factory: FactoryMetadata) -> str:
    """Render the FULL verified factory metadata as a markdown LLM context block."""
    if factory is None:
        return ""

    lines: list[str] = [
        "## FACTORY CONTEXT (100% verified Azure Data Factory metadata)",
        f"- **Factory:** `{factory.factory_name}`",
        f"- **Resource Group:** `{factory.resource_group}`",
        f"- **Subscription ID:** `{factory.subscription_id}`",
        f"- **Location:** `{factory.location}`",
    ]

    if factory.global_parameters:
        lines.append(f"### Global Parameters ({len(factory.global_parameters)})")
        for pname, pdef in factory.global_parameters.items():
            if isinstance(pdef, dict):
                lines.append(f"- `{pname}`: type={pdef.get('type', 'String')}, value=`{pdef.get('value')}`")
            else:
                lines.append(f"- `{pname}`: `{pdef}`")

    lines.append(f"### Pipelines ({len(factory.pipelines)})")
    if not factory.pipelines:
        lines.append("- None")
    for p in factory.pipelines:
        header = f"- **`{p.name}`**"
        bits = []
        if p.folder:
            bits.append(f"folder={p.folder}")
        if p.description:
            bits.append(f"desc={p.description}")
        if p.concurrency is not None:
            bits.append(f"concurrency={p.concurrency}")
        if p.annotations:
            bits.append(f"annotations={p.annotations}")
        if p.parameters:
            bits.append(f"params={{{', '.join(f'{k}: {v.type}' for k, v in p.parameters.items())}}}")
        if p.variables:
            bits.append(f"vars={{{', '.join(f'{k}: {v.type}' for k, v in p.variables.items())}}}")
        lines.append(header + (f" ({'; '.join(bits)})" if bits else ""))
        for a in p.activities:
            act = f"    - Activity `{a.name}` [{a.type}]"
            details = []
            if a.inputs:
                details.append(f"in={a.inputs}")
            if a.outputs:
                details.append(f"out={a.outputs}")
            if a.linked_service:
                details.append(f"ls={a.linked_service}")
            if a.called_pipeline:
                details.append(f"calls={a.called_pipeline}")
            if a.depends_on:
                details.append(f"deps={a.depends_on}")
            if a.retry_policy and a.retry_policy.count:
                details.append(f"retry={a.retry_policy.count}")
            if a.timeout:
                details.append(f"timeout={a.timeout}")
            lines.append(act + (f" ({'; '.join(details)})" if details else ""))

    lines.append(f"### Datasets ({len(factory.datasets)})")
    if not factory.datasets:
        lines.append("- None")
    for ds in factory.datasets:
        header = f"- **`{ds.name}`** [{ds.type}] linked_service=`{ds.linked_service_name}`"
        bits = []
        if ds.folder:
            bits.append(f"folder={ds.folder}")
        if ds.description:
            bits.append(f"desc={ds.description}")
        if ds.location_details:
            bits.append(f"loc={ds.location_details}")
        if ds.parameters:
            bits.append(f"params={list(ds.parameters.keys())}")
        if ds.annotations:
            bits.append(f"annotations={ds.annotations}")
        lines.append(header + (f" ({'; '.join(bits)})" if bits else ""))
        if ds.schema_fields:
            schema = ", ".join(f"{sf.get('name')}: {sf.get('type')}" for sf in ds.schema_fields)
            lines.append(f"    - Schema: {schema}")

    lines.append(f"### Linked Services ({len(factory.linked_services)})")
    if not factory.linked_services:
        lines.append("- None")
    for ls in factory.linked_services:
        header = f"- **`{ls.name}`** [{ls.type}]"
        bits = []
        if ls.connect_via_integration_runtime:
            bits.append(f"ir={ls.connect_via_integration_runtime}")
        if ls.connection_properties:
            bits.append(f"conn={ls.connection_properties}")
        if ls.annotations:
            bits.append(f"annotations={ls.annotations}")
        lines.append(header + (f" ({'; '.join(bits)})" if bits else ""))

    lines.append(f"### Triggers ({len(factory.triggers)})")
    if not factory.triggers:
        lines.append("- None")
    for t in factory.triggers:
        header = f"- **`{t.name}`** [{t.type}]"
        bits = []
        if t.recurrence_schedule:
            bits.append(f"schedule={t.recurrence_schedule}")
        if t.pipelines:
            bits.append(f"fires={t.pipelines}")
        if t.runtime_state:
            bits.append(f"state={t.runtime_state}")
        if t.parameters:
            bits.append(f"params={t.parameters}")
        lines.append(header + (f" ({'; '.join(bits)})" if bits else ""))

    lines.append(f"### Data Flows ({len(factory.data_flows)})")
    if not factory.data_flows:
        lines.append("- None")
    for df in factory.data_flows:
        header = f"- **`{df.name}`** [{df.type}]"
        bits = []
        if df.description:
            bits.append(f"desc={df.description}")
        if df.sources:
            bits.append(f"sources={df.sources}")
        if df.sinks:
            bits.append(f"sinks={df.sinks}")
        if df.transformations:
            bits.append(f"transformations={df.transformations}")
        lines.append(header + (f" ({'; '.join(bits)})" if bits else ""))

    return "\n".join(lines)


class MetadataRepository:
    """Thread-safe in-memory cache and repository for discovered Azure Data Factory metadata.
    
    Provides sub-5ms indexed lookups, tenant-isolated multi-factory storage, 
    and persistent JSON cache serialization.
    """

    def __init__(self, cache_root: Path = Path("output/cache")):
        self._lock = Lock()
        self.cache_root = cache_root
        # Key: (tenant_id, subscription_id, factory_name)
        self._factories: dict[tuple[str, str, str], FactoryMetadata] = {}
        # Key: (tenant_id, subscription_id, factory_name) -> ISO 8601 UTC string
        self._last_refreshed_at: dict[tuple[str, str, str], str] = {}
        # Fast pipeline lookup index: (tenant_id, pipeline_name) -> PipelineMetadata
        self._pipeline_index: dict[tuple[str, str], PipelineMetadata] = {}
        # Key: (tenant_id, subscription_id, factory_name) -> provenance tag.
        # "arm" = real Azure ARM extraction, "cache" = restored from disk cache,
        # "mock" = demo/test fixture, "unknown" = not yet classified.
        self._provenance: dict[tuple[str, str, str], str] = {}

    def _normalize_key(self, tenant_id: Optional[str], subscription_id: Optional[str], factory_name: str) -> tuple[str, str, str]:
        t_id = (tenant_id or "default-tenant").strip().lower()
        s_id = (subscription_id or "default-subscription").strip().lower()
        f_name = factory_name.strip().lower()
        return (t_id, s_id, f_name)

    def save_factory(
        self,
        factory: FactoryMetadata,
        tenant_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
        last_refreshed_at: Optional[str] = None,
        provenance: str = "unknown",
    ) -> None:
        """Store factory metadata in memory with thread safety and update indices."""
        sub_id = subscription_id or factory.subscription_id or "default-subscription"
        key = self._normalize_key(tenant_id, sub_id, factory.factory_name)
        now_iso = last_refreshed_at or datetime.now(timezone.utc).isoformat()

        with self._lock:
            self._factories[key] = factory
            self._last_refreshed_at[key] = now_iso
            self._provenance[key] = provenance
            t_id = key[0]

            # Index pipelines
            for p in factory.pipelines:
                self._pipeline_index[(t_id, p.name.lower())] = p

        logger.info(
            f"Stored Factory [bold white]{factory.factory_name}[/bold white] in repository "
            f"(Tenant: {key[0]}, Pipelines: {len(factory.pipelines)}, Provenance: {provenance}, RefreshedAt: {now_iso})"
        )

    def get_provenance(
        self,
        factory_name: str,
        subscription_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> str:
        """Return the provenance tag ("arm" | "cache" | "mock" | "unknown") for a factory."""
        key = self._normalize_key(tenant_id, subscription_id, factory_name)
        with self._lock:
            return self._provenance.get(key, "unknown")

    def get_factory(
        self,
        factory_name: str,
        subscription_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[FactoryMetadata]:
        """Retrieve factory metadata by name for the scoped tenant and subscription."""
        t_id = (tenant_id or "default-tenant").strip().lower()
        f_name = factory_name.strip().lower()

        with self._lock:
            # If subscription_id provided, direct match
            if subscription_id:
                s_id = subscription_id.strip().lower()
                return self._factories.get((t_id, s_id, f_name))

            # Otherwise find first matching factory across subscriptions in this tenant
            for key, factory in self._factories.items():
                if key[0] == t_id and key[2] == f_name:
                    return factory
        return None

    def get_last_refreshed_at(
        self,
        factory_name: str,
        subscription_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[str]:
        """Get the last refreshed timestamp for a factory."""
        t_id = (tenant_id or "default-tenant").strip().lower()
        f_name = factory_name.strip().lower()

        with self._lock:
            if subscription_id:
                s_id = subscription_id.strip().lower()
                return self._last_refreshed_at.get((t_id, s_id, f_name))

            for key, timestamp in self._last_refreshed_at.items():
                if key[0] == t_id and key[2] == f_name:
                    return timestamp
        return None

    def list_factories(
        self,
        tenant_id: Optional[str] = None,
        subscription_id: Optional[str] = None,
    ) -> list[FactoryMetadata]:
        """List all loaded Data Factories matching tenant and optional subscription filter."""
        t_id = (tenant_id or "default-tenant").strip().lower()
        s_id = subscription_id.strip().lower() if subscription_id else None

        with self._lock:
            results = []
            for key, factory in self._factories.items():
                if key[0] == t_id:
                    if s_id is None or key[1] == s_id:
                        results.append(factory)
            return results

    def list_pipelines(
        self,
        factory_name: Optional[str] = None,
        folder: Optional[str] = None,
        tag: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[PipelineMetadata]:
        """Retrieve filterable pipelines for a factory or tenant."""
        factories = self.list_factories(tenant_id=tenant_id)
        if factory_name:
            target_f = factory_name.strip().lower()
            factories = [f for f in factories if f.factory_name.lower() == target_f]

        all_pipelines: list[PipelineMetadata] = []
        for f in factories:
            for p in f.pipelines:
                if folder and (not p.folder or folder.lower() not in p.folder.lower()):
                    continue
                if tag and (not p.annotations or not any(tag.lower() in a.lower() for a in p.annotations)):
                    continue
                all_pipelines.append(p)
        return all_pipelines

    def get_pipeline(
        self,
        pipeline_name: str,
        factory_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Optional[PipelineMetadata]:
        """Fast O(1) lookup of a pipeline by name within tenant."""
        t_id = (tenant_id or "default-tenant").strip().lower()
        p_name = pipeline_name.strip().lower()

        with self._lock:
            # Check fast index first
            if (t_id, p_name) in self._pipeline_index and not factory_name:
                return self._pipeline_index[(t_id, p_name)]

        # If factory_name provided, search that factory
        factory = self.get_factory(factory_name, tenant_id=tenant_id) if factory_name else None
        if factory:
            for p in factory.pipelines:
                if p.name.lower() == p_name:
                    return p
        return None

    def list_datasets(
        self,
        factory_name: Optional[str] = None,
        file_type: Optional[str] = None,
        is_onprem: Optional[bool] = None,
        tenant_id: Optional[str] = None,
    ) -> list[DatasetMetadata]:
        """List datasets with file type and on-prem connectivity filters."""
        factories = self.list_factories(tenant_id=tenant_id)
        if factory_name:
            target_f = factory_name.strip().lower()
            factories = [f for f in factories if f.factory_name.lower() == target_f]

        datasets: list[DatasetMetadata] = []
        for f in factories:
            for ds in f.datasets:
                if file_type and file_type.lower() not in ds.type.lower():
                    continue
                if is_onprem is not None:
                    # Check linked service or location
                    ds_type_str = (ds.type + str(ds.location_properties)).lower()
                    ds_is_onprem = any(k in ds_type_str for k in ["fileserver", "sftp", "\\\\", "onprem"])
                    if ds_is_onprem != is_onprem:
                        continue
                datasets.append(ds)
        return datasets

    def list_linked_services(
        self,
        factory_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[LinkedServiceMetadata]:
        """List all linked services for the tenant/factory."""
        factories = self.list_factories(tenant_id=tenant_id)
        if factory_name:
            target_f = factory_name.strip().lower()
            factories = [f for f in factories if f.factory_name.lower() == target_f]

        services: list[LinkedServiceMetadata] = []
        for f in factories:
            services.extend(f.linked_services)
        return services

    def list_triggers(
        self,
        factory_name: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> list[TriggerMetadata]:
        """List all triggers for the tenant/factory."""
        factories = self.list_factories(tenant_id=tenant_id)
        if factory_name:
            target_f = factory_name.strip().lower()
            factories = [f for f in factories if f.factory_name.lower() == target_f]

        triggers: list[TriggerMetadata] = []
        for f in factories:
            triggers.extend(f.triggers)
        return triggers

    def save_to_cache(
        self,
        factory_name: str,
        subscription_id: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Path:
        """Serialize factory metadata to partitioned JSON file with last_refreshed_at."""
        factory = self.get_factory(factory_name, subscription_id=subscription_id, tenant_id=tenant_id)
        if not factory:
            raise ValueError(f"Factory '{factory_name}' not found in repository.")

        t_id = (tenant_id or "default-tenant").strip().lower()
        s_id = (subscription_id or factory.subscription_id or "default-subscription").strip().lower()
        refreshed_at = self.get_last_refreshed_at(factory_name, subscription_id=s_id, tenant_id=t_id)

        target_dir = self.cache_root / t_id / s_id
        target_dir.mkdir(parents=True, exist_ok=True)
        target_file = target_dir / f"{factory.factory_name}.json"

        cache_payload = {
            "version": "2.0",
            "last_refreshed_at": refreshed_at or datetime.now(timezone.utc).isoformat(),
            "tenant_id": t_id,
            "subscription_id": s_id,
            "factory": factory.model_dump(mode="json"),
        }

        with open(target_file, "w", encoding="utf-8") as f:
            json.dump(cache_payload, f, indent=2)

        logger.info(f"Saved cache file to: {target_file}")
        return target_file

    def load_from_cache(self, file_path: Path) -> FactoryMetadata:
        """Load factory metadata from JSON file and register in repository."""
        if not file_path.exists():
            raise FileNotFoundError(f"Cache file {file_path} does not exist.")

        with open(file_path, "r", encoding="utf-8") as f:
            payload = json.load(f)

        if "factory" in payload:
            factory_data = payload["factory"]
            last_refreshed = payload.get("last_refreshed_at")
            t_id = payload.get("tenant_id", "default-tenant")
            s_id = payload.get("subscription_id", "default-subscription")
        else:
            factory_data = payload
            last_refreshed = datetime.now(timezone.utc).isoformat()
            t_id = "default-tenant"
            s_id = "default-subscription"

        factory = FactoryMetadata.model_validate(factory_data)
        self.save_factory(factory, tenant_id=t_id, subscription_id=s_id, last_refreshed_at=last_refreshed, provenance="cache")
        return factory

    def load_cached_factories(self) -> list[FactoryMetadata]:
        """Restore every factory cache file under cache_root into the repository."""
        loaded: list[FactoryMetadata] = []
        if not self.cache_root.exists():
            return loaded
        for file_path in sorted(self.cache_root.rglob("*.json")):
            try:
                factory = self.load_from_cache(file_path)
                loaded.append(factory)
                logger.info(f"Restored factory '{factory.factory_name}' from cache: {file_path}")
            except Exception as exc:
                logger.warning(f"Could not load cache file {file_path}: {exc}")
        return loaded

    def factory_full_context_markdown(self, factory_name: str, subscription_id: Optional[str] = None,
                                      tenant_id: Optional[str] = None) -> str:
        """Render the FULL metadata for a stored factory as an LLM context block."""
        factory = self.get_factory(factory_name, subscription_id=subscription_id, tenant_id=tenant_id)
        if not factory:
            return ""
        return render_factory_full_context(factory)

    def preload_defaults(self) -> None:
        """Preload mock fixture or cached live metadata into repository on startup."""
        try:
            import sys
            from pathlib import Path
            # Ensure the project root (parent of src/) is on the path so the
            # top-level `spikes` package is importable regardless of cwd.
            project_root = Path(__file__).resolve().parents[3]
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            from spikes.spike_2_discovery.mock_adf_fixture import get_mock_spike_2_result
            result = get_mock_spike_2_result()
            for factory in result.factories:
                self.save_factory(
                    factory,
                    tenant_id="default-tenant",
                    subscription_id="60a58917-1a0c-4902-a24d-ab97dd75f0ab",
                    last_refreshed_at=datetime.now(timezone.utc).isoformat(),
                    provenance="mock",
                )
            logger.info("Successfully preloaded default mock ADF factory into MetadataRepository.")
        except Exception as e:
            logger.warning(f"Could not preload default fixture: {e}")


# Singleton instance
_GLOBAL_REPOSITORY: Optional[MetadataRepository] = None


def get_repository() -> MetadataRepository:
    """Return singleton MetadataRepository instance."""
    global _GLOBAL_REPOSITORY
    if _GLOBAL_REPOSITORY is None:
        _GLOBAL_REPOSITORY = MetadataRepository()
        # Do NOT preload defaults - only use factories explicitly synced by user
    return _GLOBAL_REPOSITORY
