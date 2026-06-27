import httpx
import pytest

from acqmcp.alma_client import AlmaApiClient
from acqmcp.openapi_catalog import AcqOpenAPICatalog


@pytest.mark.asyncio
async def test_invoke_operation_adds_api_key_and_returns_json() -> None:
    spec = {
        "paths": {
            "/almaws/v1/acq/test": {
                "get": {
                    "operationId": "get/almaws/v1/acq/test",
                    "parameters": [],
                }
            }
        }
    }
    catalog = AcqOpenAPICatalog(spec)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.params["apikey"] == "secret"
        return httpx.Response(200, json={"ok": True}, headers={"X-Exl-Api-Remaining": "42"})

    client = AlmaApiClient(
        base_url="https://api.example.edu",
        api_key="secret",
        catalog=catalog,
        transport=httpx.MockTransport(handler),
    )

    result = await client.invoke_operation(operation_id="get/almaws/v1/acq/test")

    assert result["ok"] is True
    assert result["status_code"] == 200
    assert result["body"] == {"ok": True}
    assert result["headers"]["x-exl-api-remaining"] == "42"
