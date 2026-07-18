from unittest.mock import MagicMock, patch

from ai.services.ai_service import AiService


@patch("ai.services.ai_service.settings")
def test_get_azure_client_is_cached(mock_settings):
    """__get_azure_client is static/zero-arg with a process-stable result —
    repeated calls must return the same cached client, not build a new one."""
    mock_settings.azure_api_key = "fake-key"
    mock_settings.azure_endpoint = "https://example.invalid"

    get_client = AiService._AiService__get_azure_client
    get_client.cache_clear()
    try:
        client1 = get_client()
        client2 = get_client()
        assert client1 is client2
    finally:
        get_client.cache_clear()


@patch.object(AiService, "_AiService__get_azure_client")
def test_health_check_does_not_call_azure_completion(mock_get_client):
    """The health probe must verify the client is configured WITHOUT issuing a
    billable completion — otherwise every /api/ai/health hit costs money."""
    mock_client = MagicMock()
    mock_get_client.return_value = mock_client

    result = AiService.health_check()

    assert result == {"status": "healthy", "azure_connected": True}
    mock_get_client.assert_called_once()
    mock_client.complete.assert_not_called()
