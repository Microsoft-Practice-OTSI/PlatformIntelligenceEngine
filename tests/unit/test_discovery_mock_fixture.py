"""Unit tests for Spike 2 synthetic ADF fixture and JSON serialization."""

import pytest
from spikes.spike_2_discovery.mock_adf_fixture import get_mock_spike_2_result
from pie.discovery.models import Spike2Result


def test_spike_2_mock_fixture_integrity():
    """Verify mock ADF fixture produces valid, rich metadata."""
    result = get_mock_spike_2_result()
    assert isinstance(result, Spike2Result)
    assert result.status == "SUCCESS"
    assert result.total_factories == 1
    assert result.total_pipelines == 5
    assert result.total_activities == 9
    assert result.total_datasets == 5
    assert result.total_linked_services == 4
    assert result.total_triggers == 3
    assert result.total_data_flows == 1

    factory = result.factories[0]
    assert factory.factory_name == "adf-sales-enterprise-prod"

    # Verify pipeline activities
    pipe_names = [p.name for p in factory.pipelines]
    assert "PL_Customer_Daily_Ingestion" in pipe_names
    assert "PL_Master_Nightly_Orchestrator" in pipe_names

    # Verify JSON export capability
    json_export = result.model_dump_json()
    assert "PL_Customer_Daily_Ingestion" in json_export
    assert "LS_AzureSql_EnterpriseDWH" in json_export
    assert "TR_Daily_Midnight_Schedule" in json_export
