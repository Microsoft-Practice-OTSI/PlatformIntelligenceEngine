"""Domain models for Azure Data Factory metadata normalization."""

from datetime import datetime
from typing import Any
from pydantic import BaseModel, Field


class ParameterDefinition(BaseModel):
    """Pipeline or Dataset parameter definition."""
    name: str
    type: str = "String"
    default_value: Any = None


class VariableDefinition(BaseModel):
    """Pipeline variable definition."""
    name: str
    type: str = "String"
    default_value: Any = None


class RetryPolicy(BaseModel):
    """Activity retry policy specification."""
    count: int = 0
    interval_in_seconds: int = 30


class ActivityMetadata(BaseModel):
    """Normalized metadata for a single pipeline activity."""
    name: str
    type: str = Field(description="Copy, ExecutePipeline, DatabricksNotebook, Web, Lookup, ForEach, Until, etc.")
    description: str | None = None
    depends_on: list[str] = Field(default_factory=list, description="List of parent activity names")
    inputs: list[str] = Field(default_factory=list, description="Referenced source dataset names")
    outputs: list[str] = Field(default_factory=list, description="Referenced sink dataset names")
    linked_service: str | None = Field(default=None, description="Direct linked service reference if applicable")
    called_pipeline: str | None = Field(default=None, description="Child pipeline name for ExecutePipeline activities")
    retry_policy: RetryPolicy = Field(default_factory=RetryPolicy)
    timeout: str | None = Field(default="0.12:00:00", description="Activity execution timeout")
    type_properties: dict[str, Any] = Field(default_factory=dict, description="Normalized activity type properties")


class PipelineMetadata(BaseModel):
    """Normalized metadata for an Azure Data Factory Pipeline."""
    name: str
    id: str
    folder: str | None = Field(default=None, description="ADF UI folder hierarchy")
    description: str | None = None
    parameters: dict[str, ParameterDefinition] = Field(default_factory=dict)
    variables: dict[str, VariableDefinition] = Field(default_factory=dict)
    annotations: list[str] = Field(default_factory=list)
    activities: list[ActivityMetadata] = Field(default_factory=list)
    concurrency: int | None = Field(default=None, description="Max concurrent pipeline runs")


class DatasetMetadata(BaseModel):
    """Normalized metadata for an ADF Dataset."""
    name: str
    id: str
    type: str = Field(description="AzureBlob, AzureSqlTable, DelimitedText, Parquet, Json, etc.")
    folder: str | None = None
    description: str | None = None
    linked_service_name: str = Field(description="Parent Linked Service name")
    schema_fields: list[dict[str, str]] = Field(default_factory=list, description="Column names and data types")
    parameters: dict[str, ParameterDefinition] = Field(default_factory=dict)
    location_details: dict[str, Any] = Field(default_factory=dict, description="Container, path, table, or query")
    annotations: list[str] = Field(default_factory=list)


class LinkedServiceMetadata(BaseModel):
    """Normalized metadata for an ADF Linked Service."""
    name: str
    id: str
    type: str = Field(description="AzureBlobStorage, AzureSqlDatabase, AzureKeyVault, Databricks, RestService, etc.")
    description: str | None = None
    connect_via_integration_runtime: str | None = None
    connection_properties: dict[str, Any] = Field(
        default_factory=dict,
        description="Sanitized connection details (endpoints, server, database; secrets excluded)",
    )
    annotations: list[str] = Field(default_factory=list)


class TriggerMetadata(BaseModel):
    """Normalized metadata for an ADF Trigger."""
    name: str
    id: str
    type: str = Field(description="ScheduleTrigger, TumblingWindowTrigger, BlobEventsTrigger, CustomEventsTrigger")
    description: str | None = None
    runtime_state: str = Field(default="Started", description="Started or Stopped")
    recurrence_schedule: str | None = Field(default=None, description="Recurrence expression or cron frequency")
    pipelines: list[str] = Field(default_factory=list, description="Target pipeline names triggered by this schedule")
    parameters: dict[str, Any] = Field(default_factory=dict)
    annotations: list[str] = Field(default_factory=list)


class DataFlowMetadata(BaseModel):
    """Normalized metadata for an ADF Mapping Data Flow."""
    name: str
    id: str
    type: str = Field(default="MappingDataFlow")
    description: str | None = None
    folder: str | None = None
    sources: list[str] = Field(default_factory=list, description="Input dataset references")
    sinks: list[str] = Field(default_factory=list, description="Output dataset references")
    transformations: list[str] = Field(default_factory=list, description="Transformation steps")


class FactoryMetadata(BaseModel):
    """Consolidated metadata container for an entire Azure Data Factory instance."""
    factory_name: str
    resource_group: str
    subscription_id: str
    location: str
    extracted_at: datetime = Field(default_factory=datetime.utcnow)
    global_parameters: dict[str, Any] = Field(default_factory=dict, description="Factory-level Global Parameters accessible across all pipelines")
    pipelines: list[PipelineMetadata] = Field(default_factory=list)
    datasets: list[DatasetMetadata] = Field(default_factory=list)
    linked_services: list[LinkedServiceMetadata] = Field(default_factory=list)
    triggers: list[TriggerMetadata] = Field(default_factory=list)
    data_flows: list[DataFlowMetadata] = Field(default_factory=list)
    summary: dict[str, int] = Field(default_factory=dict)


class Spike2Result(BaseModel):
    """Standardized output schema for Spike 2 (ADF Metadata Extraction)."""
    spike_id: str = "spike_2_adf_metadata_extraction"
    status: str = "SUCCESS"
    executed_at: datetime = Field(default_factory=datetime.utcnow)
    factories: list[FactoryMetadata]
    total_factories: int
    total_pipelines: int
    total_activities: int
    total_datasets: int
    total_linked_services: int
    total_triggers: int
    total_data_flows: int
