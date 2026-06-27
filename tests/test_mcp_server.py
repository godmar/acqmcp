from pathlib import Path

import httpx
import pytest

from acqmcp.alma_client import AlmaApiClient
from acqmcp.mcp_server import AlmaApiSurface, build_mcp_server
from acqmcp.openapi_catalog import AcqOpenAPICatalog
from acqmcp.settings import Settings


def test_generated_tool_names_are_unique() -> None:
    acq_catalog = AcqOpenAPICatalog.from_file(Path("acq.json"))
    bibs_catalog = AcqOpenAPICatalog.from_file(Path("bibs.json"))

    names = [
        operation.tool_name
        for catalog in [acq_catalog, bibs_catalog]
        for operation in catalog.operations.values()
    ]

    assert len(names) == len(set(names))
    assert "get_acq_funds" in names
    assert "get_acq_vendors_by_vendorCode" in names
    assert "get_bibs" in names
    assert "get_bibs_by_mms_id_holdings" in names


async def test_mcp_registers_combined_acq_and_bibs_tools() -> None:
    settings = Settings(
        ACQ_API_KEY="acq-secret",
        BIBS_API_KEY="bibs-secret",
        API_BASE_URL="https://api.example.edu",
        MCP_BEARER_TOKEN="token",
        MCP_URL="https://mcp.example.edu",
    )
    acq_catalog = AcqOpenAPICatalog.from_file(Path("acq.json"))
    bibs_catalog = AcqOpenAPICatalog.from_file(Path("bibs.json"))
    mcp = build_mcp_server(
        settings=settings,
        api_surfaces=[
            AlmaApiSurface(
                name="acq",
                display_name="Alma Acquisitions",
                catalog=acq_catalog,
                client=AlmaApiClient(
                    base_url="https://api.example.edu",
                    api_key="acq-secret",
                    catalog=acq_catalog,
                    transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
                ),
            ),
            AlmaApiSurface(
                name="bibs",
                display_name="Alma Bibliographic and Inventory",
                catalog=bibs_catalog,
                client=AlmaApiClient(
                    base_url="https://api.example.edu",
                    api_key="bibs-secret",
                    catalog=bibs_catalog,
                    transport=httpx.MockTransport(lambda request: httpx.Response(200, json={})),
                ),
            ),
        ],
    )

    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}
    reminders_tool = next(tool for tool in tools if tool.name == "get_bibs_by_mms_id_reminders")

    assert len(tools) == 59 + 77 + 3
    assert {"get_acq_funds", "get_bibs", "get_bibs_by_mms_id_holdings"} <= names
    assert {"list_alma_operations", "get_alma_operation", "invoke_alma_operation"} <= names
    assert "from_" in reminders_tool.inputSchema["properties"]
    assert "from" not in reminders_tool.inputSchema["properties"]


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

    alma_client = AlmaApiClient(
        base_url="https://api.example.edu",
        api_key="secret",
        catalog=catalog,
        transport=httpx.MockTransport(handler),
    )
    mcp = build_mcp_server(
        settings=Settings(
            ACQ_API_KEY="secret",
            BIBS_API_KEY="bibs-secret",
            API_BASE_URL="https://api.example.edu",
            MCP_BEARER_TOKEN="token",
            MCP_URL="https://mcp.example.edu",
        ),
        api_surfaces=[
            AlmaApiSurface(
                name="acq",
                display_name="Alma Acquisitions",
                catalog=catalog,
                client=alma_client,
            )
        ],
    )

    tools = await mcp.list_tools()
    names = {tool.name for tool in tools}

    assert names == {
        "list_alma_operations",
        "get_alma_operation",
        "invoke_alma_operation",
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
