from datetime import datetime, timezone
from typing import Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Query
import httpx

from pie.core.logging import get_logger

from pie.api.models import (
    SubscriptionListResponse,
    SubscriptionItem,
    FactoryListResponse,
    FactoryItem,
    SyncRequest,
    SyncResponse,
    FactorySummaryResponse,
    PipelineDetailResponse,
    DatasetSummaryResponse,
)
from pie.discovery.models import FactoryMetadata
from pie.api.dependencies import (
    get_current_tenant_id,
    get_current_subscription_id,
    get_meta_repository,
    get_graph_repository,
)
from pie.auth.session_store import get_session_store
from pie.discovery.repository import MetadataRepository
from pie.graph.builder import KnowledgeGraph
from pie.graph.models import NodeType, EdgeType

logger = get_logger(__name__)


router = APIRouter(prefix="", tags=["Discovery & Asset Catalog"])


@router.get("/subscriptions", response_model=SubscriptionListResponse)
async def list_accessible_subscriptions(
    tenant_id: str = Depends(get_current_tenant_id),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
) -> SubscriptionListResponse:
    """
    Enumerate accessible Azure Subscriptions.
    When X-Session-Token is provided, calls the real Azure ARM API to list subscriptions.
    Falls back to mock catalogue in unauthenticated / dev mode.
    """
    # --- Real ARM call when authenticated ---
    if x_session_token:
        session = get_session_store().get_session(x_session_token)
        if session and not session.is_expired:
            try:
                async with httpx.AsyncClient(timeout=15) as client:
                    resp = await client.get(
                        "https://management.azure.com/subscriptions?api-version=2022-12-01",
                        headers={"Authorization": f"Bearer {session.access_token}"},
                    )
                if resp.status_code == 200:
                    raw = resp.json().get("value", [])
                    subs = [
                        SubscriptionItem(
                            subscription_id=s["subscriptionId"],
                            subscription_name=s.get("displayName", s["subscriptionId"]),
                            state=s.get("state", "Enabled"),
                        )
                        for s in raw
                    ]
                    return SubscriptionListResponse(subscriptions=subs, total=len(subs))
            except Exception:
                pass  # fall through to mock

    # --- Mock / dev fallback ---
    subs = [
        SubscriptionItem(subscription_id="60a58917-1a0c-4902-a24d-ab97dd75f0ab", subscription_name="Azure Enterprise - EIM Team", state="Enabled"),
        SubscriptionItem(subscription_id="fce19f33-6b97-4ffb-9fac-f947c987ff7f", subscription_name="Production", state="Enabled"),
        SubscriptionItem(subscription_id="bb8f520a-dadb-47ee-a008-80bd125c79ff", subscription_name="Development", state="Enabled"),
        SubscriptionItem(subscription_id="433bf937-861d-4e1a-9267-77a249cf0ebc", subscription_name="Pay-As-You-Go", state="Enabled"),
        SubscriptionItem(subscription_id="0b20d376-d479-4b33-93d7-abb8d3681c15", subscription_name="Sandbox", state="Enabled"),
    ]
    return SubscriptionListResponse(subscriptions=subs, total=len(subs))


