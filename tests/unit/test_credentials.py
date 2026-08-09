"""Unit tests for CredentialFactory and authentication modes."""

import pytest
from pie.core.config import Settings, AuthMode
from pie.auth.credentials import CredentialFactory, MockTokenCredential
from pie.core.exceptions import PieAuthError


def test_credential_factory_mock_mode():
    """Verify Mock mode returns MockTokenCredential instance."""
    settings = Settings(auth_mode=AuthMode.MOCK)
    cred, desc = CredentialFactory.get_credential(settings)
    assert isinstance(cred, MockTokenCredential)
    assert "Mock" in desc

    token = cred.get_token("https://management.azure.com/.default")
    assert token.token.startswith("mock-bearer-token")


def test_credential_factory_device_code_mode():
    """Verify Device Code mode instantiates DeviceCodeCredential."""
    settings = Settings(auth_mode=AuthMode.DEVICE_CODE)
    cred, desc = CredentialFactory.get_credential(settings)
    assert "Device Code" in desc


def test_service_principal_missing_credentials_raises_error():
    """Verify Service Principal mode requires client_id, secret, and tenant_id."""
    settings = Settings(
        auth_mode=AuthMode.SERVICE_PRINCIPAL,
        tenant_id=None,
        client_id=None,
        client_secret=None,
    )
    with pytest.raises(PieAuthError) as exc_info:
        CredentialFactory.get_credential(settings)
    assert "requires AZURE_TENANT_ID" in str(exc_info.value)
