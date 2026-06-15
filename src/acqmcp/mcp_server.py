from __future__ import annotations

import inspect
from typing import Annotated, Any

from mcp.server.auth.settings import AuthSettings
from mcp.server.fastmcp import FastMCP
from pydantic import AnyHttpUrl, Field

from acqmcp.alma_client import AlmaAcquisitionsClient
from acqmcp.auth import StaticBearerTokenVerifier
from acqmcp.openapi_catalog import AcqOpenAPICatalog
from acqmcp.settings import Settings


JSON_TYPE_MAP = {
    "string": str,
    "integer": int,
    "number": float,
    "boolean": bool,
    "array": list,
    "object": dict,
}


def build_mcp_server(
    *,
    settings: Settings,
    catalog: AcqOpenAPICatalog,
    alma_client: AlmaAcquisitionsClient,
) -> FastMCP:
    mcp = FastMCP(
        name="Ex Libris Acquisitions",
        instructions=(
            f"This server exposes {len(catalog.operations)} operation-specific Alma "
            "Acquisitions tools, plus support tools. Prefer the operation-specific tools "
            "returned by MCP tools/list. Tool names are generated from HTTP method and "
            "path, for example GET /almaws/v1/acq/funds becomes get_acq_funds and GET "
            "/almaws/v1/acq/vendors/{vendorCode} becomes get_acq_vendors_by_vendorCode. "
            "The list_acq_operations, get_acq_operation, and invoke_acq_operation tools "
            "are support tools for discovery, inspection, and fallback calls. All calls "
            "are authenticated by the server with the configured Alma API key."
        ),
        host=settings.host,
        streamable_http_path="/mcp",
        json_response=True,
        stateless_http=True,
        token_verifier=StaticBearerTokenVerifier(settings.acq_mcp_bearer_token),
        auth=AuthSettings(
            issuer_url=AnyHttpUrl(settings.public_url),
            resource_server_url=AnyHttpUrl(settings.mcp_endpoint_url),
            required_scopes=[],
        ),
    )

    @mcp.resource("alma://acquisitions/openapi-summary")
    def openapi_summary() -> dict[str, Any]:
        """Return a compact summary of all configured acquisitions operations."""
        return {
            "title": catalog.spec.get("info", {}).get("title"),
            "version": catalog.spec.get("info", {}).get("version"),
            "operation_count": len(catalog.operations),
            "operations": catalog.list_operations(),
        }

    @mcp.tool()
    async def list_acq_operations(
        method: str | None = None,
        tag: str | None = None,
        text: str | None = None,
    ) -> dict[str, Any]:
        """List supported Alma Acquisitions API operations, optionally filtered."""
        operations = catalog.list_operations(method=method, tag=tag, text=text)
        return {"count": len(operations), "operations": operations}

    @mcp.tool()
    async def get_acq_operation(operation_id: str) -> dict[str, Any]:
        """Inspect one Alma Acquisitions operation before invoking it."""
        operation = catalog.get_operation(operation_id)
        return {
            **operation.summary_record(),
            "parameters": list(operation.parameters),
            "request_body": operation.request_body,
            "responses": operation.raw.get("responses", {}),
        }

    @mcp.tool()
    async def invoke_acq_operation(
        operation_id: str,
        path_params: dict[str, Any] | None = None,
        query_params: dict[str, Any] | None = None,
        body: Any = None,
        content_type: str = "application/json",
    ) -> dict[str, Any]:
        """Invoke an Alma Acquisitions API operation by operation_id."""
        return await alma_client.invoke_operation(
            operation_id=operation_id,
            path_params=path_params,
            query_params=query_params,
            body=body,
            content_type=content_type,
        )

    _register_operation_tools(mcp=mcp, catalog=catalog, alma_client=alma_client)

    return mcp


def _register_operation_tools(
    *,
    mcp: FastMCP,
    catalog: AcqOpenAPICatalog,
    alma_client: AlmaAcquisitionsClient,
) -> None:
    seen_names: set[str] = set()
    for operation in catalog.operations.values():
        if operation.tool_name in seen_names:
            raise ValueError(f"Duplicate MCP tool name generated: {operation.tool_name}")
        seen_names.add(operation.tool_name)

        tool = _build_operation_tool(
            operation_id=operation.operation_id,
            catalog=catalog,
            alma_client=alma_client,
        )
        mcp.add_tool(
            tool,
            name=operation.tool_name,
            description=_operation_tool_description(operation),
        )


def _build_operation_tool(
    *,
    operation_id: str,
    catalog: AcqOpenAPICatalog,
    alma_client: AlmaAcquisitionsClient,
):
    operation = catalog.get_operation(operation_id)
    path_param_names = operation.path_parameters
    query_param_names = {
        parameter["name"] for parameter in operation.parameters if parameter.get("in") == "query"
    }

    async def operation_tool(**kwargs: Any) -> dict[str, Any]:
        path_params = {name: kwargs.pop(name) for name in path_param_names if name in kwargs}
        query_params = {name: kwargs.pop(name) for name in query_param_names if name in kwargs}
        body = kwargs.pop("body", None)
        content_type = kwargs.pop("content_type", "application/json")
        if kwargs:
            raise ValueError(f"Unexpected arguments: {sorted(kwargs)}")
        return await alma_client.invoke_operation(
            operation_id=operation_id,
            path_params=path_params,
            query_params=query_params,
            body=body,
            content_type=content_type,
        )

    operation_tool.__name__ = operation.tool_name
    operation_tool.__doc__ = _operation_tool_description(operation)
    operation_tool.__signature__ = _operation_signature(operation)  # type: ignore[attr-defined]
    return operation_tool


def _operation_signature(operation) -> inspect.Signature:
    required_params: list[inspect.Parameter] = []
    optional_params: list[inspect.Parameter] = []

    for parameter in operation.parameters:
        location = parameter.get("in")
        if location not in {"path", "query"}:
            continue
        name = parameter["name"]
        schema = parameter.get("schema", {})
        annotation = _parameter_annotation(parameter)
        default = inspect.Parameter.empty if parameter.get("required") else schema.get("default", None)
        signature_param = inspect.Parameter(
            name=name,
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=default,
            annotation=annotation,
        )
        if default is inspect.Parameter.empty:
            required_params.append(signature_param)
        else:
            optional_params.append(signature_param)

    if operation.request_body is not None:
        body_param = inspect.Parameter(
            name="body",
            kind=inspect.Parameter.KEYWORD_ONLY,
            default=inspect.Parameter.empty if operation.requires_body else None,
            annotation=Annotated[dict[str, Any], Field(description="JSON request body for this Alma operation.")],
        )
        if operation.requires_body:
            required_params.append(body_param)
        else:
            optional_params.append(body_param)
        optional_params.append(
            inspect.Parameter(
                name="content_type",
                kind=inspect.Parameter.KEYWORD_ONLY,
                default="application/json",
                annotation=Annotated[str, Field(description="Request Content-Type header.")],
            )
        )

    return inspect.Signature(
        parameters=[*required_params, *optional_params],
        return_annotation=dict[str, Any],
    )


def _parameter_annotation(parameter: dict[str, Any]) -> Any:
    schema = parameter.get("schema", {})
    python_type = JSON_TYPE_MAP.get(schema.get("type"), Any)
    description = parameter.get("description") or f"{parameter.get('in', 'API')} parameter."
    return Annotated[python_type, Field(description=description)]


def _operation_tool_description(operation) -> str:
    lines = [operation.summary or operation.tool_name]
    if operation.description:
        lines.extend(["", operation.description])
    return "\n".join(lines)
