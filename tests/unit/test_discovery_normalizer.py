"""Unit tests for AdfNormalizer and schema normalization layer."""

import pytest
from pie.discovery.normalizer import AdfNormalizer
from pie.discovery.models import PipelineMetadata, DatasetMetadata, LinkedServiceMetadata, TriggerMetadata


def test_normalize_activity_with_dependencies_and_datasets():
    """Verify raw activity JSON transforms into structured ActivityMetadata."""
    raw_act = {
        "name": "CopyCustomerData",
        "type": "Copy",
        "description": "Copy raw CSV to SQL staging",
        "dependsOn": [{"activity": "LookupWatermark", "dependencyConditions": ["Succeeded"]}],
        "inputs": [{"referenceName": "DS_Customer_CSV", "type": "DatasetReference"}],
        "outputs": [{"referenceName": "DS_Customer_Staging_SQL", "type": "DatasetReference"}],
        "linkedServiceName": {"referenceName": "LS_AzureBlob", "type": "LinkedServiceReference"},
        "policy": {
            "timeout": "0.01:00:00",
            "retry": 3,
            "retryIntervalInSeconds": 30,
        },
    }

    norm = AdfNormalizer.normalize_activity(raw_act)
    assert norm.name == "CopyCustomerData"
    assert norm.type == "Copy"
    assert norm.depends_on == ["LookupWatermark"]
    assert norm.inputs == ["DS_Customer_CSV"]
    assert norm.outputs == ["DS_Customer_Staging_SQL"]
    assert norm.linked_service == "LS_AzureBlob"
    assert norm.retry_policy.count == 3
    assert norm.retry_policy.interval_in_seconds == 30
    assert norm.timeout == "0.01:00:00"


def test_normalize_pipeline_with_parameters_and_variables():
    """Verify raw pipeline JSON transforms into structured PipelineMetadata."""
    raw_pipe = {
        "name": "PL_Sales_Ingestion",
        "id": "/subscriptions/sub-1/resourceGroups/rg-1/providers/Microsoft.DataFactory/factories/adf-1/pipelines/PL_Sales_Ingestion",
        "properties": {
            "description": "Daily sales loader",
            "folder": {"name": "Sales/Ingestion"},
            "parameters": {
                "LoadDate": {"type": "String", "defaultValue": "2026-08-08"},
                "Environment": {"type": "String", "defaultValue": "Prod"},
            },
            "variables": {
                "BatchId": {"type": "String", "defaultValue": "BATCH-001"},
            },
            "annotations": ["Sales", "Tier1"],
            "activities": [
                {"name": "LookupWatermark", "type": "Lookup"},
            ],
        },
    }

    norm = AdfNormalizer.normalize_pipeline(raw_pipe)
    assert norm.name == "PL_Sales_Ingestion"
    assert norm.folder == "Sales/Ingestion"
    assert len(norm.parameters) == 2
    assert norm.parameters["LoadDate"].default_value == "2026-08-08"
    assert norm.variables["BatchId"].default_value == "BATCH-001"
    assert norm.annotations == ["Sales", "Tier1"]
    assert len(norm.activities) == 1
    assert norm.activities[0].name == "LookupWatermark"


def test_normalize_linked_service_sanitizes_secrets():
    """Verify sensitive connection properties are redacted."""
    raw_ls = {
        "name": "LS_AzureSql_DWH",
        "id": "/linkedServices/LS_AzureSql_DWH",
        "properties": {
            "type": "AzureSqlDatabase",
            "typeProperties": {
                "server": "sql-prod.database.windows.net",
                "database": "DWH",
                "password": "SuperSecretPassword123!",
                "connectionString": "Server=tcp:sql-prod...;Password=Secret123!",
            },
        },
    }

    norm = AdfNormalizer.normalize_linked_service(raw_ls)
    assert norm.name == "LS_AzureSql_DWH"
    assert norm.connection_properties["server"] == "sql-prod.database.windows.net"
    assert norm.connection_properties["password"] == "[REDACTED_BY_PIE_DISCOVERY]"
    assert norm.connection_properties["connectionString"] == "[REDACTED_BY_PIE_DISCOVERY]"


def test_normalize_dataset_schema_and_location():
    """Verify dataset columns and folder hierarchy are parsed."""
    raw_ds = {
        "name": "DS_Customer_Parquet",
        "properties": {
            "type": "Parquet",
            "folder": {"name": "CRM/Curated"},
            "linkedServiceName": {"referenceName": "LS_DataLake"},
            "schema": [
                {"name": "CustId", "type": "String"},
                {"name": "Amount", "type": "Decimal"},
            ],
            "typeProperties": {"container": "curated", "directory": "crm/customer"},
        },
    }

    norm = AdfNormalizer.normalize_dataset(raw_ds)
    assert norm.name == "DS_Customer_Parquet"
    assert norm.type == "Parquet"
    assert norm.folder == "CRM/Curated"
    assert norm.linked_service_name == "LS_DataLake"
    assert len(norm.schema_fields) == 2
    assert norm.schema_fields[0]["name"] == "CustId"
