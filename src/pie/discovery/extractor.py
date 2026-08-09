"""Azure Data Factory metadata extraction engine supporting direct REST and SDK pagination."""

import requests
from typing import Any
from pie.core.exceptions import PieDiscoveryError
from pie.core.logging import get_logger
from pie.discovery.models import (
    FactoryMetadata,
    Spike2Result,
    PipelineMetadata,
    DatasetMetadata,
    LinkedServiceMetadata,
    TriggerMetadata,
    DataFlowMetadata,
)
from pie.discovery.normalizer import AdfNormalizer

logger = get_logger(__name__)


class AdfMetadataExtractor:
    """Extracts and normalizes live metadata from Azure Data Factory instances."""

    def __init__(self, access_token: str, subscription_id: str):
        self.access_token = access_token
        self.subscription_id = subscription_id
        self.headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

    def _fetch_all_pages(self, url: str) -> list[dict[str, Any]]:
        """Fetch all pages from an Azure Management REST endpoint."""
        items: list[dict[str, Any]] = []
        next_url: str | None = url

        while next_url:
            resp = requests.get(next_url, headers=self.headers, timeout=20)
            if not resp.ok:
                logger.warning(f"ARM REST API returned status {resp.status_code}: {resp.text[:200]}")
                break
            data = resp.json()
            items.extend(data.get("value", []))
            next_url = data.get("nextLink")

        return items

    def extract_pipelines(self, resource_group: str, factory_name: str) -> list[PipelineMetadata]:
        """Extract all pipelines from the target Data Factory."""
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DataFactory/factories/{factory_name}/pipelines?api-version=2018-06-01"
        raw_items = self._fetch_all_pages(url)
        pipelines = []

        for raw in raw_items:
            normalized = AdfNormalizer.normalize_pipeline(raw, pipeline_id=raw.get("id"))
            pipelines.append(normalized)
            logger.info(f"  [success][OK][/success] Discovered Pipeline: [bold white]{normalized.name}[/bold white] ({len(normalized.activities)} activities)")

        return pipelines

    def extract_datasets(self, resource_group: str, factory_name: str) -> list[DatasetMetadata]:
        """Extract all datasets from the target Data Factory."""
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DataFactory/factories/{factory_name}/datasets?api-version=2018-06-01"
        raw_items = self._fetch_all_pages(url)
        datasets = []

        for raw in raw_items:
            normalized = AdfNormalizer.normalize_dataset(raw, dataset_id=raw.get("id"))
            datasets.append(normalized)
            logger.info(f"  [success][OK][/success] Discovered Dataset: [cyan]{normalized.name}[/cyan] ({normalized.type}) -> LS: [magenta]{normalized.linked_service_name}[/magenta]")

        return datasets

    def extract_linked_services(self, resource_group: str, factory_name: str) -> list[LinkedServiceMetadata]:
        """Extract all linked services from the target Data Factory."""
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DataFactory/factories/{factory_name}/linkedservices?api-version=2018-06-01"
        raw_items = self._fetch_all_pages(url)
        linked_services = []

        for raw in raw_items:
            normalized = AdfNormalizer.normalize_linked_service(raw, ls_id=raw.get("id"))
            linked_services.append(normalized)
            logger.info(f"  [success][OK][/success] Discovered Linked Service: [bold magenta]{normalized.name}[/bold magenta] ({normalized.type})")

        return linked_services

    def extract_triggers(self, resource_group: str, factory_name: str) -> list[TriggerMetadata]:
        """Extract all triggers from the target Data Factory."""
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DataFactory/factories/{factory_name}/triggers?api-version=2018-06-01"
        raw_items = self._fetch_all_pages(url)
        triggers = []

        for raw in raw_items:
            normalized = AdfNormalizer.normalize_trigger(raw, trigger_id=raw.get("id"))
            triggers.append(normalized)
            logger.info(f"  [success][OK][/success] Discovered Trigger: [yellow]{normalized.name}[/yellow] ({normalized.runtime_state}) -> Targets: {normalized.pipelines}")

        return triggers

    def extract_data_flows(self, resource_group: str, factory_name: str) -> list[DataFlowMetadata]:
        """Extract all data flows from the target Data Factory."""
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DataFactory/factories/{factory_name}/dataflows?api-version=2018-06-01"
        raw_items = self._fetch_all_pages(url)
        data_flows = []

        for raw in raw_items:
            normalized = AdfNormalizer.normalize_data_flow(raw, df_id=raw.get("id"))
            data_flows.append(normalized)
            logger.info(f"  [success][OK][/success] Discovered Data Flow: [bold cyan]{normalized.name}[/bold cyan]")

        return data_flows

    def extract_factory_properties(self, resource_group: str, factory_name: str) -> dict[str, Any]:
        """Fetch factory-level resource properties including global parameters."""
        url = f"https://management.azure.com/subscriptions/{self.subscription_id}/resourceGroups/{resource_group}/providers/Microsoft.DataFactory/factories/{factory_name}?api-version=2018-06-01"
        try:
            resp = requests.get(url, headers=self.headers, timeout=20)
            if resp.ok:
                props = resp.json().get("properties", {})
                global_params = props.get("globalParameters", {})
                logger.info(f"  [success][OK][/success] Discovered {len(global_params)} Global Parameter(s)")
                return global_params
        except Exception as e:
            logger.warning(f"Failed fetching factory properties: {e}")
        return {}

    def extract_entire_factory(self, resource_group: str, factory_name: str, location: str = "centralus") -> FactoryMetadata:
        """Extract and normalize all resources for a Data Factory instance."""
        global_params = self.extract_factory_properties(resource_group, factory_name)
        pipelines = self.extract_pipelines(resource_group, factory_name)
        datasets = self.extract_datasets(resource_group, factory_name)
        linked_services = self.extract_linked_services(resource_group, factory_name)
        triggers = self.extract_triggers(resource_group, factory_name)
        data_flows = self.extract_data_flows(resource_group, factory_name)

        total_activities = sum(len(p.activities) for p in pipelines)
        summary = {
            "pipelines": len(pipelines),
            "activities": total_activities,
            "datasets": len(datasets),
            "linked_services": len(linked_services),
            "triggers": len(triggers),
            "data_flows": len(data_flows),
            "global_parameters": len(global_params),
        }

        return FactoryMetadata(
            factory_name=factory_name,
            resource_group=resource_group,
            subscription_id=self.subscription_id,
            location=location,
            global_parameters=global_params,
            pipelines=pipelines,
            datasets=datasets,
            linked_services=linked_services,
            triggers=triggers,
            data_flows=data_flows,
            summary=summary,
        )
