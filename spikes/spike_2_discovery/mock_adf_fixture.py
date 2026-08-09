"""Synthetic ADF environment fixture providing realistic enterprise metadata for Spike 2."""

from datetime import datetime
from pie.discovery.models import (
    FactoryMetadata,
    PipelineMetadata,
    ActivityMetadata,
    DatasetMetadata,
    LinkedServiceMetadata,
    TriggerMetadata,
    DataFlowMetadata,
    ParameterDefinition,
    VariableDefinition,
    RetryPolicy,
    Spike2Result,
)


def get_mock_spike_2_result() -> Spike2Result:
    """Generate enterprise Data Factory metadata for offline validation."""
    sub_id = "00000000-0000-0000-0000-000000000001"
    rg_name = "rg-enterprise-sales-prod"
    factory_name = "adf-sales-enterprise-prod"

    # 1. Linked Services
    ls_blob = LinkedServiceMetadata(
        name="LS_BlobStorage_RawDataLake",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/linkedServices/LS_BlobStorage_RawDataLake",
        type="AzureBlobStorage",
        description="Landing storage account for raw vendor and CRM data files",
        connection_properties={
            "accountEndpoint": "https://datalakeprod01.blob.core.windows.net/",
            "authType": "ManagedIdentity",
            "accountKey": "[REDACTED_BY_PIE_DISCOVERY]",
        },
    )

    ls_sql = LinkedServiceMetadata(
        name="LS_AzureSql_EnterpriseDWH",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/linkedServices/LS_AzureSql_EnterpriseDWH",
        type="AzureSqlDatabase",
        description="Enterprise Data Warehouse database hosting Star Schema and ODS",
        connection_properties={
            "server": "sql-sales-enterprise-prod.database.windows.net",
            "database": "SalesEnterpriseDWH",
            "authType": "ActiveDirectoryIntegrated",
        },
    )

    ls_databricks = LinkedServiceMetadata(
        name="LS_AzureDatabricks_Engineering",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/linkedServices/LS_AzureDatabricks_Engineering",
        type="AzureDatabricks",
        description="Databricks workspace for heavy distributed feature engineering",
        connection_properties={
            "domain": "https://adb-1234567890.azuredatabricks.net",
            "clusterId": "0808-120000-jobcluster",
        },
    )

    ls_kv = LinkedServiceMetadata(
        name="LS_AzureKeyVault_Secrets",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/linkedServices/LS_AzureKeyVault_Secrets",
        type="AzureKeyVault",
        description="Centralized secrets vault",
        connection_properties={"baseUrl": "https://kv-sales-prod-eastus.vault.azure.net/"},
    )

    # 2. Datasets
    ds_raw_customer = DatasetMetadata(
        name="DS_Blob_Customer_Raw_CSV",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/datasets/DS_Blob_Customer_Raw_CSV",
        type="DelimitedText",
        folder="CRM/Raw",
        description="Raw incoming customer export files from SFDC",
        linked_service_name="LS_BlobStorage_RawDataLake",
        schema_fields=[
            {"name": "CustomerId", "type": "String"},
            {"name": "CustomerName", "type": "String"},
            {"name": "Email", "type": "String"},
            {"name": "SignupDate", "type": "String"},
            {"name": "CountryCode", "type": "String"},
        ],
        parameters={"Environment": ParameterDefinition(name="Environment", default_value="Prod")},
        location_details={"container": "raw-landing", "directory": "crm/customer/@{formatDateTime(utcnow(),'yyyy/MM/dd')}"},
    )

    ds_staging_customer = DatasetMetadata(
        name="DS_AzureSql_CustomerStaging",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/datasets/DS_AzureSql_CustomerStaging",
        type="AzureSqlTable",
        folder="CRM/Staging",
        description="Transient staging table for batch upserts",
        linked_service_name="LS_AzureSql_EnterpriseDWH",
        schema_fields=[
            {"name": "CustomerId", "type": "String"},
            {"name": "CustomerName", "type": "String"},
            {"name": "Email", "type": "String"},
            {"name": "CountryCode", "type": "String"},
            {"name": "BatchId", "type": "Int64"},
        ],
        location_details={"schema": "stg", "table": "Customer_Raw_Staging"},
    )

    ds_dim_customer = DatasetMetadata(
        name="DS_AzureSql_DimCustomer",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/datasets/DS_AzureSql_DimCustomer",
        type="AzureSqlTable",
        folder="Analytics/Dimensions",
        description="Production Dimension table supporting SCD Type 2 history",
        linked_service_name="LS_AzureSql_EnterpriseDWH",
        schema_fields=[
            {"name": "CustomerSK", "type": "Int64"},
            {"name": "CustomerId", "type": "String"},
            {"name": "CustomerName", "type": "String"},
            {"name": "IsCurrent", "type": "Boolean"},
            {"name": "EffectiveDate", "type": "DateTime"},
            {"name": "EndDate", "type": "DateTime"},
        ],
        location_details={"schema": "dim", "table": "DimCustomer"},
    )

    ds_raw_orders = DatasetMetadata(
        name="DS_Parquet_RawOrders",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/datasets/DS_Parquet_RawOrders",
        type="Parquet",
        folder="Orders/Raw",
        description="High-volume sales orders ingested hourly",
        linked_service_name="LS_BlobStorage_RawDataLake",
        schema_fields=[
            {"name": "OrderId", "type": "String"},
            {"name": "CustomerId", "type": "String"},
            {"name": "OrderAmount", "type": "Decimal"},
            {"name": "Currency", "type": "String"},
            {"name": "OrderTimestamp", "type": "DateTime"},
        ],
        location_details={"container": "curated", "directory": "sales/orders"},
    )

    ds_fact_orders = DatasetMetadata(
        name="DS_AzureSql_FactOrders",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/datasets/DS_AzureSql_FactOrders",
        type="AzureSqlTable",
        folder="Analytics/Facts",
        description="Central Fact table for Enterprise Revenue Reporting",
        linked_service_name="LS_AzureSql_EnterpriseDWH",
        schema_fields=[
            {"name": "OrderSK", "type": "Int64"},
            {"name": "CustomerSK", "type": "Int64"},
            {"name": "DateSK", "type": "Int32"},
            {"name": "TotalRevenue", "type": "Decimal"},
        ],
        location_details={"schema": "fact", "table": "FactOrders"},
    )

    # 3. Pipelines
    # Pipeline 1: PL_Customer_Daily_Ingestion
    act_watermark = ActivityMetadata(
        name="Lookup_Last_Watermark",
        type="Lookup",
        description="Query the watermark tracking table in Azure SQL",
        linked_service="LS_AzureSql_EnterpriseDWH",
        retry_policy=RetryPolicy(count=2, interval_in_seconds=20),
        type_properties={"source": "SELECT MAX(LastModified) as Watermark FROM sys.WatermarkAudit"},
    )

    act_copy_customer = ActivityMetadata(
        name="Copy_Blob_To_Staging_SQL",
        type="Copy",
        description="Bulk load raw CSV into staging SQL table with schema validation",
        depends_on=["Lookup_Last_Watermark"],
        inputs=["DS_Blob_Customer_Raw_CSV"],
        outputs=["DS_AzureSql_CustomerStaging"],
        retry_policy=RetryPolicy(count=3, interval_in_seconds=30),
        timeout="0.02:00:00",
        type_properties={"enableStaging": False, "writeBatchSize": 10000},
    )

    act_databricks_enrich = ActivityMetadata(
        name="Databricks_Enrich_Customer",
        type="DatabricksNotebook",
        description="Run customer deduplication and geo-IP lookup in Apache Spark",
        depends_on=["Copy_Blob_To_Staging_SQL"],
        linked_service="LS_AzureDatabricks_Engineering",
        retry_policy=RetryPolicy(count=1, interval_in_seconds=60),
        type_properties={"notebookPath": "/Shared/ETL/EnrichCustomerData"},
    )

    act_call_scd2 = ActivityMetadata(
        name="Execute_SCD2_Dimension_Pipeline",
        type="ExecutePipeline",
        description="Invoke downstream dimension pipeline to apply Type 2 changes",
        depends_on=["Databricks_Enrich_Customer"],
        called_pipeline="PL_DimCustomer_SCD2_Transform",
        type_properties={"waitOnCompletion": True},
    )

    pipe_customer = PipelineMetadata(
        name="PL_Customer_Daily_Ingestion",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/pipelines/PL_Customer_Daily_Ingestion",
        folder="Ingestion/CRM",
        description="Orchestrates ingestion of daily CRM exports into Enterprise Staging and triggers Dimension processing",
        parameters={
            "BatchId": ParameterDefinition(name="BatchId", type="String", default_value="BATCH_AUTO"),
            "TriggerTime": ParameterDefinition(name="TriggerTime", type="String", default_value="@{utcnow()}"),
        },
        variables={"RowCounter": VariableDefinition(name="RowCounter", type="Integer", default_value=0)},
        annotations=["Domain:Customer", "Tier:Critical", "SLA:06:00UTC"],
        activities=[act_watermark, act_copy_customer, act_databricks_enrich, act_call_scd2],
    )

    # Pipeline 2: PL_DimCustomer_SCD2_Transform
    act_dataflow_scd2 = ActivityMetadata(
        name="DataFlow_Apply_SCD2",
        type="ExecuteDataFlow",
        description="Execute Mapping Data Flow with Surrogate Key generation and SCD2 logic",
        inputs=["DS_AzureSql_CustomerStaging"],
        outputs=["DS_AzureSql_DimCustomer"],
        type_properties={"dataFlow": {"referenceName": "DF_Transform_Customer_Dedupe"}},
    )

    pipe_scd2 = PipelineMetadata(
        name="PL_DimCustomer_SCD2_Transform",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/pipelines/PL_DimCustomer_SCD2_Transform",
        folder="Transform/Dimensions",
        description="Processes staging customer records into DimCustomer applying Slowly Changing Dimensions Type 2",
        parameters={"RunDate": ParameterDefinition(name="RunDate", type="String", default_value="@{formatDateTime(utcnow(),'yyyy-MM-dd')}")},
        annotations=["Domain:Customer", "Type:Transform"],
        activities=[act_dataflow_scd2],
    )

    # Pipeline 3: PL_Orders_Ingestion_S3_to_SQL
    act_copy_orders = ActivityMetadata(
        name="Copy_Parquet_Orders_To_Fact",
        type="Copy",
        description="Ingest parquet orders files into FactOrders table in DW",
        inputs=["DS_Parquet_RawOrders"],
        outputs=["DS_AzureSql_FactOrders"],
        retry_policy=RetryPolicy(count=2, interval_in_seconds=45),
        timeout="0.04:00:00",
    )

    pipe_orders = PipelineMetadata(
        name="PL_Orders_Ingestion_S3_to_SQL",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/pipelines/PL_Orders_Ingestion_S3_to_SQL",
        folder="Ingestion/Orders",
        description="Hourly ingestion of e-commerce order streams into FactOrders",
        annotations=["Domain:Sales", "Tier:HighFrequency"],
        activities=[act_copy_orders],
    )

    # Pipeline 4: PL_Master_Nightly_Orchestrator
    act_run_customer = ActivityMetadata(
        name="Trigger_Customer_Pipeline",
        type="ExecutePipeline",
        called_pipeline="PL_Customer_Daily_Ingestion",
        type_properties={"waitOnCompletion": True},
    )
    act_run_orders = ActivityMetadata(
        name="Trigger_Orders_Pipeline",
        type="ExecutePipeline",
        depends_on=["Trigger_Customer_Pipeline"],
        called_pipeline="PL_Orders_Ingestion_S3_to_SQL",
        type_properties={"waitOnCompletion": True},
    )
    pipe_master = PipelineMetadata(
        name="PL_Master_Nightly_Orchestrator",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/pipelines/PL_Master_Nightly_Orchestrator",
        folder="Orchestration",
        description="Top-level master orchestrator executing customer and sales ETL dependencies in sequence",
        annotations=["Orchestrator", "MasterSchedule"],
        activities=[act_run_customer, act_run_orders],
    )

    # Pipeline 5: PL_Legacy_Orphan_Export (Technical Debt: Unreferenced and zero-retry)
    act_orphan_copy = ActivityMetadata(
        name="Copy_Legacy_Export",
        type="Copy",
        description="Unreferenced legacy export activity without retry policy",
        inputs=["DS_Blob_Customer_Raw_CSV"],
        outputs=["DS_AzureSql_CustomerStaging"],
        retry_policy=RetryPolicy(count=0, interval_in_seconds=30),
    )
    pipe_orphan = PipelineMetadata(
        name="PL_Legacy_Orphan_Export",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/pipelines/PL_Legacy_Orphan_Export",
        folder="Legacy/Archive",
        description="Deprecated pipeline that is no longer scheduled or called",
        annotations=["Deprecated", "Debt"],
        activities=[act_orphan_copy],
    )


    # 4. Triggers
    tr_daily = TriggerMetadata(
        name="TR_Daily_Midnight_Schedule",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/triggers/TR_Daily_Midnight_Schedule",
        type="ScheduleTrigger",
        description="Fires every day at 00:00 UTC to begin nightly batch",
        runtime_state="Started",
        recurrence_schedule="Every 1 Day(s) at 00:00 UTC",
        pipelines=["PL_Master_Nightly_Orchestrator"],
    )

    tr_blob = TriggerMetadata(
        name="TR_Blob_Arrival_CustomerCSV",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/triggers/TR_Blob_Arrival_CustomerCSV",
        type="BlobEventsTrigger",
        description="Event-driven trigger listening to blob created events in raw-landing",
        runtime_state="Started",
        recurrence_schedule="Event: Microsoft.Storage.BlobCreated",
        pipelines=["PL_Customer_Daily_Ingestion"],
    )

    tr_tumbling = TriggerMetadata(
        name="TR_Hourly_TumblingWindow_Orders",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/triggers/TR_Hourly_TumblingWindow_Orders",
        type="TumblingWindowTrigger",
        description="Hourly self-healing window for order batching",
        runtime_state="Started",
        recurrence_schedule="Every 1 Hour(s)",
        pipelines=["PL_Orders_Ingestion_S3_to_SQL"],
    )

    # 5. Data Flows
    df_customer = DataFlowMetadata(
        name="DF_Transform_Customer_Dedupe",
        id=f"/subscriptions/{sub_id}/resourceGroups/{rg_name}/providers/Microsoft.DataFactory/factories/{factory_name}/dataFlows/DF_Transform_Customer_Dedupe",
        folder="Transforms",
        description="Mapping Data Flow performing fuzzy deduplication, surrogate key lookup, and SCD2 column hashing",
        sources=["DS_AzureSql_CustomerStaging"],
        sinks=["DS_AzureSql_DimCustomer"],
        transformations=["Filter_Valid_Email", "Derived_MD5_Hash", "Lookup_Existing_SK", "AlterRow_SCD2"],
    )

    all_pipelines = [pipe_master, pipe_customer, pipe_scd2, pipe_orders, pipe_orphan]
    all_datasets = [ds_raw_customer, ds_staging_customer, ds_dim_customer, ds_raw_orders, ds_fact_orders]
    all_linked_services = [ls_blob, ls_sql, ls_databricks, ls_kv]
    all_triggers = [tr_daily, tr_blob, tr_tumbling]
    all_data_flows = [df_customer]

    factory_1 = FactoryMetadata(
        factory_name=factory_name,
        resource_group=rg_name,
        subscription_id=sub_id,
        location="eastus",
        pipelines=all_pipelines,
        datasets=all_datasets,
        linked_services=all_linked_services,
        triggers=all_triggers,
        data_flows=all_data_flows,
        summary={
            "pipelines": len(all_pipelines),
            "activities": sum(len(p.activities) for p in all_pipelines),
            "datasets": len(all_datasets),
            "linked_services": len(all_linked_services),
            "triggers": len(all_triggers),
            "data_flows": len(all_data_flows),
        },
    )

    return Spike2Result(
        spike_id="spike_2_adf_metadata_extraction",
        status="SUCCESS",
        executed_at=datetime.utcnow(),
        factories=[factory_1],
        total_factories=1,
        total_pipelines=len(all_pipelines),
        total_activities=sum(len(p.activities) for p in all_pipelines),
        total_datasets=len(all_datasets),
        total_linked_services=len(all_linked_services),
        total_triggers=len(all_triggers),
        total_data_flows=len(all_data_flows),
    )
