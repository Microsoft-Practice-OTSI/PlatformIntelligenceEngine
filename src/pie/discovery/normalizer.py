"""Metadata Normalization Layer: Translates heterogeneous ADF JSON schemas into unified domain models."""

from typing import Any
from pie.discovery.models import (
    PipelineMetadata,
    ActivityMetadata,
    DatasetMetadata,
    LinkedServiceMetadata,
    TriggerMetadata,
    DataFlowMetadata,
    ParameterDefinition,
    VariableDefinition,
    RetryPolicy,
)
from pie.core.logging import get_logger

logger = get_logger(__name__)


class AdfNormalizer:
    """Normalizes raw ADF Management API objects into strict PIE domain models."""

    @staticmethod
    def normalize_parameters(raw_params: dict[str, Any] | None) -> dict[str, ParameterDefinition]:
        """Convert ADF parameter dictionary to normalized ParameterDefinitions."""
        if not raw_params:
            return {}
        normalized = {}
        for param_name, param_def in raw_params.items():
            if isinstance(param_def, dict):
                normalized[param_name] = ParameterDefinition(
                    name=param_name,
                    type=param_def.get("type", "String"),
                    default_value=param_def.get("defaultValue", None),
                )
            else:
                normalized[param_name] = ParameterDefinition(name=param_name, default_value=param_def)
        return normalized

    @staticmethod
    def normalize_variables(raw_vars: dict[str, Any] | None) -> dict[str, VariableDefinition]:
        """Convert ADF variable dictionary to normalized VariableDefinitions."""
        if not raw_vars:
            return {}
        normalized = {}
        for var_name, var_def in raw_vars.items():
            if isinstance(var_def, dict):
                normalized[var_name] = VariableDefinition(
                    name=var_name,
                    type=var_def.get("type", "String"),
                    default_value=var_def.get("defaultValue", None),
                )
            else:
                normalized[var_name] = VariableDefinition(name=var_name, default_value=var_def)
        return normalized

    @classmethod
    def normalize_activity(cls, raw: dict[str, Any]) -> ActivityMetadata:
        """Convert raw activity JSON into ActivityMetadata."""
        name = raw.get("name", "UnnamedActivity")
        act_type = raw.get("type", "Unknown")
        description = raw.get("description")

        # Depends On
        depends_on = []
        for dep in raw.get("dependsOn", []):
            if isinstance(dep, dict) and "activity" in dep:
                depends_on.append(dep["activity"])
            elif isinstance(dep, str):
                depends_on.append(dep)

        # Inputs and Outputs (Datasets)
        inputs = []
        for inp in raw.get("inputs", []):
            if isinstance(inp, dict) and "referenceName" in inp:
                inputs.append(inp["referenceName"])
            elif isinstance(inp, str):
                inputs.append(inp)

        outputs = []
        for out in raw.get("outputs", []):
            if isinstance(out, dict) and "referenceName" in out:
                outputs.append(out["referenceName"])
            elif isinstance(out, str):
                outputs.append(out)

        # Linked Service reference
        linked_service = None
        raw_ls = raw.get("linkedServiceName")
        if isinstance(raw_ls, dict):
            linked_service = raw_ls.get("referenceName")
        elif isinstance(raw_ls, str):
            linked_service = raw_ls

        # Execute Pipeline reference
        called_pipeline = None
        if act_type == "ExecutePipeline":
            type_props = raw.get("typeProperties", {})
            pipe_ref = type_props.get("pipeline", {})
            if isinstance(pipe_ref, dict):
                called_pipeline = pipe_ref.get("referenceName")

        # Retry policy
        policy = raw.get("policy", {})
        retry_dict = policy.get("retry", 0) if isinstance(policy, dict) else 0
        retry_interval = policy.get("retryIntervalInSeconds", 30) if isinstance(policy, dict) else 30
        retry_policy = RetryPolicy(
            count=retry_dict if isinstance(retry_dict, int) else 0,
            interval_in_seconds=retry_interval,
        )
        timeout = policy.get("timeout", "0.12:00:00") if isinstance(policy, dict) else "0.12:00:00"

        return ActivityMetadata(
            name=name,
            type=act_type,
            description=description,
            depends_on=depends_on,
            inputs=inputs,
            outputs=outputs,
            linked_service=linked_service,
            called_pipeline=called_pipeline,
            retry_policy=retry_policy,
            timeout=timeout,
            type_properties=raw.get("typeProperties", {}) or {},
        )

    @classmethod
    def normalize_pipeline(cls, raw: dict[str, Any], pipeline_id: str | None = None) -> PipelineMetadata:
        """Convert raw pipeline JSON into PipelineMetadata."""
        name = raw.get("name", "UnnamedPipeline")
        properties = raw.get("properties", raw)
        folder_dict = properties.get("folder")
        folder = folder_dict.get("name") if isinstance(folder_dict, dict) else (folder_dict if isinstance(folder_dict, str) else None)

        activities = [cls.normalize_activity(act) for act in properties.get("activities", [])]
        parameters = cls.normalize_parameters(properties.get("parameters"))
        variables = cls.normalize_variables(properties.get("variables"))
        annotations = properties.get("annotations", []) or []

        return PipelineMetadata(
            name=name,
            id=pipeline_id or raw.get("id", f"/pipelines/{name}"),
            folder=folder,
            description=properties.get("description"),
            parameters=parameters,
            variables=variables,
            annotations=annotations,
            activities=activities,
            concurrency=properties.get("concurrency"),
        )

    @classmethod
    def normalize_dataset(cls, raw: dict[str, Any], dataset_id: str | None = None) -> DatasetMetadata:
        """Convert raw dataset JSON into DatasetMetadata."""
        name = raw.get("name", "UnnamedDataset")
        properties = raw.get("properties", raw)
        ds_type = properties.get("type", "GenericDataset")

        folder_dict = properties.get("folder")
        folder = folder_dict.get("name") if isinstance(folder_dict, dict) else (folder_dict if isinstance(folder_dict, str) else None)

        # Linked Service
        ls_ref = properties.get("linkedServiceName", {})
        ls_name = ls_ref.get("referenceName", "UnknownLS") if isinstance(ls_ref, dict) else str(ls_ref)

        # Schema fields
        schema_fields = []
        raw_schema = properties.get("schema", [])
        if isinstance(raw_schema, list):
            for field in raw_schema:
                if isinstance(field, dict):
                    schema_fields.append({
                        "name": field.get("name", ""),
                        "type": field.get("type", "String"),
                    })

        parameters = cls.normalize_parameters(properties.get("parameters"))
        type_props = properties.get("typeProperties", {}) or {}

        return DatasetMetadata(
            name=name,
            id=dataset_id or raw.get("id", f"/datasets/{name}"),
            type=ds_type,
            folder=folder,
            description=properties.get("description"),
            linked_service_name=ls_name,
            schema_fields=schema_fields,
            parameters=parameters,
            location_details=type_props,
        )

    @classmethod
    def normalize_linked_service(cls, raw: dict[str, Any], ls_id: str | None = None) -> LinkedServiceMetadata:
        """Convert raw linked service JSON into LinkedServiceMetadata (secrets sanitized)."""
        name = raw.get("name", "UnnamedLinkedService")
        properties = raw.get("properties", raw)
        ls_type = properties.get("type", "GenericLinkedService")

        # Sanitize sensitive properties
        type_props = properties.get("typeProperties", {}) or {}
        sanitized_props = {}
        for k, v in type_props.items():
            k_lower = k.lower()
            if any(secret_kw in k_lower for secret_kw in ["password", "secret", "key", "token", "connectionstring"]):
                sanitized_props[k] = "[REDACTED_BY_PIE_DISCOVERY]"
            else:
                sanitized_props[k] = v

        connect_via = None
        connect_ref = properties.get("connectVia")
        if isinstance(connect_ref, dict):
            connect_via = connect_ref.get("referenceName")

        return LinkedServiceMetadata(
            name=name,
            id=ls_id or raw.get("id", f"/linkedServices/{name}"),
            type=ls_type,
            description=properties.get("description"),
            connect_via_integration_runtime=connect_via,
            connection_properties=sanitized_props,
        )

    @classmethod
    def normalize_trigger(cls, raw: dict[str, Any], trigger_id: str | None = None) -> TriggerMetadata:
        """Convert raw trigger JSON into TriggerMetadata."""
        name = raw.get("name", "UnnamedTrigger")
        properties = raw.get("properties", raw)
        trig_type = properties.get("type", "ScheduleTrigger")
        runtime_state = properties.get("runtimeState", "Started")

        # Target pipelines
        pipelines = []
        for p in properties.get("pipelines", []):
            if isinstance(p, dict):
                pipe_ref = p.get("pipelineReference", {})
                if isinstance(pipe_ref, dict) and "referenceName" in pipe_ref:
                    pipelines.append(pipe_ref["referenceName"])
            elif isinstance(p, str):
                pipelines.append(p)

        # Recurrence schedule
        recurrence = properties.get("typeProperties", {}).get("recurrence")
        recurrence_str = None
        if recurrence and isinstance(recurrence, dict):
            freq = recurrence.get("frequency", "Day")
            interval = recurrence.get("interval", 1)
            recurrence_str = f"Every {interval} {freq}(s)"

        return TriggerMetadata(
            name=name,
            id=trigger_id or raw.get("id", f"/triggers/{name}"),
            type=trig_type,
            description=properties.get("description"),
            runtime_state=runtime_state,
            recurrence_schedule=recurrence_str,
            pipelines=pipelines,
            parameters=properties.get("typeProperties", {}) or {},
        )

    @classmethod
    def normalize_data_flow(cls, raw: dict[str, Any], df_id: str | None = None) -> DataFlowMetadata:
        """Convert raw data flow JSON into DataFlowMetadata."""
        name = raw.get("name", "UnnamedDataFlow")
        properties = raw.get("properties", raw)

        folder_dict = properties.get("folder")
        folder = folder_dict.get("name") if isinstance(folder_dict, dict) else (folder_dict if isinstance(folder_dict, str) else None)

        sources = []
        for s in properties.get("typeProperties", {}).get("sources", []):
            if isinstance(s, dict):
                ds = s.get("dataset", {})
                if isinstance(ds, dict) and "referenceName" in ds:
                    sources.append(ds["referenceName"])

        sinks = []
        for s in properties.get("typeProperties", {}).get("sinks", []):
            if isinstance(s, dict):
                ds = s.get("dataset", {})
                if isinstance(ds, dict) and "referenceName" in ds:
                    sinks.append(ds["referenceName"])

        transformations = []
        for t in properties.get("typeProperties", {}).get("transformations", []):
            if isinstance(t, dict) and "name" in t:
                transformations.append(t["name"])

        return DataFlowMetadata(
            name=name,
            id=df_id or raw.get("id", f"/dataFlows/{name}"),
            type=properties.get("type", "MappingDataFlow"),
            description=properties.get("description"),
            folder=folder,
            sources=sources,
            sinks=sinks,
            transformations=transformations,
        )
