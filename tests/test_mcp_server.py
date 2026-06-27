from pathlib import Path

import httpx
import pytest

from acqmcp.alma_client import AlmaAcquisitionsClient
from acqmcp.mcp_server import build_mcp_server
from acqmcp.openapi_catalog import AcqOpenAPICatalog
from acqmcp.settings import Settings


def test_generated_tool_names_are_unique() -> None:
    catalog = AcqOpenAPICatalog.from_file(Path("acq.json"))

    names = [operation.tool_name for operation in catalog.operations.values()]

    assert len(names) == len(set(names))
    assert "get_acq_funds" in names
    assert "get_acq_vendors_by_vendorCode" in names


async def test_mcp_registers_one_tool_per_operation_plus_support_tools() -> None:
    spec = {
        "paths": {
            "/almaws/v1/acq/vendors/{vendorCode}": {
                "get": {
                    "operationId": "get/almaws/v1/acq/vendors/{vendorCode}",
                    "summary": "Retrieve vendor",
                    "parameters": [
                        {"name": "vendorCode", "in": "path", "required": True, "schema": {"type": "string"}},
                        {"name": "view", "in": "query", "required": False, "schema": {"type": "string"}},
                    ],
                }
            }
        }
    }
    catalog = AcqOpenAPICatalog(spec)

    async def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/almaws/v1/acq/vendors/VEND1"
        assert request.url.params["view"] == "brief"
        return httpx.Response(200, json={"vendor": "VEND1"})

    alma_client = AlmaAcquisitionsClient(
        base_url="https://api.example.edu",
        api_key="secret",
        catalog=catalog,
        transport=httpx.MockTransport(handler),
    )
    mcp = build_mcp_server(
        settings=Settings(
            ACQ_API_KEY="secret",
            API_BASE_URL="https://api.example.edu",
            MCP_BEARER_TOKEN="token",
            MCP_URL="https://mcp.example.edu",
        ),
        catalog=catalog,
        alma_client=alma_client,
    )

    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert names == {
        "list_acq_operations",
        "get_acq_operation",
        "invoke_acq_operation",
        "get_acq_vendors_by_vendorCode",
    }
    vendor_tool = next(tool for tool in tools if tool.name == "get_acq_vendors_by_vendorCode")
    assert set(vendor_tool.inputSchema["properties"]) == {"vendorCode", "view"}
    assert vendor_tool.inputSchema["required"] == ["vendorCode"]
    assert "operationId" not in vendor_tool.description
    assert "HTTP:" not in vendor_tool.description

    result = await mcp.call_tool(
        "get_acq_vendors_by_vendorCode",
        {"vendorCode": "VEND1", "view": "brief"},
    )
    _, structured_content = result

    assert structured_content["status_code"] == 200
    assert structured_content["body"] == {"vendor": "VEND1"}