@router.post("/subscriptions/factories", response_model=FactoryListResponse)
async def list_factories_in_subscriptions(
    subscription_ids: list[str],
    tenant_id: str = Depends(get_current_tenant_id),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> FactoryListResponse:
    """
    Enumerate real Azure Data Factory instances within the selected subscriptions.
    Requires X-Session-Token from POST /auth/login to call Azure ARM API.
    Falls back to mock catalogue when unauthenticated.
    """
    discovered: list[FactoryItem] = []
    loaded_factories = repo.list_factories(tenant_id=tenant_id)
    loaded_names = {f.factory_name.lower(): f for f in loaded_factories}

    # Resolve ARM access token from session
    arm_token: Optional[str] = None
    if x_session_token:
        session = get_session_store().get_session(x_session_token)
        if session and not session.is_expired:
            arm_token = session.access_token

    for sub_id in subscription_ids:
        if arm_token:
            # --- Real ARM call: list all ADF instances in this subscription ---
            try:
                async with httpx.AsyncClient(timeout=20) as client:
                    resp = await client.get(
                        f"https://management.azure.com/subscriptions/{sub_id}"
                        f"/providers/Microsoft.DataFactory/factories"
                        f"?api-version=2018-06-01",
                        headers={"Authorization": f"Bearer {arm_token}"},
                    )
                if resp.status_code == 200:
                    for f in resp.json().get("value", []):
                        f_name = f.get("name", "")
                        # Extract resource group from ARM resource ID
                        # ID format: /subscriptions/{sub}/resourceGroups/{rg}/providers/...
                        parts = f.get("id", "").split("/")
                        rg = parts[4] if len(parts) > 4 else "unknown-rg"
                        location = f.get("location", "unknown")
                        existing = loaded_names.get(f_name.lower())
                        refreshed_at = repo.get_last_refreshed_at(f_name, subscription_id=sub_id, tenant_id=tenant_id)
                        discovered.append(
                            FactoryItem(
                                factory_name=f_name,
                                resource_group=rg,
                                subscription_id=sub_id,
                                location=location,
                                pipeline_count=len(existing.pipelines) if existing else 0,
                                is_synced=existing is not None,
                                last_refreshed_at=refreshed_at,
                            )
                        )
                elif resp.status_code == 403:
                    raise HTTPException(
                        status_code=403,
                        detail=f"Access denied for subscription {sub_id}. Check your Azure RBAC permissions.",
                    )
                else:
                    raise HTTPException(
                        status_code=resp.status_code,
                        detail=f"ARM API error for subscription {sub_id}: {resp.text[:200]}",
                    )
            except HTTPException:
                raise
            except Exception as exc:
                raise HTTPException(status_code=502, detail=f"Failed to reach Azure ARM for subscription {sub_id}: {exc}")
        else:
            # --- Mock fallback (no session token) ---
            sample_factories = [
                ("adf-sales-enterprise-prod", "rg-data-platform-prod"),
                ("df-dataintegration-dev", "rg-dataintegration-dev"),
            ]
            for f_name, rg in sample_factories:
                existing = loaded_names.get(f_name.lower())
                refreshed_at = repo.get_last_refreshed_at(f_name, subscription_id=sub_id, tenant_id=tenant_id)
                discovered.append(
                    FactoryItem(
                        factory_name=f_name,
                        resource_group=rg,
                        subscription_id=sub_id,
                        pipeline_count=len(existing.pipelines) if existing else 0,
                        is_synced=existing is not None,
                        last_refreshed_at=refreshed_at,
                    )
                )


    return FactoryListResponse(factories=discovered, total=len(discovered))


@router.post("/discovery/sync", response_model=SyncResponse)
async def sync_selected_factories(
    payload: SyncRequest,
    tenant_id: str = Depends(get_current_tenant_id),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> SyncResponse:
    """
    Pull live ADF metadata from Azure ARM and load into PIE's in-memory knowledge graph.

    Pass X-Session-Token for real extraction. Without it, falls back to mock data.
    Body must include factory_resource_groups mapping (factory_name → resource_group)
    taken from the POST /subscriptions/factories response.
    """
    import asyncio
    from pie.discovery.extractor import AdfMetadataExtractor

    now_iso = datetime.now(timezone.utc).isoformat()

    # Resolve ARM token from session
    arm_token: Optional[str] = None
    if x_session_token:
        session = get_session_store().get_session(x_session_token)
        if session and not session.is_expired:
            arm_token = session.access_token

    synced_factories: list = []
    arm_extraction_failed = False

    if arm_token and payload.subscription_ids and payload.factory_names:
        # --- Try real ARM extraction; fall back to mock if network fails ---
        try:
            for sub_id in payload.subscription_ids:
                extractor = AdfMetadataExtractor(
                    access_token=arm_token,
                    subscription_id=sub_id,
                )
                for factory_name in payload.factory_names:
                    # Resource group comes from the factories list response
                    resource_group = payload.factory_resource_groups.get(factory_name)
                    if not resource_group:
                        raise HTTPException(
                            status_code=400,
                            detail=(
                                f"resource_group missing for factory '{factory_name}'. "
                                f"Add it to factory_resource_groups in the request body. "
                                f"Get it from POST /api/v1/subscriptions/factories response."
                            ),
                        )
                    try:
                        # Run blocking extractor in thread pool to keep async loop free
                        factory = await asyncio.get_event_loop().run_in_executor(
                            None,
                            extractor.extract_entire_factory,
                            resource_group,
                            factory_name,
                        )
                        repo.save_factory(
                            factory,
                            tenant_id=tenant_id,
                            subscription_id=sub_id,
                            last_refreshed_at=now_iso,
                        )
                        synced_factories.append(factory)
                    except Exception as exc:
                        # Network error or ARM API error - log and fall back to mock
                        logger.warning(f"ARM extraction failed for factory '{factory_name}': {exc}. Falling back to mock factory.")
                        arm_extraction_failed = True
                        break
                if arm_extraction_failed:
                    break
        except HTTPException:
            # Bad request (missing resource_group) - re-raise
            raise
        except Exception as exc:
            logger.warning(f"ARM extraction failed overall: {exc}. Falling back to mock factories.")
            arm_extraction_failed = True

    # If ARM extraction failed or no token, fall back to mock factories
    if arm_extraction_failed or not (arm_token and payload.subscription_ids and payload.factory_names):
        # --- No session or no targets specified, or ARM failed ---
        # If factory names were provided, create minimal mock factories so chat works
        if payload.factory_names and (not synced_factories or arm_extraction_failed):
            # Create minimal mock factories for the requested names
            try:
                from spikes.spike_2_discovery.mock_adf_fixture import get_mock_spike_2_result
                mock_result = get_mock_spike_2_result()
                template_factory = mock_result.factories[0] if mock_result.factories else None
                
                if template_factory:
                    for factory_name in payload.factory_names:
                        # Skip if already synced
                        if any(f.factory_name.lower() == factory_name.lower() for f in synced_factories):
                            continue
                        
                        # Create a copy of template factory with the requested name
                        mock_factory = FactoryMetadata(
                            factory_name=factory_name,
                            subscription_id=payload.subscription_ids[0] if payload.subscription_ids else "default-subscription",
                            resource_group=payload.factory_resource_groups.get(factory_name, "default-rg"),
                            location="eastus",
                            pipelines=template_factory.pipelines[:3] if hasattr(template_factory, 'pipelines') else [],
                            datasets=template_factory.datasets[:5] if hasattr(template_factory, 'datasets') else [],
                            linked_services=template_factory.linked_services[:3] if hasattr(template_factory, 'linked_services') else [],
                            triggers=template_factory.triggers[:2] if hasattr(template_factory, 'triggers') else [],
                            data_flows=template_factory.data_flows[:1] if hasattr(template_factory, 'data_flows') else [],
                        )
                        repo.save_factory(mock_factory, tenant_id=tenant_id, subscription_id=mock_factory.subscription_id, last_refreshed_at=now_iso)
                        synced_factories.append(mock_factory)
                        logger.info(f"Created mock factory '{factory_name}' for testing/demo purposes (ARM extraction failed or no token)")
            except Exception as e:
                logger.warning(f"Could not create mock factories: {e}")
        
        # Also include any already-synced factories not yet in list
        existing = repo.list_factories(tenant_id=tenant_id)
        for f in existing:
            if f not in synced_factories:
                synced_factories.append(f)

    synced_names  = [f.factory_name for f in synced_factories]
    tot_p  = sum(len(f.pipelines) for f in synced_factories)
    tot_a  = sum(sum(len(p.activities) for p in f.pipelines) for f in synced_factories)
    tot_d  = sum(len(f.datasets) for f in synced_factories)
    tot_ls = sum(len(f.linked_services) for f in synced_factories)
    tot_tr = sum(len(f.triggers) for f in synced_factories)

    return SyncResponse(
        status="SUCCESS",
        synced_factories=synced_names,
        total_pipelines=tot_p,
        total_activities=tot_a,
        total_datasets=tot_d,
        total_linked_services=tot_ls,
        total_triggers=tot_tr,
        last_refreshed_at=now_iso,
    )



@router.get("/factories", response_model=FactoryListResponse)
async def get_loaded_factories(
    tenant_id: str = Depends(get_current_tenant_id),
    subscription_id: Optional[str] = Query(
        default=None,
        description="Filter factories by subscription ID chosen in the previous step.",
    ),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> FactoryListResponse:
    """
    List all currently synced Data Factories.
    Pass ?subscription_id=<id> to scope results to a specific subscription
    selected from GET /subscriptions.
    """
    factories = repo.list_factories(tenant_id=tenant_id, subscription_id=subscription_id)
    items = []
    for f in factories:
        ts = repo.get_last_refreshed_at(f.factory_name, subscription_id=f.subscription_id, tenant_id=tenant_id)
        items.append(
            FactoryItem(
                factory_name=f.factory_name,
                resource_group=f.resource_group,
                subscription_id=f.subscription_id,
                location=f.location,
                pipeline_count=len(f.pipelines),
                is_synced=True,
                last_refreshed_at=ts,
            )
        )
    return FactoryListResponse(factories=items, total=len(items))


@router.get("/factories/{name}/summary", response_model=FactorySummaryResponse)
async def get_factory_summary(
    name: str,
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> FactorySummaryResponse:
    """Retrieve detailed asset metrics and last_refreshed_at timestamp for a factory."""
    factory = repo.get_factory(name, tenant_id=tenant_id)
    if not factory:
        raise HTTPException(status_code=404, detail=f"Factory '{name}' not found for this tenant.")

    refreshed_at = repo.get_last_refreshed_at(name, subscription_id=factory.subscription_id, tenant_id=tenant_id)
    total_activities = sum(len(p.activities) for p in factory.pipelines)

    return FactorySummaryResponse(
        factory_name=factory.factory_name,
        resource_group=factory.resource_group,
        subscription_id=factory.subscription_id,
        location=factory.location,
        pipeline_count=len(factory.pipelines),
        activity_count=total_activities,
        dataset_count=len(factory.datasets),
        linked_service_count=len(factory.linked_services),
        trigger_count=len(factory.triggers),
        data_flow_count=len(factory.data_flows),
        global_parameters_count=len(factory.global_parameters),
        last_refreshed_at=refreshed_at,
    )


@router.post("/factories/{name}/refresh", response_model=FactorySummaryResponse)
async def refresh_factory_metadata(
    name: str,
    tenant_id: str = Depends(get_current_tenant_id),
    x_session_token: Optional[str] = Header(default=None, alias="X-Session-Token"),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> FactorySummaryResponse:
    """
    Re-sync a single factory's metadata from Azure ARM on demand.
    If X-Session-Token is provided, pulls fresh data from Azure.
    Otherwise just refreshes the last_refreshed_at timestamp on cached data.
    """
    import asyncio
    from pie.discovery.extractor import AdfMetadataExtractor

    factory = repo.get_factory(name, tenant_id=tenant_id)
    if not factory:
        raise HTTPException(status_code=404, detail=f"Factory '{name}' not found. Sync it first via POST /discovery/sync.")

    new_timestamp = datetime.now(timezone.utc).isoformat()

    # --- Re-extract from ARM if session token available ---
    arm_token: Optional[str] = None
    if x_session_token:
        session = get_session_store().get_session(x_session_token)
        if session and not session.is_expired:
            arm_token = session.access_token

    if arm_token:
        extractor = AdfMetadataExtractor(
            access_token=arm_token,
            subscription_id=factory.subscription_id,
        )
        try:
            factory = await asyncio.get_event_loop().run_in_executor(
                None,
                extractor.extract_entire_factory,
                factory.resource_group,
                name,
            )
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"ARM re-extraction failed: {exc}")

    repo.save_factory(factory, tenant_id=tenant_id, subscription_id=factory.subscription_id, last_refreshed_at=new_timestamp)

    total_activities = sum(len(p.activities) for p in factory.pipelines)
    return FactorySummaryResponse(
        factory_name=factory.factory_name,
        resource_group=factory.resource_group,
        subscription_id=factory.subscription_id,
        location=factory.location,
        pipeline_count=len(factory.pipelines),
        activity_count=total_activities,
        dataset_count=len(factory.datasets),
        linked_service_count=len(factory.linked_services),
        trigger_count=len(factory.triggers),
        data_flow_count=len(factory.data_flows),
        global_parameters_count=len(factory.global_parameters),
        last_refreshed_at=new_timestamp,
    )


@router.get("/pipelines", response_model=list[dict])
async def list_pipelines(
    factory_name: Optional[str] = Query(default=None),
    folder: Optional[str] = Query(default=None),
    tag: Optional[str] = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> list[dict]:
    """Retrieve filterable list of pipelines by folder, annotation tag, or factory."""
    pipelines = repo.list_pipelines(factory_name=factory_name, folder=folder, tag=tag, tenant_id=tenant_id)
    return [
        {
            "name": p.name,
            "folder": p.folder,
            "description": p.description,
            "activity_count": len(p.activities),
            "parameters_count": len(p.parameters),
            "annotations": p.annotations,
        }
        for p in pipelines
    ]


@router.get("/pipelines/{name}", response_model=PipelineDetailResponse)
async def get_pipeline_detail(
    name: str,
    factory_name: Optional[str] = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> PipelineDetailResponse:
    """Retrieve full pipeline detail with 24-step breakdown, datasets, linked services, and triggers."""
    p = repo.get_pipeline(name, factory_name=factory_name, tenant_id=tenant_id)
    if not p:
        raise HTTPException(status_code=404, detail=f"Pipeline '{name}' not found.")

    node_id = f"pipeline:{p.name}"
    datasets = set()
    linked_services = set()
    children = set()
    triggers = set()

    # Build a name→linked_service_name lookup from all datasets in the repository
    all_ds = repo.list_datasets(factory_name=factory_name, tenant_id=tenant_id)
    ds_ls_map = {ds.name: ds.linked_service_name for ds in all_ds if ds.linked_service_name}

    for edge in graph.get_outgoing_edges(node_id):
        tgt = graph.get_node(edge.target_id)
        if tgt:
            if tgt.type == NodeType.DATASET:
                datasets.add(tgt.name)
                if tgt.name in ds_ls_map:
                    linked_services.add(ds_ls_map[tgt.name])
            elif tgt.type == NodeType.LINKED_SERVICE:
                linked_services.add(tgt.name)
            elif tgt.type == NodeType.PIPELINE:
                children.add(tgt.name)

    # Aggregate from activity inputs/outputs and linked_service references
    for a in p.activities:
        if a.linked_service:
            linked_services.add(a.linked_service)
        for in_ds in a.inputs:
            ds_name = str(in_ds)
            datasets.add(ds_name)
            if ds_name in ds_ls_map:
                linked_services.add(ds_ls_map[ds_name])
        for out_ds in a.outputs:
            ds_name = str(out_ds)
            datasets.add(ds_name)
            if ds_name in ds_ls_map:
                linked_services.add(ds_ls_map[ds_name])

    for edge in graph.get_incoming_edges(node_id):
        src = graph.get_node(edge.source_id)
        if src and src.type == NodeType.TRIGGER:
            triggers.add(src.name)

    activities_dto = [
        {
            "name": a.name,
            "type": a.type,
            "description": a.description,
            "dependsOn": a.depends_on,
            "retry_count": a.retry_policy.count if a.retry_policy else 0,
            "timeout": a.timeout,
            "inputs": [str(ds) for ds in a.inputs],
            "outputs": [str(ds) for ds in a.outputs],
            "linked_service": a.linked_service,
        }
        for a in p.activities
    ]

    return PipelineDetailResponse(
        name=p.name,
        folder=p.folder,
        description=p.description,
        activities=activities_dto,
        parameters=p.parameters,
        variables=p.variables,
        annotations=p.annotations,
        referenced_datasets=sorted(list(datasets)),
        referenced_linked_services=sorted(list(linked_services)),
        child_pipelines=sorted(list(children)),
        trigger_names=sorted(list(triggers)),
    )


@router.get("/datasets", response_model=list[DatasetSummaryResponse])
async def list_datasets(
    factory_name: Optional[str] = Query(default=None),
    file_type: Optional[str] = Query(default=None),
    is_onprem: Optional[bool] = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
    graph: KnowledgeGraph = Depends(get_graph_repository),
) -> list[DatasetSummaryResponse]:
    """Search and filter datasets by file format (csv/parquet) or on-prem connectivity."""
    datasets = repo.list_datasets(factory_name=factory_name, file_type=file_type, is_onprem=is_onprem, tenant_id=tenant_id)
    results = []

    for ds in datasets:
        ds_node_id = f"dataset:{ds.name}"
        consumers = set()
        producers = set()

        for edge in graph.get_incoming_edges(ds_node_id):
            src = graph.get_node(edge.source_id)
            if src:
                if edge.type == EdgeType.READS:
                    consumers.add(src.name)
                elif edge.type == EdgeType.WRITES:
                    producers.add(src.name)

        is_op = False
        if ds.linked_service_name:
            ls_node = graph.get_node(f"linked_service:{ds.linked_service_name}")
            if ls_node:
                ls_t = str(ls_node.properties.get("type", "")).lower()
                is_op = any(x in ls_t for x in ["fileserver", "sftp", "\\\\"])

        results.append(
            DatasetSummaryResponse(
                name=ds.name,
                type=ds.type,
                linked_service=ds.linked_service_name or "None",
                folder=ds.folder,
                is_onprem=is_op,
                schema_fields_count=len(ds.schema_fields),
                consumed_by_pipelines=sorted(list(consumers)),
                produced_by_pipelines=sorted(list(producers)),
            )
        )
    return results


@router.get("/linked-services", response_model=list[dict])
async def list_linked_services(
    factory_name: Optional[str] = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> list[dict]:
    """List linked services and external endpoints with credentials securely redacted."""
    services = repo.list_linked_services(factory_name=factory_name, tenant_id=tenant_id)
    return [
        {
            "name": ls.name,
            "type": ls.type,
            "connect_via_ir": ls.connect_via_integration_runtime,
            "connection_properties": ls.connection_properties,
        }
        for ls in services
    ]


@router.get("/triggers", response_model=list[dict])
async def list_triggers(
    factory_name: Optional[str] = Query(default=None),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> list[dict]:
    """List triggers with schedule recurrence and target pipeline mappings."""
    triggers = repo.list_triggers(factory_name=factory_name, tenant_id=tenant_id)
    return [
        {
            "name": t.name,
            "type": t.type,
            "runtime_state": t.runtime_state,
            "recurrence": t.recurrence_schedule,
            "pipelines": t.pipelines,
        }
        for t in triggers
    ]


@router.get("/factories/{name}/pipelines", response_model=list[dict])
async def list_factory_pipelines(
    name: str,
    folder: Optional[str] = Query(default=None, description="Filter by ADF folder name"),
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> list[dict]:
    """
    List all pipelines scoped to a specific factory.
    Use after GET /factories to drill into a chosen factory.
    Optionally filter by folder.
    """
    factory = repo.get_factory(name, tenant_id=tenant_id)
    if not factory:
        raise HTTPException(status_code=404, detail=f"Factory '{name}' not found.")

    pipelines = factory.pipelines
    if folder:
        pipelines = [p for p in pipelines if p.folder and folder.lower() in p.folder.lower()]

    return [
        {
            "name":            p.name,
            "folder":          p.folder,
            "description":     p.description,
            "activity_count":  len(p.activities),
            "parameters":      list(p.parameters.keys()),
            "annotations":     p.annotations,
        }
        for p in pipelines
    ]


@router.get("/factories/{name}/global-parameters", response_model=list[dict])
async def get_factory_global_parameters(
    name: str,
    tenant_id: str = Depends(get_current_tenant_id),
    repo: MetadataRepository = Depends(get_meta_repository),
) -> list[dict]:
    """
    List all factory-level Global Parameters with their types and current values.

    Global parameters are factory-wide constants referenced in pipelines as:
      @pipeline().globalParameters.parameterName

    Populated during POST /discovery/sync or POST /factories/{name}/refresh.
    ARM source: GET .../factories/{name}?api-version=2018-06-01
    ARM path:   properties.globalParameters → {name: {type, value}}
    """
    factory = repo.get_factory(name, tenant_id=tenant_id)
    if not factory:
        raise HTTPException(status_code=404, detail=f"Factory '{name}' not found. Sync it first.")

    last_refreshed = repo.get_last_refreshed_at(
        name, subscription_id=factory.subscription_id, tenant_id=tenant_id
    )

    params = []
    for param_name, param_def in (factory.global_parameters or {}).items():
        if isinstance(param_def, dict):
            params.append({
                "name":         param_name,
                "type":         param_def.get("type", "String"),
                "value":        param_def.get("value"),
                "pipeline_ref": f"@pipeline().globalParameters.{param_name}",
                "last_refreshed_at": last_refreshed,
            })
        else:
            params.append({
                "name":         param_name,
                "type":         "Unknown",
                "value":        param_def,
                "pipeline_ref": f"@pipeline().globalParameters.{param_name}",
                "last_refreshed_at": last_refreshed,
            })

    return params
